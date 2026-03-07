from sqlalchemy import Column, Integer, Date, DateTime, String, Boolean, ForeignKey, Enum as SQLEnum, Index, text
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base


class ReminderType(str, enum.Enum):
    PUNCH_IN_REMINDER = "PUNCH_IN_REMINDER"
    PUNCH_OUT_REMINDER = "PUNCH_OUT_REMINDER"


class DeliveryStatus(str, enum.Enum):
    SENT = "SENT"
    FAILED = "FAILED"


class NotificationReminder(Base):
    __tablename__ = "notification_reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    reminder_date = Column(Date, nullable=False, index=True)  # IST date
    reminder_type = Column(SQLEnum(ReminderType), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(String(500), nullable=False)
    delivery_status = Column(SQLEnum(DeliveryStatus), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    user = relationship("Employee")

    __table_args__ = (
        Index("ix_reminder_unique_user_date_type", "user_id", "reminder_date", "reminder_type", unique=True),
    )
