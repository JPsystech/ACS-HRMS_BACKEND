from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, text, Index
from sqlalchemy.orm import relationship
from app.db.base import Base


class NotificationDevice(Base):
    __tablename__ = "notification_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    fcm_token = Column(String(512), unique=True, nullable=False, index=True)
    platform = Column(String(32), nullable=False)
    app_version = Column(String(64), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    user = relationship("Employee")

    __table_args__ = (
        Index("ix_notification_devices_user_id", "user_id"),
    )
