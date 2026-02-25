"""
Attendance log model
"""
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, String, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    punch_date = Column(Date, nullable=False, index=True)  # Server date (UTC) - derived from server "today"
    in_time = Column(DateTime(timezone=True), nullable=False)  # Server UTC timestamp
    in_lat = Column(Numeric(10, 8), nullable=False)  # GPS latitude
    in_lng = Column(Numeric(11, 8), nullable=False)  # GPS longitude
    out_time = Column(DateTime(timezone=True), nullable=True)  # Server UTC timestamp (for Day 5)
    out_lat = Column(Numeric(10, 8), nullable=True)  # GPS latitude (for Day 5)
    out_lng = Column(Numeric(11, 8), nullable=True)  # GPS longitude (for Day 5)
    source = Column(String, default="mobile", nullable=False)  # e.g., "mobile", "web"
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    __table_args__ = (
        UniqueConstraint('employee_id', 'punch_date', name='uq_employee_punch_date'),
    )

    # Relationships
    employee = relationship("Employee", backref="attendance_logs")
