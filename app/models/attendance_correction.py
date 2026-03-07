from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, String, Text, Enum as SQLEnum
from sqlalchemy.sql import func
import enum
from app.db.base import Base


class CorrectionRequestType(str, enum.Enum):
    FORGOT_PUNCH_IN = "FORGOT_PUNCH_IN"
    FORGOT_PUNCH_OUT = "FORGOT_PUNCH_OUT"
    CORRECTION = "CORRECTION"


class CorrectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AttendanceCorrectionRequest(Base):
    __tablename__ = "attendance_correction_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    request_type = Column(SQLEnum(CorrectionRequestType), nullable=False)
    date = Column(Date, nullable=False, index=True)
    requested_punch_in = Column(DateTime(timezone=True), nullable=True)
    requested_punch_out = Column(DateTime(timezone=True), nullable=True)
    reason = Column(Text, nullable=False)
    remarks = Column(Text, nullable=True)
    status = Column(SQLEnum(CorrectionStatus), nullable=False, default=CorrectionStatus.PENDING, index=True)
    approved_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    admin_remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
