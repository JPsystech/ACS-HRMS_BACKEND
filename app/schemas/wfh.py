"""
WFH (Work From Home) schemas
"""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer, ConfigDict
from decimal import Decimal
from app.models.wfh import WFHStatus


class WFHApplyRequest(BaseModel):
    """Schema for applying WFH"""
    request_date: date = Field(..., description="WFH date")
    reason: Optional[str] = Field(None, description="Optional reason")


class WFHRequestOut(BaseModel):
    """Schema for WFH request output. Datetimes in IST (+05:30)."""
    id: int
    employee_id: int
    request_date: date
    reason: Optional[str]
    status: WFHStatus
    day_value: Decimal
    applied_at: datetime
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("applied_at", "approved_at", "created_at", "updated_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None


class WFHActionRequest(BaseModel):
    """Schema for approve/reject WFH"""
    remarks: Optional[str] = Field(None, description="Optional remarks")


class WFHListResponse(BaseModel):
    """Schema for WFH list response"""
    items: list[WFHRequestOut]
    total: int


class AdminWfhBalanceItem(BaseModel):
    """Admin view of per-employee WFH usage for a year."""
    employee_id: int
    employee_name: Optional[str]
    department_name: Optional[str]
    emp_code: Optional[str]
    entitled: int
    accrued: int
    used: int
    remaining: int


class AdminWfhBalancesResponse(BaseModel):
    """Response for admin WFH balances list."""
    year: int
    items: List[AdminWfhBalanceItem]
    total: int


class AdminWfhTransactionOut(BaseModel):
    """Admin WFH 'transaction' entry for balances drawer."""
    id: int
    employee_id: int
    date: date
    day_value: Decimal
    action: str
    remarks: Optional[str]
    action_by_employee_id: Optional[int]
    action_at: datetime

    @field_serializer("action_at", when_used="always")
    @classmethod
    def _ser_action_at(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None


class WFHBalanceMeOut(BaseModel):
    """Simple WFH balance summary for employee dashboard."""
    year: int
    entitled: int
    accrued: int
    used: int
    remaining: int
