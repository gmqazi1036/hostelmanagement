from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, auth
from typing import List

router = APIRouter(
    prefix="/api/assets",
    tags=["Asset Tracking"]
)

# Warden or Student
student_or_admin_dependency = Depends(auth.RoleChecker([
    models.UserRole.STUDENT, models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN
]))
warden_dependency = Depends(auth.RoleChecker([
    models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN
]))

@router.get("/my", response_model=List[schemas.StudentAssetOut])
def get_my_allocated_assets(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    Get assets allocated to the logged-in student.
    """
    if current_user.role != models.UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a student."
        )

    student = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found."
        )

    # Fetch active allotment
    active_allotment = db.query(models.AllotmentHistory).filter(
        models.AllotmentHistory.student_id == student.id,
        models.AllotmentHistory.vacated_date == None
    ).first()

    if not active_allotment:
        return []

    # Get student assets
    student_assets = db.query(models.StudentAsset).filter(models.StudentAsset.allotment_id == active_allotment.id).all()
    
    # Map to schema
    res = []
    for sa in student_assets:
        res.append(schemas.StudentAssetOut(
            id=sa.id,
            allotment_id=sa.allotment_id,
            asset_name=sa.asset.name,
            serial_no=sa.serial_no,
            condition=sa.condition
        ))
    return res


@router.get("/student/{student_id}", response_model=List[schemas.StudentAssetOut], dependencies=[warden_dependency])
def get_student_assets_by_warden(student_id: int, db: Session = Depends(get_db)):
    """
    Get assets allocated to a specific student (Warden only).
    """
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found."
        )

    # Fetch active allotment
    active_allotment = db.query(models.AllotmentHistory).filter(
        models.AllotmentHistory.student_id == student.id,
        models.AllotmentHistory.vacated_date == None
    ).first()

    if not active_allotment:
        return []

    student_assets = db.query(models.StudentAsset).filter(models.StudentAsset.allotment_id == active_allotment.id).all()
    
    res = []
    for sa in student_assets:
        res.append(schemas.StudentAssetOut(
            id=sa.id,
            allotment_id=sa.allotment_id,
            asset_name=sa.asset.name,
            serial_no=sa.serial_no,
            condition=sa.condition
        ))
    return res


@router.post("/audit", status_code=status.HTTP_200_OK, dependencies=[warden_dependency])
def audit_student_asset(req: schemas.AssetAuditRequest, db: Session = Depends(get_db)):
    """
    Audit/inspect an allocated asset during check-out or routine checks (Warden only).
    Updates condition to Good, Damaged, or Lost.
    """
    sa = db.query(models.StudentAsset).filter(models.StudentAsset.id == req.student_asset_id).first()
    if not sa:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allocated student asset record not found."
        )

    sa.condition = req.condition
    db.commit()
    return {"message": f"Asset '{sa.asset.name}' condition updated to {req.condition.value}."}
