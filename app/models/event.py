"""
Company event model
"""
from sqlalchemy import Column, Integer, Date, String, Boolean, DateTime, UniqueConstraint, Text
from sqlalchemy.sql import func
from app.db.base import Base


class CompanyEvent(Base):
    __tablename__ = "company_events"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    description = Column(Text, nullable=True)
    image_key = Column(String(500), nullable=True)
    image_url = Column(String(500), nullable=True)
    location = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), onupdate=func.current_timestamp(), nullable=False)

    __table_args__ = (
        UniqueConstraint('year', 'date', name='uq_event_year_date'),
    )
