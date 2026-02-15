"""
Policy settings service - business logic for policy management
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.policy import PolicySetting
from app.services.audit_service import log_audit
from app.services.policy_validator import get_or_create_policy_settings


def get_policy_settings(db: Session, year: int) -> PolicySetting:
    """
    Get policy settings for a year
    
    Args:
        db: Database session
        year: Calendar year
    
    Returns:
        PolicySetting instance
    
    Raises:
        HTTPException: If policy settings not found
    """
    policy = db.query(PolicySetting).filter(PolicySetting.year == year).first()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy settings for year {year} not found"
        )
    
    return policy


def update_policy_settings(
    db: Session,
    year: int,
    # Annual entitlements
    annual_pl: int = None,
    annual_cl: int = None,
    annual_sl: int = None,
    annual_rh: int = None,
    public_holiday_total: int = None,
    # Monthly credits
    monthly_credit_pl: float = None,
    monthly_credit_cl: float = None,
    monthly_credit_sl: float = None,
    # PL eligibility
    pl_eligibility_months: int = None,
    # Backdated leave
    backdated_max_days: int = None,
    # Carry forward
    carry_forward_pl_max: int = None,
    # WFH
    wfh_max_days: int = None,
    wfh_day_value: float = None,
    # Old rules
    probation_months: int = None,
    cl_pl_notice_days: int = None,
    cl_pl_monthly_cap: float = None,
    enforce_monthly_cap: bool = None,
    enforce_notice_days: bool = None,
    notice_days_cl_pl: int = None,
    # Sick intimation
    enforce_sick_intimation: bool = None,
    sick_intimation_min_minutes: int = None,
    # Sandwich rule
    weekly_off_day: int = None,
    sandwich_enabled: bool = None,
    sandwich_include_weekly_off: bool = None,
    sandwich_include_holidays: bool = None,
    sandwich_include_rh: bool = None,
    treat_event_as_non_working_for_sandwich: bool = None,
    # HR override
    allow_hr_override: bool = None,
    actor_id: int = None
) -> PolicySetting:
    """
    Update policy settings for a year (creates if not exists)
    
    Supports all policy fields from FINAL PDF.
    
    Args:
        db: Database session
        year: Calendar year
        actor_id: ID of user updating the policy
        ... (all policy fields as optional parameters)
    
    Returns:
        Updated PolicySetting instance
    """
    from decimal import Decimal
    
    policy = db.query(PolicySetting).filter(PolicySetting.year == year).first()
    
    if not policy:
        # Create new policy settings with defaults
        policy = get_or_create_policy_settings(db, year)
    
    # Update fields if provided
    if annual_pl is not None:
        policy.annual_pl = annual_pl
    if annual_cl is not None:
        policy.annual_cl = annual_cl
    if annual_sl is not None:
        policy.annual_sl = annual_sl
    if annual_rh is not None:
        policy.annual_rh = annual_rh
    if public_holiday_total is not None:
        policy.public_holiday_total = public_holiday_total
    if monthly_credit_pl is not None:
        policy.monthly_credit_pl = Decimal(str(monthly_credit_pl))
    if monthly_credit_cl is not None:
        policy.monthly_credit_cl = Decimal(str(monthly_credit_cl))
    if monthly_credit_sl is not None:
        policy.monthly_credit_sl = Decimal(str(monthly_credit_sl))
    if pl_eligibility_months is not None:
        policy.pl_eligibility_months = pl_eligibility_months
    if backdated_max_days is not None:
        policy.backdated_max_days = backdated_max_days
    if carry_forward_pl_max is not None:
        policy.carry_forward_pl_max = carry_forward_pl_max
    if wfh_max_days is not None:
        policy.wfh_max_days = wfh_max_days
    if wfh_day_value is not None:
        policy.wfh_day_value = Decimal(str(wfh_day_value))
    if probation_months is not None:
        policy.probation_months = probation_months
    if cl_pl_notice_days is not None:
        policy.cl_pl_notice_days = cl_pl_notice_days
    if cl_pl_monthly_cap is not None:
        policy.cl_pl_monthly_cap = Decimal(str(cl_pl_monthly_cap))
    if enforce_monthly_cap is not None:
        policy.enforce_monthly_cap = enforce_monthly_cap
    if enforce_notice_days is not None:
        policy.enforce_notice_days = enforce_notice_days
    if notice_days_cl_pl is not None:
        policy.notice_days_cl_pl = notice_days_cl_pl
    if enforce_sick_intimation is not None:
        policy.enforce_sick_intimation = enforce_sick_intimation
    if sick_intimation_min_minutes is not None:
        policy.sick_intimation_min_minutes = sick_intimation_min_minutes
    if weekly_off_day is not None:
        policy.weekly_off_day = weekly_off_day
    if sandwich_enabled is not None:
        policy.sandwich_enabled = sandwich_enabled
    if sandwich_include_weekly_off is not None:
        policy.sandwich_include_weekly_off = sandwich_include_weekly_off
    if sandwich_include_holidays is not None:
        policy.sandwich_include_holidays = sandwich_include_holidays
    if sandwich_include_rh is not None:
        policy.sandwich_include_rh = sandwich_include_rh
    if treat_event_as_non_working_for_sandwich is not None:
        policy.treat_event_as_non_working_for_sandwich = treat_event_as_non_working_for_sandwich
    if allow_hr_override is not None:
        policy.allow_hr_override = allow_hr_override
    
    db.commit()
    db.refresh(policy)
    
    # Log audit
    if actor_id:
        log_audit(
            db=db,
            actor_id=actor_id,
            action="POLICY_UPDATE",
            entity_type="policy_settings",
            entity_id=policy.id,
            meta={"year": year}
        )
    
    return policy
