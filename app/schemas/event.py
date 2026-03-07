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
    image_key: str | None = None
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

    @model_validator(mode="after")
    def set_dynamic_image_url(self) -> "CompanyEventOut":
        """Generate dynamic R2 pre-signed URL if image_key is present"""
        if self.image_key:
            try:
                from app.services.r2_storage import get_r2_storage_service
                from app.core.config import settings
                
                # 1. Try pre-signed URL (preferred for R2)
                r2_service = get_r2_storage_service()
                presigned_url = r2_service.get_presigned_url(self.image_key)
                if presigned_url:
                    self.image_url = presigned_url
                    return self
            except Exception:
                pass
            
            # 2. Fallback to proxy URL
            try:
                from app.core.config import settings
                base = settings.PUBLIC_BASE_URL.rstrip("/")
                self.image_url = f"{base}/api/v1/events/image/{self.image_key}"
            except Exception:
                pass
        return self
