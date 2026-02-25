"""
WFH (Work From Home) request model
"""
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, String, Text, Numeric, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base


class WFHStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class WFHRequest(Base):
    __tablename__ = "wfh_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    request_date = Column(Date, nullable=False, index=True)
    reason = Column(Text, nullable=True)
    status = Column(SQLEnum(WFHStatus), nullable=False, server_default=func.text("'PENDING'"))
    day_value = Column(Numeric(5, 2), nullable=False, default=0.5)  # Default 0.5 day from policy
    applied_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    approved_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], backref="wfh_requests")
    approver = relationship("Employee", foreign_keys=[approved_by])

    __table_args__ = (
        UniqueConstraint('employee_id', 'request_date', name='uq_wfh_employee_date'),
    )
