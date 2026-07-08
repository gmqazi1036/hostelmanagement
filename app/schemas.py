from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import Optional, List
import re
from app.models import UserRole, StudentLifecycleStatus, LeaveRecordStatus, MessAttendanceStatus, InvoicePaymentStatus, ComplaintLifecycleStatus, AssetConditionType

# --- User & Auth Schemas ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: UserRole

class UserLogin(UserBase):
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None

class UserOut(UserBase):
    id: int
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

# --- Student Schemas ---
class StudentBase(BaseModel):
    student_id: str = Field(..., description="4-digit numeric student ID")
    name: str
    father_name: str
    class_course: str
    contact_number: str

    @field_validator("student_id")
    @classmethod
    def validate_student_id(cls, v: str) -> str:
        if not re.match(r"^\d{4}$", v):
            raise ValueError("Student ID must be exactly 4 digits numeric only.")
        return v

class StudentCreate(StudentBase):
    username: Optional[str] = None
    password: Optional[str] = None

class StudentUpdate(BaseModel):
    name: Optional[str] = None
    father_name: Optional[str] = None
    class_course: Optional[str] = None
    contact_number: Optional[str] = None
    status: Optional[StudentLifecycleStatus] = None

class StudentOut(StudentBase):
    status: StudentLifecycleStatus
    user_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

# --- Allotment & Room Schemas ---
class BedSwapRequest(BaseModel):
    student_x_id: str = Field(..., description="4-digit numeric ID of student X")
    student_y_id: str = Field(..., description="4-digit numeric ID of student Y")

    @field_validator("student_x_id", "student_y_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        if not re.match(r"^\d{4}$", v):
            raise ValueError("Student ID must be exactly 4 digits numeric only.")
        return v

class RoomTransferRequest(BaseModel):
    student_id: str = Field(..., description="4-digit numeric student ID")
    target_bed_id: int

    @field_validator("student_id")
    @classmethod
    def validate_student_id(cls, v: str) -> str:
        if not re.match(r"^\d{4}$", v):
            raise ValueError("Student ID must be exactly 4 digits numeric only.")
        return v

class AllotmentOut(BaseModel):
    id: int
    student: StudentOut
    hostel_name: str
    floor_no: int
    room_no: str
    bed_no: str
    allotment_date: date
    vacated_date: Optional[date]

    class Config:
        from_attributes = True

# --- Leave & Gate Pass Schemas ---
class LeaveApply(BaseModel):
    start_date: date
    end_date: date
    reason: str

class LeaveApprove(BaseModel):
    status: LeaveRecordStatus = Field(..., description="Approved or Rejected")

class LeaveOut(BaseModel):
    id: int
    student_id: str
    start_date: date
    end_date: date
    reason: str
    status: LeaveRecordStatus
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# --- Visitor Schemas ---
class VisitorCreate(BaseModel):
    student_id: str = Field(..., description="4-digit numeric student ID")
    visitor_name: str
    relationship: str
    contact_number: str
    purpose: Optional[str] = None

    @field_validator("student_id")
    @classmethod
    def validate_student_id(cls, v: str) -> str:
        if not re.match(r"^\d{4}$", v):
            raise ValueError("Student ID must be exactly 4 digits numeric only.")
        return v

class VisitorOut(VisitorCreate):
    id: int
    entry_time: datetime
    exit_time: Optional[datetime]

    class Config:
        from_attributes = True

# --- Complaint Schemas ---
class ComplaintCreate(BaseModel):
    title: str
    description: str
    category: str

class ComplaintAssign(BaseModel):
    assigned_to: str

class ComplaintOut(BaseModel):
    id: int
    student_id: str
    title: str
    description: str
    category: str
    status: ComplaintLifecycleStatus
    assigned_to: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

# --- Asset Schemas ---
class AssetAuditRequest(BaseModel):
    student_asset_id: int
    condition: AssetConditionType

class StudentAssetOut(BaseModel):
    id: int
    allotment_id: int
    asset_name: str
    serial_no: Optional[str]
    condition: AssetConditionType

    class Config:
        from_attributes = True

# --- Invoice Schemas ---
class InvoiceOut(BaseModel):
    id: int
    student_id: str
    billing_month: date
    base_amount: float
    rebate_amount: float
    net_amount: float
    status: InvoicePaymentStatus
    created_at: datetime

    class Config:
        from_attributes = True
