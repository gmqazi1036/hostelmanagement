from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app import models, schemas, auth
from datetime import datetime, date
from typing import List

router = APIRouter(
    prefix="/api/leaves",
    tags=["Leaves & Lifecycle"]
)

# Roles
student_or_admin_dependency = Depends(auth.RoleChecker([
    models.UserRole.STUDENT, models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN
]))
warden_dependency = Depends(auth.RoleChecker([
    models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN
]))

@router.post("/apply", response_model=schemas.LeaveOut, status_code=status.HTTP_201_CREATED)
def apply_leave(leave_in: schemas.LeaveApply, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    Apply for a gate pass / leave (Students only).
    Database trigger prevents application if student status is 'Suspended'.
    """
    if current_user.role != models.UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can apply for leaves."
        )
    
    # Resolve student profile
    student = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found."
        )

    # Validate dates
    if leave_in.end_date < leave_in.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date cannot be before start date."
        )

    try:
        # Check if database is SQLite or PostgreSQL (for testing fallback)
        is_sqlite = db.bind.dialect.name == "sqlite"

        # If SQLite, check student status here in python since DB triggers aren't running
        if is_sqlite and student.status == models.StudentLifecycleStatus.Suspended:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leave application blocked: Student is currently Suspended."
            )

        new_leave = models.LeaveRecord(
            student_id=student.id,
            start_date=leave_in.start_date,
            end_date=leave_in.end_date,
            reason=leave_in.reason,
            status=models.LeaveRecordStatus.Pending
        )
        db.add(new_leave)
        db.commit()
        db.refresh(new_leave)
        return new_leave
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        # Handle database trigger exception (suspended students)
        err_msg = str(e)
        if "Suspended" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Leave application blocked: Student is currently Suspended."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit leave application: {err_msg}"
        )


@router.post("/{leave_id}/approve", response_model=schemas.LeaveOut)
def approve_leave(leave_id: int, req: schemas.LeaveApprove, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    Warden approves or rejects a leave.
    Approval triggers the PG trigger to mark Mess Attendance as 'OFF' and apply rebate billing.
    If database dialect is SQLite (e.g. testing), it falls back to Python-based replication.
    """
    # Verify warden status
    if current_user.role not in [models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only wardens or admins can approve leaves."
        )

    leave = db.query(models.LeaveRecord).filter(models.LeaveRecord.id == leave_id).first()
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave record not found."
        )

    if leave.status != models.LeaveRecordStatus.Pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave application is already {leave.status.value}."
        )

    try:
        leave.status = req.status
        leave.approved_by = current_user.id
        leave.approved_at = datetime.now()

        # Fallback Python automation for non-PostgreSQL (e.g. SQLite tests)
        if req.status == models.LeaveRecordStatus.Approved and db.bind.dialect.name == "sqlite":
            from datetime import timedelta
            
            # Loop through dates and mark Mess Attendance as 'OFF'
            curr_date = leave.start_date
            months_affected = {}
            while curr_date <= leave.end_date:
                # Upsert mess attendance in SQLite
                existing_att = db.query(models.MessAttendance).filter(
                    models.MessAttendance.student_id == leave.student_id,
                    models.MessAttendance.date == curr_date
                ).first()
                if existing_att:
                    existing_att.status = models.MessAttendanceStatus.OFF
                else:
                    new_att = models.MessAttendance(
                        student_id=leave.student_id,
                        date=curr_date,
                        status=models.MessAttendanceStatus.OFF
                    )
                    db.add(new_att)

                # Count leave days grouped by billing month (first of the month)
                month_start = curr_date.replace(day=1)
                months_affected[month_start] = months_affected.get(month_start, 0) + 1
                curr_date += timedelta(days=1)
            
            db.flush()

            # Apply rebates to monthly invoices in SQLite
            daily_rebate_rate = 150.00
            for billing_month, days_count in months_affected.items():
                existing_inv = db.query(models.Invoice).filter(
                    models.Invoice.student_id == leave.student_id,
                    models.Invoice.billing_month == billing_month
                ).first()
                
                computed_rebate = float(days_count) * daily_rebate_rate
                
                if existing_inv:
                    # Limit rebate to base amount
                    existing_inv.rebate_amount = min(float(existing_inv.base_amount), float(existing_inv.rebate_amount) + computed_rebate)
                else:
                    new_inv = models.Invoice(
                        student_id=leave.student_id,
                        billing_month=billing_month,
                        base_amount=5000.00,
                        rebate_amount=min(5000.00, computed_rebate),
                        status=models.InvoicePaymentStatus.Unpaid
                    )
                    db.add(new_inv)

        db.commit()
        db.refresh(leave)
        return leave
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update leave status: {str(e)}"
        )


@router.get("", response_model=List[schemas.LeaveOut])
def list_leaves(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    List leave applications (Students see their own; Wardens/Admins see all).
    """
    if current_user.role == models.UserRole.STUDENT:
        student = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
        if not student:
            return []
        return db.query(models.LeaveRecord).filter(models.LeaveRecord.student_id == student.id).all()
    else:
        return db.query(models.LeaveRecord).all()


@router.put("/students/{student_id}/status", status_code=status.HTTP_200_OK, dependencies=[warden_dependency])
def update_student_lifecycle_status(student_id: int, status_val: models.StudentLifecycleStatus, db: Session = Depends(get_db)):
    """
    Student Suspension Workflow:
    Updates student status to Suspended, Active, Left, or Graduated.
    If 'Suspended', database triggers will automatically update future daily active mess attendance to 'SUSPENDED'.
    """
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found."
        )

    try:
        old_status = student.status
        student.status = status_val
        
        # Fallback Python automation for non-PostgreSQL (e.g. SQLite tests)
        if db.bind.dialect.name == "sqlite" and old_status != status_val:
            today = date.today()
            if status_val == models.StudentLifecycleStatus.Suspended:
                # Update future mess attendance to SUSPENDED in SQLite
                future_records = db.query(models.MessAttendance).filter(
                    models.MessAttendance.student_id == student.id,
                    models.MessAttendance.date >= today
                ).all()
                for record in future_records:
                    record.status = models.MessAttendanceStatus.SUSPENDED
            elif status_val == models.StudentLifecycleStatus.Active and old_status == models.StudentLifecycleStatus.Suspended:
                # Restore suspended future mess attendance in SQLite
                future_records = db.query(models.MessAttendance).filter(
                    models.MessAttendance.student_id == student.id,
                    models.MessAttendance.date >= today,
                    models.MessAttendance.status == models.MessAttendanceStatus.SUSPENDED
                ).all()
                for record in future_records:
                    record.status = models.MessAttendanceStatus.ON
                    
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update student lifecycle status: {str(e)}"
        )

    return {"message": f"Successfully updated student {student.student_id} status to {status_val.value}."}
