from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, auth
from datetime import datetime
from typing import List

router = APIRouter(
    prefix="/api/visitors",
    tags=["Visitor Management"]
)

# Gate Guard role check
gate_role_dependency = Depends(auth.RoleChecker([
    models.UserRole.GATE_GUARD, models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN
]))

@router.post("/entry", response_model=schemas.VisitorOut, status_code=status.HTTP_201_CREATED, dependencies=[gate_role_dependency])
def log_visitor_entry(visitor_in: schemas.VisitorCreate, db: Session = Depends(get_db)):
    """
    Log incoming parent/visitor details at the gate.
    Triggers a mock notification (push / SMS) to the student.
    """
    student = db.query(models.Student).filter(models.Student.student_id == visitor_in.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found."
        )

    # 1. Create visitor entry record
    new_visitor = models.Visitor(
        student_id=visitor_in.student_id,
        visitor_name=visitor_in.visitor_name,
        relationship=visitor_in.relationship,
        contact_number=visitor_in.contact_number,
        purpose=visitor_in.purpose,
        entry_time=datetime.now()
    )
    
    db.add(new_visitor)
    db.commit()
    db.refresh(new_visitor)

    # 2. Trigger notification stub
    # In a production system, this sends an SMS or a Push Notification via Firebase (FCM) or Twilio
    send_notification_to_student(
        student_phone=student.contact_number,
        student_name=student.name,
        visitor_name=visitor_in.visitor_name,
        relationship=visitor_in.relationship
    )

    return new_visitor


@router.post("/{visitor_id}/exit", response_model=schemas.VisitorOut, dependencies=[gate_role_dependency])
def log_visitor_exit(visitor_id: int, db: Session = Depends(get_db)):
    """
    Log visitor departure.
    """
    visitor = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    if not visitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visitor entry record not found."
        )

    if visitor.exit_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Visitor has already logged out."
        )

    visitor.exit_time = datetime.now()
    db.commit()
    db.refresh(visitor)
    return visitor


@router.get("", response_model=List[schemas.VisitorOut], dependencies=[gate_role_dependency])
def list_visitor_logs(db: Session = Depends(get_db)):
    """
    Fetch all visitor logs (Guards/Admins).
    """
    return db.query(models.Visitor).order_by(models.Visitor.entry_time.desc()).all()


def send_notification_to_student(student_phone: str, student_name: str, visitor_name: str, relationship: str):
    """
    Stub method simulating SMS/Push notification.
    """
    print(f"[NOTIFICATION SENT] SMS to {student_phone} (Student: {student_name}):")
    print(f"\"Hello {student_name}, your {relationship}, {visitor_name}, has arrived at the gate at {datetime.now().strftime('%H:%M')}. Please coordinate with security.\"")
