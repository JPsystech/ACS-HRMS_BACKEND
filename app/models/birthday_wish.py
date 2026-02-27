from sqlalchemy import Column, Integer, Text, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class BirthdayWish(Base):
    __tablename__ = "birthday_wishes"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    reply_message = Column(Text, nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    employee = relationship("Employee", foreign_keys=[employee_id])
    sender = relationship("Employee", foreign_keys=[sender_id])
