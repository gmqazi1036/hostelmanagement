from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, auth
import pandas as pd
import io
import re
from datetime import date
from typing import List

router = APIRouter(
    prefix="/api/allotments",
    tags=["Hostel & Bed Allotments"]
)

admin_role_dependency = Depends(auth.RoleChecker([models.UserRole.SUPER_ADMIN, models.UserRole.WARDEN]))

@router.post("/import", status_code=status.HTTP_201_CREATED, dependencies=[admin_role_dependency])
def import_excel_allotments(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Parses Excel/CSV files, validates schema and room capacity, handles master student mapping,
    creates rooms/beds dynamically, and records active allotments with assets.
    """
    content = file.file.read()
    filename = file.filename.lower()
    
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.endswith('.xlsx') or filename.endswith('.xls'):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file format. Please upload an Excel (.xlsx/.xls) or CSV (.csv) file."
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse spreadsheet file: {str(e)}"
        )

    # Schema Validation
    required_cols = [
        "Academic_Session", "Student_ID", "Student_Name", "Father_Name", 
        "Class_Course", "Contact_Number", "Hostel_Name", "Floor_No", "Room_No", "Bed_No"
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing columns in uploaded sheet: {missing_cols}"
        )

    df = df.fillna("")
    
    # Check for duplicates within the spreadsheet itself
    spreadsheet_bed_duplicates = df[df.duplicated(subset=["Academic_Session", "Hostel_Name", "Room_No", "Bed_No"], keep=False)]
    if not spreadsheet_bed_duplicates.empty:
        dupes_info = spreadsheet_bed_duplicates[["Academic_Session", "Hostel_Name", "Room_No", "Bed_No"]].to_dict(orient="records")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duplicate bed allocations found within the uploaded sheet: {dupes_info}"
        )

    spreadsheet_student_duplicates = df[df.duplicated(subset=["Academic_Session", "Student_ID"], keep=False)]
    if not spreadsheet_student_duplicates.empty:
        dupes_info = spreadsheet_student_duplicates[["Academic_Session", "Student_ID"]].to_dict(orient="records")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Multiple room allocations for the same student in the same session in the uploaded sheet: {dupes_info}"
        )

    allotments_created = 0
    
    try:
        for index, row in df.iterrows():
            session_name = str(row["Academic_Session"]).strip()
            student_code = str(row["Student_ID"]).strip()
            student_name = str(row["Student_Name"]).strip()
            father_name = str(row["Father_Name"]).strip()
            class_course = str(row["Class_Course"]).strip()
            contact_number = str(row["Contact_Number"]).strip()
            hostel_name = str(row["Hostel_Name"]).strip()
            floor_no = int(row["Floor_No"])
            room_no = str(row["Room_No"]).strip()
            bed_no = str(row["Bed_No"]).strip()

            if not student_code or not session_name or not hostel_name or not room_no or not bed_no:
                continue

            # CRITICAL check: student_id must be exactly 4 digits numeric only
            if not re.match(r"^\d{4}$", student_code):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {index+2}: Student ID '{student_code}' is invalid. Student ID must be exactly 4 digits numeric only."
                )

            # CRITICAL check: Qadri Hostel is under construction
            if hostel_name.lower() == "qadri hostel" or "qadri" in hostel_name.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {index+2}: Cannot allocate room in '{hostel_name}'. This hostel is currently under construction."
                )

            # a) Ensure Session master
            db_session = db.query(models.AcademicSession).filter(models.AcademicSession.session_name == session_name).first()
            if not db_session:
                db_session = models.AcademicSession(session_name=session_name)
                db.add(db_session)
                db.flush()

            # b) Ensure Student master
            db_student = db.query(models.Student).filter(models.Student.student_id == student_code).first()
            if not db_student:
                username = student_code
                user_pwd_hash = auth.hash_password(f"{username}123")
                db_user = models.User(username=username, password_hash=user_pwd_hash, role=models.UserRole.STUDENT)
                db.add(db_user)
                db.flush()

                db_student = models.Student(
                    user_id=db_user.id,
                    student_id=student_code,
                    name=student_name,
                    father_name=father_name,
                    class_course=class_course,
                    contact_number=contact_number,
                    status=models.StudentLifecycleStatus.Active
                )
                db.add(db_student)
                db.flush()
            else:
                db_student.name = student_name
                db_student.father_name = father_name
                db_student.class_course = class_course
                db_student.contact_number = contact_number
                db.flush()

            # c) Ensure Hostel exists
            db_hostel = db.query(models.Hostel).filter(models.Hostel.name == hostel_name).first()
            if not db_hostel:
                db_hostel = models.Hostel(name=hostel_name)
                db.add(db_hostel)
                db.flush()

            # d) Ensure Room exists
            db_room = db.query(models.Room).filter(
                models.Room.hostel_id == db_hostel.id, 
                models.Room.room_no == room_no
            ).first()
            if not db_room:
                db_room = models.Room(hostel_id=db_hostel.id, floor_no=floor_no, room_no=room_no)
                db.add(db_room)
                db.flush()

            # e) Ensure Bed exists
            db_bed = db.query(models.Bed).filter(
                models.Bed.room_id == db_room.id, 
                models.Bed.bed_no == bed_no
            ).first()
            if not db_bed:
                # Check room capacity limit for Azhari Hostel
                current_beds_count = db.query(models.Bed).filter(models.Bed.room_id == db_room.id).count()
                if hostel_name.lower() == "azhari hostel" and current_beds_count >= 8:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Row {index+2}: Cannot add Bed '{bed_no}' in Room '{room_no}'. Azhari Hostel has a maximum room capacity of 8 students."
                    )
                db_bed = models.Bed(room_id=db_room.id, bed_no=bed_no)
                db.add(db_bed)
                db.flush()

            # f) Validation check on Database: Bed or Student already active in this session?
            existing_student_allotment = db.query(models.AllotmentHistory).filter(
                models.AllotmentHistory.student_id == db_student.student_id,
                models.AllotmentHistory.session_id == db_session.id,
                models.AllotmentHistory.vacated_date == None
            ).first()
            
            existing_bed_allotment = db.query(models.AllotmentHistory).filter(
                models.AllotmentHistory.bed_id == db_bed.id,
                models.AllotmentHistory.session_id == db_session.id,
                models.AllotmentHistory.vacated_date == None
            ).first()

            if existing_student_allotment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {index+2}: Student {student_code} already has an active allotment in Session {session_name}."
                )
                
            if existing_bed_allotment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Row {index+2}: Bed {bed_no} in Room {room_no} of Hostel {hostel_name} is already occupied in Session {session_name}."
                )

            # g) Create Allotment
            allotment = models.AllotmentHistory(
                student_id=db_student.student_id,
                bed_id=db_bed.id,
                session_id=db_session.id,
                allotment_date=date.today()
            )
            db.add(allotment)
            db.flush()

            # h) Assign Default Assets
            default_asset_names = ["Bed Frame", "Mattress", "Study Table", "Room Key"]
            for asset_name in default_asset_names:
                asset = db.query(models.Asset).filter(models.Asset.name == asset_name).first()
                if not asset:
                    asset = models.Asset(name=asset_name)
                    db.add(asset)
                    db.flush()
                
                student_asset = models.StudentAsset(
                    allotment_id=allotment.id,
                    asset_id=asset.id,
                    serial_no=f"SR-{hostel_name[:3].upper()}-{room_no}-{bed_no}-{asset_name[:2].upper()}",
                    condition=models.AssetConditionType.Good
                )
                db.add(student_asset)

            allotments_created += 1

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed during bulk import: {str(e)}"
        )

    return {"message": f"Successfully parsed Excel file. Created {allotments_created} student allotments and assigned assets."}


@router.post("/swap", status_code=status.HTTP_200_OK, dependencies=[admin_role_dependency])
def swap_beds(req: schemas.BedSwapRequest, db: Session = Depends(get_db)):
    """
    Bed/Room Swipe Module: Swap/exchange allotments of Student X and Student Y mid-session
    retaining historical records using transaction safety.
    """
    allotment_x = db.query(models.AllotmentHistory).filter(
        models.AllotmentHistory.student_id == req.student_x_id,
        models.AllotmentHistory.vacated_date == None
    ).first()

    allotment_y = db.query(models.AllotmentHistory).filter(
        models.AllotmentHistory.student_id == req.student_y_id,
        models.AllotmentHistory.vacated_date == None
    ).first()

    if not allotment_x or not allotment_y:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Both students must have active allotments in the current session to swap."
        )

    if allotment_x.session_id != allotment_y.session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot swap beds across different academic sessions."
        )

    current_session_id = allotment_x.session_id
    today = date.today()

    try:
        # Vacate current allotments
        allotment_x.vacated_date = today
        allotment_y.vacated_date = today
        
        bed_x_id = allotment_x.bed_id
        bed_y_id = allotment_y.bed_id

        db.flush()

        # Create new active allotments with swapped beds
        new_allotment_x = models.AllotmentHistory(
            student_id=req.student_x_id,
            bed_id=bed_y_id,
            session_id=current_session_id,
            allotment_date=today
        )
        new_allotment_y = models.AllotmentHistory(
            student_id=req.student_y_id,
            bed_id=bed_x_id,
            session_id=current_session_id,
            allotment_date=today
        )

        db.add(new_allotment_x)
        db.add(new_allotment_y)
        db.flush()

        # Swap assets
        for asset_x in allotment_x.allocated_assets:
            new_asset = models.StudentAsset(
                allotment_id=new_allotment_x.id,
                asset_id=asset_x.asset_id,
                serial_no=asset_x.serial_no,
                condition=asset_x.condition
            )
            db.add(new_asset)

        for asset_y in allotment_y.allocated_assets:
            new_asset = models.StudentAsset(
                allotment_id=new_allotment_y.id,
                asset_id=asset_y.asset_id,
                serial_no=asset_y.serial_no,
                condition=asset_y.condition
            )
            db.add(new_asset)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bed swap transaction: {str(e)}"
        )

    return {"message": f"Successfully swapped bed allocations for student ID {req.student_x_id} and {req.student_y_id}."}


@router.post("/transfer", status_code=status.HTTP_200_OK, dependencies=[admin_role_dependency])
def transfer_to_vacant_room(req: schemas.RoomTransferRequest, db: Session = Depends(get_db)):
    """
    Vacant Room Transfer: Moves Student X to an empty bed in real-time.
    """
    current_allotment = db.query(models.AllotmentHistory).filter(
        models.AllotmentHistory.student_id == req.student_id,
        models.AllotmentHistory.vacated_date == None
    ).first()

    if not current_allotment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student has no active allotment to transfer from."
        )

    session_id = current_allotment.session_id
    today = date.today()

    target_bed = db.query(models.Bed).filter(models.Bed.id == req.target_bed_id).first()
    if not target_bed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target bed does not exist."
        )

    is_occupied = db.query(models.AllotmentHistory).filter(
        models.AllotmentHistory.bed_id == req.target_bed_id,
        models.AllotmentHistory.session_id == session_id,
        models.AllotmentHistory.vacated_date == None
    ).first()

    if is_occupied:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target bed is already occupied. Use swap endpoint instead."
        )

    try:
        # Vacate current bed
        current_allotment.vacated_date = today
        db.flush()

        # Allocate new bed
        new_allotment = models.AllotmentHistory(
            student_id=req.student_id,
            bed_id=req.target_bed_id,
            session_id=session_id,
            allotment_date=today
        )
        db.add(new_allotment)
        db.flush()

        # Assign default assets
        for old_asset in current_allotment.allocated_assets:
            new_asset = models.StudentAsset(
                allotment_id=new_allotment.id,
                asset_id=old_asset.asset_id,
                serial_no=old_asset.serial_no,
                condition=old_asset.condition
            )
            db.add(new_asset)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Room transfer failed: {str(e)}"
        )

    return {"message": f"Successfully transferred student ID {req.student_id} to Bed ID {req.target_bed_id}."}


@router.get("/capacity", dependencies=[admin_role_dependency])
def get_room_occupancy_and_capacity(db: Session = Depends(get_db)):
    """
    Real-time room occupancy and capacity calculations.
    """
    rooms = db.query(models.Room).all()
    result = []

    for room in rooms:
        total_beds = len(room.beds)
        occupied_beds = db.query(models.AllotmentHistory).join(models.Bed).filter(
            models.Bed.room_id == room.id,
            models.AllotmentHistory.vacated_date == None
        ).count()

        vacant_beds = total_beds - occupied_beds
        
        result.append({
            "hostel_name": room.hostel.name,
            "floor_no": room.floor_no,
            "room_no": room.room_no,
            "capacity": total_beds,
            "occupied": occupied_beds,
            "vacant": vacant_beds
        })
        
    return result
