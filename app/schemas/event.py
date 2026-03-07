"""
Company event schemas
"""
from datetime import date as date_type, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_serializer, ConfigDict


class CompanyEventCreate(BaseModel):
    """Schema for creating company event"""
    year: int = Field(..., description="Calendar year")
    date: date_type = Field(..., description="Event date")
    name: str = Field(..., min_length=1, max_length=255, description="Event name")
    active: bool = Field(True, description="Whether event is active")
    description: str | None = Field(None, description="Event description")
    image_url: str | None = Field(None, description="Event image URL")
    location: str | None = Field(None, description="Event location")


class CompanyEventUpdate(BaseModel):
    """Schema for updating company event"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    active: Optional[bool] = None
    description: str | None = Field(None)
    image_url: str | None = Field(None)
    location: str | None = Field(None)


class CompanyEventOut(BaseModel):
    """Schema for company event output. Datetimes in IST (+05:30)."""
    id: int
    year: int
    date: date_type
    name: str
    active: bool
    description: str | None = None
    image_url: str | None = None
    location: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None
