from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, auth
from datetime import datetime
from typing import List

router = APIRouter(
    prefix="/api/complaints",
    tags=["Complaints & Maintenance"]
)

@router.post("", response_model=schemas.ComplaintOut, status_code=status.HTTP_201_CREATED)
def raise_complaint(complaint_in: schemas.ComplaintCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    Raise a new complaint ticket (Students only).
    """
    if current_user.role != models.UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can raise complaint tickets."
        )

    student = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found."
        )

    new_complaint = models.Complaint(
        student_id=student.id,
        title=complaint_in.title,
        description=complaint_in.description,
        category=complaint_in.category,
        status=models.ComplaintLifecycleStatus.Pending
    )
    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)
    return new_complaint


@router.post("/{complaint_id}/assign", response_model=schemas.ComplaintOut)
def assign_complaint(complaint_id: int, req: schemas.ComplaintAssign, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    Warden assigns the complaint to a maintenance worker.
    """
    if current_user.role not in [models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only wardens or admins can assign complaints."
        )

    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found."
        )

    complaint.assigned_to = req.assigned_to
    complaint.status = models.ComplaintLifecycleStatus.Assigned
    db.commit()
    db.refresh(complaint)
    return complaint


@router.post("/{complaint_id}/resolve", response_model=schemas.ComplaintOut)
def resolve_complaint(complaint_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    Mark complaint as resolved (Warden or Super Admin).
    """
    if current_user.role not in [models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only wardens or admins can resolve complaints."
        )

    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found."
        )

    complaint.status = models.ComplaintLifecycleStatus.Resolved
    complaint.resolved_at = datetime.now()
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get("", response_model=List[schemas.ComplaintOut])
def list_complaints(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    List complaints. Students see their own; Wardens/Admins see all.
    """
    if current_user.role == models.UserRole.STUDENT:
        student = db.query(models.Student).filter(models.Student.user_id == current_user.id).first()
        if not student:
            return []
        return db.query(models.Complaint).filter(models.Complaint.student_id == student.id).all()
    else:
        return db.query(models.Complaint).all()
