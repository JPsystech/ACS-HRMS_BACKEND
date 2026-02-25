"""
Comp-off schemas
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer, ConfigDict
from decimal import Decimal
from app.models.compoff import CompoffRequestStatus


class CompoffEarnRequest(BaseModel):
    """Schema for requesting comp-off earn"""
    worked_date: date = Field(..., description="Date on which employee worked (Sunday or holiday)")
    reason: Optional[str] = Field(None, description="Reason for comp-off request")


class CompoffRequestOut(BaseModel):
    """Schema for comp-off request output. Datetimes in IST (+05:30)."""
    id: int
    employee_id: int
    worked_date: date
    status: CompoffRequestStatus
    reason: Optional[str]
    requested_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("requested_at", "created_at", "updated_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None


class CompoffActionRequest(BaseModel):
    """Schema for comp-off approve/reject request"""
    remarks: Optional[str] = Field(None, description="Optional remarks for approval/rejection")


class CompoffBalanceOut(BaseModel):
    """Schema for comp-off balance output"""
    employee_id: int
    available_days: float = Field(..., description="Available comp-off days (credits - debits, excluding expired)")
    credits: float = Field(..., description="Total credits (not expired)")
    debits: float = Field(..., description="Total debits")
    expired_credits: float = Field(0.0, description="Expired credits (for reference)")


class CompoffListResponse(BaseModel):
    """Schema for comp-off list response"""
    items: List[CompoffRequestOut]
    total: int
