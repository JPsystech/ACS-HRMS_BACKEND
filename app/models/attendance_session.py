"""
Attendance session and event models (punch in/out with sessions and immutable event log).
"""
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, String, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base


class SessionStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    AUTO_CLOSED = "AUTO_CLOSED"
    SUSPICIOUS = "SUSPICIOUS"  # e.g. punch with is_mocked=True when REJECT_MOCK_LOCATION_PUNCH=False


class AttendanceEventType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"
    ADMIN_EDIT = "ADMIN_EDIT"
    AUTO_OUT = "AUTO_OUT"


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)  # Asia/Kolkata date
    punch_in_at = Column(DateTime(timezone=True), nullable=False)
    punch_out_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(SQLEnum(SessionStatus), nullable=False, default=SessionStatus.OPEN)
    punch_in_source = Column(String, nullable=False, default="WEB")  # MOBILE/WEB/ADMIN
    punch_out_source = Column(String, nullable=True)
    punch_in_ip = Column(String, nullable=True)
    punch_out_ip = Column(String, nullable=True)
    punch_in_device_id = Column(String, nullable=True)
    punch_out_device_id = Column(String, nullable=True)
    punch_in_geo = Column(JSON, nullable=True)
    punch_out_geo = Column(JSON, nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    employee = relationship("Employee", backref="attendance_sessions")
    events = relationship("AttendanceEvent", back_populates="session", order_by="AttendanceEvent.event_at")


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    event_type = Column(SQLEnum(AttendanceEventType), nullable=False)  # IN/OUT/ADMIN_EDIT/AUTO_OUT
    event_at = Column(DateTime(timezone=True), nullable=False)
    meta_json = Column(JSON, nullable=True)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)

    session = relationship("AttendanceSession", back_populates="events")
    employee = relationship("Employee", foreign_keys=[employee_id])
    created_by_employee = relationship("Employee", foreign_keys=[created_by])
