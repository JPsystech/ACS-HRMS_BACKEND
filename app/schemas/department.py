"""
Department schemas
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_serializer, ConfigDict


class DepartmentCreate(BaseModel):
    """Schema for creating a department"""
    name: str = Field(..., description="Department name")
    active: bool = Field(default=True, description="Department active status")


class DepartmentUpdate(BaseModel):
    """Schema for updating a department"""
    name: Optional[str] = Field(None, description="Department name")
    active: Optional[bool] = Field(None, description="Department active status")


class DepartmentOut(BaseModel):
    """Schema for department output. Datetimes in IST (+05:30)."""
    id: int
    name: str
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None
