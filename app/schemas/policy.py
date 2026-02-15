"""
Policy settings schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_serializer, model_validator, ConfigDict
from decimal import Decimal


class PolicyOut(BaseModel):
    """Schema for policy settings output. Datetimes in IST (+05:30). Includes rules for validation."""
    id: int
    year: int
    rules: Optional[Dict[str, Any]] = None
    # Annual entitlements (ACS: PL=7, SL=6, CL=5, RH=1)
    annual_pl: int
    annual_cl: int
    annual_sl: int
    annual_rh: int
    public_holiday_total: Optional[int] = None  # Display only; not deducted from balance
    # Monthly credits
    monthly_credit_pl: Decimal
    monthly_credit_cl: Decimal
    monthly_credit_sl: Decimal
    # PL eligibility
    pl_eligibility_months: int
    # Backdated leave
    backdated_max_days: int
    # Carry forward / encashment
    carry_forward_pl_max: int
    # WFH policy
    wfh_max_days: int
    wfh_day_value: Decimal
    # Old rules (kept for backward compatibility)
    probation_months: int  # DEPRECATED
    cl_pl_notice_days: int
    cl_pl_monthly_cap: Decimal
    enforce_monthly_cap: bool
    enforce_notice_days: bool
    notice_days_cl_pl: int
    # Sick intimation
    enforce_sick_intimation: bool
    sick_intimation_min_minutes: int
    # Sandwich rule
    weekly_off_day: int
    sandwich_enabled: bool
    sandwich_include_weekly_off: bool
    sandwich_include_holidays: bool
    sandwich_include_rh: bool
    treat_event_as_non_working_for_sandwich: bool
    # HR override
    allow_hr_override: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def set_rules(self) -> "PolicyOut":
        """Expose key rule values for clients (backdate_limit_days, pl_min_service_months, carry_forward_pl_max)."""
        if getattr(self, "rules", None) is None:
            self.rules = {
                "backdate_limit_days": getattr(self, "backdated_max_days", 7),
                "pl_min_service_months": getattr(self, "pl_eligibility_months", 6),
                "carry_forward_pl_max": getattr(self, "carry_forward_pl_max", 4),
            }
        return self

    @field_serializer("created_at", "updated_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None


class PolicyUpdate(BaseModel):
    """Schema for updating policy settings"""
    # Annual entitlements
    annual_pl: Optional[int] = None
    annual_cl: Optional[int] = None
    annual_sl: Optional[int] = None
    annual_rh: Optional[int] = None
    public_holiday_total: Optional[int] = None
    # Monthly credits
    monthly_credit_pl: Optional[Decimal] = None
    monthly_credit_cl: Optional[Decimal] = None
    monthly_credit_sl: Optional[Decimal] = None
    # PL eligibility
    pl_eligibility_months: Optional[int] = None
    # Backdated leave
    backdated_max_days: Optional[int] = None
    # Carry forward
    carry_forward_pl_max: Optional[int] = None
    # WFH
    wfh_max_days: Optional[int] = None
    wfh_day_value: Optional[Decimal] = None
    # Old rules
    probation_months: Optional[int] = None  # DEPRECATED
    cl_pl_notice_days: Optional[int] = None
    cl_pl_monthly_cap: Optional[Decimal] = None
    enforce_monthly_cap: Optional[bool] = None
    enforce_notice_days: Optional[bool] = None
    notice_days_cl_pl: Optional[int] = None
    # Sick intimation
    enforce_sick_intimation: Optional[bool] = None
    sick_intimation_min_minutes: Optional[int] = None
    # Sandwich rule
    weekly_off_day: Optional[int] = None
    sandwich_enabled: Optional[bool] = None
    sandwich_include_weekly_off: Optional[bool] = None
    sandwich_include_holidays: Optional[bool] = None
    sandwich_include_rh: Optional[bool] = None
    treat_event_as_non_working_for_sandwich: Optional[bool] = None
    # HR override
    allow_hr_override: Optional[bool] = None
