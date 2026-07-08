from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, Numeric, Enum as SqlEnum, func, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship as orm_relationship
from app.database import Base
import enum

# Define Python Enums matching DB types
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    WARDEN = "WARDEN"
    GATE_GUARD = "GATE_GUARD"
    STUDENT = "STUDENT"

class StudentLifecycleStatus(str, enum.Enum):
    Active = "Active"
    Suspended = "Suspended"
    Left = "Left"
    Graduated = "Graduated"

class LeaveRecordStatus(str, enum.Enum):
    Pending = "Pending"
    Approved = "Approved"
    Rejected = "Rejected"

class MessAttendanceStatus(str, enum.Enum):
    ON = "ON"
    OFF = "OFF"
    SUSPENDED = "SUSPENDED"

class InvoicePaymentStatus(str, enum.Enum):
    Unpaid = "Unpaid"
    Paid = "Paid"

class ComplaintLifecycleStatus(str, enum.Enum):
    Pending = "Pending"
    Assigned = "Assigned"
    Resolved = "Resolved"

class AssetConditionType(str, enum.Enum):
    Good = "Good"
    Damaged = "Damaged"
    Lost = "Lost"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SqlEnum(UserRole, name="user_role", inherit_schema=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = orm_relationship("Student", back_populates="user", uselist=False)


class Student(Base):
    __tablename__ = "students"
    
    # student_id is the primary key (4-digit numeric only)
    student_id = Column(String(4), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True)
    name = Column(String(100), nullable=False)
    father_name = Column(String(100), nullable=False)
    class_course = Column(String(100), nullable=False)
    contact_number = Column(String(20), nullable=False)
    status = Column(SqlEnum(StudentLifecycleStatus, name="student_status", inherit_schema=True), nullable=False, default=StudentLifecycleStatus.Active)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = orm_relationship("User", back_populates="student")
    allotments = orm_relationship("AllotmentHistory", back_populates="student")
    leaves = orm_relationship("LeaveRecord", back_populates="student")
    mess_records = orm_relationship("MessAttendance", back_populates="student")
    invoices = orm_relationship("Invoice", back_populates="student")
    complaints = orm_relationship("Complaint", back_populates="student")
    visitor_logs = orm_relationship("Visitor", back_populates="student")


class AcademicSession(Base):
    __tablename__ = "academic_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_name = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    allotments = orm_relationship("AllotmentHistory", back_populates="session")


class Hostel(Base):
    __tablename__ = "hostels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rooms = orm_relationship("Room", back_populates="hostel")


class Room(Base):
    __tablename__ = "rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    hostel_id = Column(Integer, ForeignKey("hostels.id", ondelete="CASCADE"), nullable=False)
    floor_no = Column(Integer, nullable=False)
    room_no = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('hostel_id', 'room_no', name='uq_hostel_room'),)

    hostel = orm_relationship("Hostel", back_populates="rooms")
    beds = orm_relationship("Bed", back_populates="room")


class Bed(Base):
    __tablename__ = "beds"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    bed_no = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('room_id', 'bed_no', name='uq_room_bed'),)

    room = orm_relationship("Room", back_populates="beds")
    allotments = orm_relationship("AllotmentHistory", back_populates="bed")


class AllotmentHistory(Base):
    __tablename__ = "allotment_history"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(4), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    bed_id = Column(Integer, ForeignKey("beds.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False)
    allotment_date = Column(Date, nullable=False, server_default=func.current_date())
    vacated_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint('vacated_date IS NULL OR vacated_date >= allotment_date', name='chk_vacated_date'),
    )

    student = orm_relationship("Student", back_populates="allotments")
    bed = orm_relationship("Bed", back_populates="allotments")
    session = orm_relationship("AcademicSession", back_populates="allotments")
    allocated_assets = orm_relationship("StudentAsset", back_populates="allotment")


class LeaveRecord(Base):
    __tablename__ = "leave_records"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(4), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(SqlEnum(LeaveRecordStatus, name="leave_status", inherit_schema=True), nullable=False, default=LeaveRecordStatus.Pending)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint('end_date >= start_date', name='chk_leave_dates'),
    )

    student = orm_relationship("Student", back_populates="leaves")


class MessAttendance(Base):
    __tablename__ = "mess_attendance"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(4), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(SqlEnum(MessAttendanceStatus, name="mess_status", inherit_schema=True), nullable=False, default=MessAttendanceStatus.ON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('student_id', 'date', name='uq_student_date_attendance'),)

    student = orm_relationship("Student", back_populates="mess_records")


class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(4), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    billing_month = Column(Date, nullable=False) # Represents first day of billing month
    base_amount = Column(Numeric(10, 2), nullable=False, default=5000.00)
    rebate_amount = Column(Numeric(10, 2), nullable=False, default=0.00)
    status = Column(SqlEnum(InvoicePaymentStatus, name="invoice_status", inherit_schema=True), nullable=False, default=InvoicePaymentStatus.Unpaid)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('student_id', 'billing_month', name='uq_student_month'),)

    student = orm_relationship("Student", back_populates="invoices")


class Complaint(Base):
    __tablename__ = "complaints"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(4), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(150), nullable=False)
    description = Column(String, nullable=False)
    category = Column(String(50), nullable=False)
    status = Column(SqlEnum(ComplaintLifecycleStatus, name="complaint_status", inherit_schema=True), nullable=False, default=ComplaintLifecycleStatus.Pending)
    assigned_to = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = orm_relationship("Student", back_populates="complaints")


class Visitor(Base):
    __tablename__ = "visitors"
    
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String(4), ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False)
    visitor_name = Column(String(100), nullable=False)
    relationship = Column(String(50), nullable=False)
    contact_number = Column(String(20), nullable=False)
    entry_time = Column(DateTime(timezone=True), server_default=func.now())
    exit_time = Column(DateTime(timezone=True), nullable=True)
    purpose = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = orm_relationship("Student", back_populates="visitor_logs")


class Asset(Base):
    __tablename__ = "assets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    student_assets = orm_relationship("StudentAsset", back_populates="asset")


class StudentAsset(Base):
    __tablename__ = "student_assets"
    
    id = Column(Integer, primary_key=True, index=True)
    allotment_id = Column(Integer, ForeignKey("allotment_history.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    serial_no = Column(String(100), nullable=True)
    condition = Column(SqlEnum(AssetConditionType, name="asset_condition", inherit_schema=True), nullable=False, default=AssetConditionType.Good)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint('allotment_id', 'asset_id', name='uq_allotment_asset'),)

    allotment = orm_relationship("AllotmentHistory", back_populates="allocated_assets")
    asset = orm_relationship("Asset", back_populates="student_assets")
