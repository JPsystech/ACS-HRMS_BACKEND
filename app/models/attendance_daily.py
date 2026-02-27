from sqlalchemy import Column, Integer, Date, DateTime, Boolean, PrimaryKeyConstraint, Index
from sqlalchemy.sql import func
from app.db.base import Base


class AttendanceDaily(Base):
    __tablename__ = "attendance_daily"

    user_id = Column(Integer, nullable=False)
    work_date = Column(Date, nullable=False)
    first_in_time = Column(DateTime(timezone=True), nullable=True)
    is_good = Column(Boolean, nullable=False, default=False)
    computed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "work_date", name="pk_attendance_daily"),
        Index("ix_attendance_daily_user_date", "user_id", "work_date"),
    )
