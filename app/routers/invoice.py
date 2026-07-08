from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, auth
from typing import List

router = APIRouter(
    prefix="/api/invoices",
    tags=["Billing & Invoices"]
)

warden_dependency = Depends(auth.RoleChecker([
    models.UserRole.WARDEN, models.UserRole.SUPER_ADMIN
]))

@router.get("/my", response_model=List[schemas.InvoiceOut])
def get_my_invoices(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    Get invoices for the logged-in student.
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

    return db.query(models.Invoice).filter(models.Invoice.student_id == student.student_id).order_by(models.Invoice.billing_month.desc()).all()


@router.get("", response_model=List[schemas.InvoiceOut], dependencies=[warden_dependency])
def list_all_invoices(db: Session = Depends(get_db)):
    """
    Get all invoices (Wardens/Admins only).
    """
    return db.query(models.Invoice).order_by(models.Invoice.billing_month.desc()).all()


@router.post("/{invoice_id}/pay", response_model=schemas.InvoiceOut, dependencies=[warden_dependency])
def mark_invoice_as_paid(invoice_id: int, db: Session = Depends(get_db)):
    """
    Mark a student's invoice as Paid (Warden only).
    """
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found."
        )

    if invoice.status == models.InvoicePaymentStatus.Paid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice is already paid."
        )

    invoice.status = models.InvoicePaymentStatus.Paid
    db.commit()
    db.refresh(invoice)
    return invoice
