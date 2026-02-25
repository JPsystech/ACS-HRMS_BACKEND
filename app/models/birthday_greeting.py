from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base import Base

class BirthdayGreeting(Base):
    __tablename__ = "birthday_greetings"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    greeting_image_url = Column(Text, nullable=True)
    greeting_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    wish_sent_at = Column(DateTime(timezone=True), nullable=True)
    wish_sent_by = Column(Integer, ForeignKey("employees.id"), nullable=True)
    wish_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)
    __table_args__ = (UniqueConstraint("employee_id", "date", name="uq_birthday_employee_date"),)
    employee = relationship("Employee", foreign_keys=[employee_id])
    wished_by = relationship("Employee", foreign_keys=[wish_sent_by], uselist=False)
    created_by_user = relationship("Employee", foreign_keys=[created_by], uselist=False)
