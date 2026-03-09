"""
Holiday calendar schemas
"""
from datetime import date as date_type, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer, model_validator, ConfigDict
from typing import Optional
from app.utils.url_utils import build_api_image_url


class HolidayCreate(BaseModel):
    """Schema for creating a holiday"""
    year: int = Field(..., description="Year (e.g., 2026)")
    date: date_type = Field(..., description="Holiday date")
    name: str = Field(..., description="Holiday name")
    active: bool = Field(True, description="Whether the holiday is active")
    description: Optional[str] = Field(None, description="Description / Notes")


class HolidayUpdate(BaseModel):
    """Schema for updating a holiday"""
    name: Optional[str] = Field(None, description="Holiday name")
    active: Optional[bool] = Field(None, description="Whether the holiday is active")
    description: Optional[str] = Field(None, description="Description / Notes")


class HolidayOut(BaseModel):
    """Schema for holiday output. Datetimes in IST (+05:30)."""
    id: int
    year: int
    date: date_type
    name: str
    active: bool
    description: Optional[str] = None
    image_key: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None

    @model_validator(mode="after")
    def set_image_url(self) -> "HolidayOut":
        if self.image_key:
            try:
                self.image_url = build_api_image_url("holidays", self.image_key)
            except Exception:
                self.image_url = None
        else:
            self.image_url = None
        return self


class RHCreate(BaseModel):
    """Schema for creating a restricted holiday"""
    year: int = Field(..., description="Year (e.g., 2026)")
    date: date_type = Field(..., description="Restricted holiday date")
    name: str = Field(..., description="Restricted holiday name")
    active: bool = Field(True, description="Whether the restricted holiday is active")
    description: Optional[str] = Field(None, description="Description / Notes")


class RHUpdate(BaseModel):
    """Schema for updating a restricted holiday"""
    name: Optional[str] = Field(None, description="Restricted holiday name")
    active: Optional[bool] = Field(None, description="Whether the restricted holiday is active")
    description: Optional[str] = Field(None, description="Description / Notes")


class RHOut(BaseModel):
    """Schema for restricted holiday output. Datetimes in IST (+05:30)."""
    id: int
    year: int
    date: date_type
    name: str
    active: bool
    description: Optional[str] = None
    image_key: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None

    @model_validator(mode="after")
    def set_image_url(self) -> "RHOut":
        if self.image_key:
            try:
                self.image_url = build_api_image_url("holidays", self.image_key)
            except Exception:
                self.image_url = None
        else:
            self.image_url = None
        return self
