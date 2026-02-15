"""
Leave schemas
"""
from datetime import date, datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, model_validator, field_serializer
from pydantic import ConfigDict
from app.utils.datetime_utils import iso_ist
from decimal import Decimal
from app.models.leave import LeaveType, LeaveStatus
from app.schemas.employee import EmployeeOut


class LeaveApplyRequest(BaseModel):
    """Schema for applying leave"""
    leave_type: LeaveType = Field(..., description="Type of leave")
    from_date: date = Field(..., description="Start date of leave")
    to_date: date = Field(..., description="End date of leave")
    reason: Optional[str] = Field(None, description="Reason for leave")
    override_policy: bool = Field(False, description="Override policy rules (HR only)")
    override_remark: Optional[str] = Field(None, description="Remark for override (required if override_policy is True)")


class ApprovalActionRequest(BaseModel):
    """Schema for leave approval request"""
    remarks: Optional[str] = Field(None, description="Optional remarks for approval")


class RejectActionRequest(BaseModel):
    """Schema for leave rejection request"""
    remarks: str = Field(..., description="Remarks for rejection")


class LeaveOut(BaseModel):
    """Schema for leave output (includes remarks and actor info for Flutter/Admin)"""
    id: int
    employee_id: int
    employee: Optional[EmployeeOut] = None
    leave_type: LeaveType
    from_date: date
    to_date: date
    reason: Optional[str]
    status: LeaveStatus
    computed_days: Decimal
    paid_days: Decimal
    lwp_days: Decimal
    override_policy: bool
    override_remark: Optional[str]
    auto_converted_to_lwp: bool
    auto_lwp_reason: Optional[str]
    applied_at: datetime
    created_at: datetime
    updated_at: datetime
    approver_id: Optional[int] = Field(None, description="ID of the approver")
    approver: Optional[EmployeeOut] = Field(None, description="Approver details")
    approved_remark: Optional[str] = Field(None, description="Remarks on approval")
    approved_at: Optional[datetime] = Field(None, description="When the leave was approved")
    rejected_remark: Optional[str] = Field(None, description="Remarks on rejection")
    rejected_by_id: Optional[int] = Field(None, description="ID of the rejector")
    rejected_at: Optional[datetime] = Field(None, description="When the leave was rejected")
    rejected_by: Optional[EmployeeOut] = Field(None, description="Rejector details")
    cancelled_remark: Optional[str] = Field(None, description="Remarks on cancellation")
    cancelled_by_id: Optional[int] = Field(None, description="ID of the canceller")
    cancelled_at: Optional[datetime] = Field(None, description="When the leave was cancelled")
    cancelled_by: Optional[EmployeeOut] = Field(None, description="Canceller details")
    # Alias for Flutter: same value as cancelled_remark
    cancel_remark: Optional[str] = Field(None, description="Same as cancelled_remark (for mobile)")

    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "applied_at", "created_at", "updated_at", "approved_at", "rejected_at", "cancelled_at",
        when_used="always",
    )
    @classmethod
    def _ser_datetime(cls, dt: Optional[datetime]) -> Optional[str]:
        return iso_ist(dt) if dt is not None else None

    @model_validator(mode="after")
    def set_cancel_remark_alias(self) -> "LeaveOut":
        if getattr(self, "cancel_remark", None) is None and getattr(self, "cancelled_remark", None) is not None:
            self.cancel_remark = self.cancelled_remark
        return self


class LeaveListItemOut(BaseModel):
    """Schema for leave list item output (same as LeaveOut)"""
    id: int
    employee_id: int
    employee: Optional[EmployeeOut] = None
    leave_type: LeaveType
    from_date: date
    to_date: date
    reason: Optional[str]
    status: LeaveStatus
    computed_days: Decimal
    paid_days: Decimal
    lwp_days: Decimal
    override_policy: bool
    override_remark: Optional[str]
    auto_converted_to_lwp: bool
    auto_lwp_reason: Optional[str]
    applied_at: datetime
    created_at: datetime
    updated_at: datetime
    approver_id: Optional[int] = Field(None, description="ID of the approver")
    approver: Optional[EmployeeOut] = Field(None, description="Approver details")
    approved_remark: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_remark: Optional[str] = None
    rejected_by_id: Optional[int] = None
    rejected_at: Optional[datetime] = None
    rejected_by: Optional[EmployeeOut] = None
    cancelled_remark: Optional[str] = None
    cancelled_by_id: Optional[int] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[EmployeeOut] = None
    cancel_remark: Optional[str] = None  # alias for cancelled_remark (for mobile)

    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "applied_at", "created_at", "updated_at", "approved_at", "rejected_at", "cancelled_at",
        when_used="always",
    )
    @classmethod
    def _ser_datetime(cls, dt: Optional[datetime]) -> Optional[str]:
        return iso_ist(dt) if dt is not None else None

    @model_validator(mode="after")
    def set_cancel_remark_alias(self) -> "LeaveListItemOut":
        if getattr(self, "cancel_remark", None) is None and getattr(self, "cancelled_remark", None) is not None:
            self.cancel_remark = self.cancelled_remark
        return self


class LeaveListResponse(BaseModel):
    """Schema for leave list response"""
    items: List[LeaveListItemOut]
    total: int


# --- Leave balance (wallet) ---


class BalanceItemOut(BaseModel):
    """One leave type balance for API."""
    leave_type: LeaveType
    total_entitlement: float
    opening: float
    accrued: float
    used: float
    remaining: float
    eligible: bool = True
    notes: Optional[str] = None


class BalanceTypeOut(BaseModel):
    """Per-type: entitled (=allocated), used, available (=remaining). For mobile and dashboard."""
    allocated: float
    used: float
    remaining: float
    entitled: float  # same as allocated
    available: float  # same as remaining


class BalanceMeResponse(BaseModel):
    """GET /leaves/balance/me response. items + employee_id + balances (PL/CL/SL/RH)."""
    year: int
    employee_id: int
    items: List[BalanceItemOut]
    balances: Optional[Dict[str, BalanceTypeOut]] = None  # e.g. {"PL": {allocated, used, remaining}}


class BalanceSummaryItemOut(BaseModel):
    """Shorter summary item."""
    leave_type: LeaveType
    remaining: float
    used: float
    eligible: bool = True


class BalanceSummaryMeResponse(BaseModel):
    """GET /leaves/balance/summary/me response."""
    year: int
    items: List[BalanceSummaryItemOut]


class AdminBalanceItemOut(BaseModel):
    """Admin balance row (includes employee info). allocated = opening + accrued + carry_forward."""
    employee_id: int
    employee_name: Optional[str] = None
    department_name: Optional[str] = None
    emp_code: Optional[str] = None
    leave_type: LeaveType
    allocated: float
    opening: float
    accrued: float
    used: float
    remaining: float
    eligible: bool = True


class AdminBalancesResponse(BaseModel):
    """GET /admin/leaves/balances response."""
    year: int
    items: List[AdminBalanceItemOut]
    total: int


class LeaveTransactionOut(BaseModel):
    """Single transaction for audit. Datetimes in IST (+05:30)."""
    id: int
    employee_id: int
    leave_id: Optional[int]
    year: int
    leave_type: LeaveType
    delta_days: Decimal
    action: str
    remarks: Optional[str]
    action_by_employee_id: Optional[int]
    action_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("action_at", when_used="always")
    @classmethod
    def _ser_action_at(cls, dt: datetime) -> str:
        return iso_ist(dt) or ""
