"""
Policy settings management endpoints (HR-only for GET/PUT; public-summary for app/dashboard).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Role, Employee
from app.schemas.policy import PolicyOut, PolicyUpdate
from app.services.policy_service import get_policy_settings, update_policy_settings
from app.services.policy_validator import get_or_create_policy_settings
from app.services.year_close_service import run_year_close

router = APIRouter()


@router.get("/{year}/public-summary")
async def get_policy_public_summary(
    year: int,
    db: Session = Depends(get_db),
):
    """
    Public summary of leave entitlements for a year (for app and dashboard).
    If policy does not exist, it is created with ACS defaults (PL=7, SL=6, CL=5, RH=1, public_holidays=14).
    """
    policy = get_or_create_policy_settings(db, year)
    return {
        "year": year,
        "PL": policy.annual_pl,
        "CL": policy.annual_cl,
        "SL": policy.annual_sl,
        "RH": policy.annual_rh,
        "public_holidays": policy.public_holiday_total if policy.public_holiday_total is not None else 14,
    }


@router.get("/{year}", response_model=PolicyOut)
async def get_policy_endpoint(
    year: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Get policy settings for a year (Admin-only)"""
    return get_policy_settings(db, year)


@router.put("/{year}", response_model=PolicyOut)
async def update_policy_endpoint(
    year: int,
    policy_data: PolicyUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Update policy settings for a year (creates if not exists) (Admin-only)"""
    from decimal import Decimal
    
    return update_policy_settings(
        db=db,
        year=year,
        # Annual entitlements
        annual_pl=policy_data.annual_pl,
        annual_cl=policy_data.annual_cl,
        annual_sl=policy_data.annual_sl,
        annual_rh=policy_data.annual_rh,
        public_holiday_total=policy_data.public_holiday_total,
        # Monthly credits
        monthly_credit_pl=float(policy_data.monthly_credit_pl) if policy_data.monthly_credit_pl is not None else None,
        monthly_credit_cl=float(policy_data.monthly_credit_cl) if policy_data.monthly_credit_cl is not None else None,
        monthly_credit_sl=float(policy_data.monthly_credit_sl) if policy_data.monthly_credit_sl is not None else None,
        # PL eligibility
        pl_eligibility_months=policy_data.pl_eligibility_months,
        # Backdated leave
        backdated_max_days=policy_data.backdated_max_days,
        # Carry forward
        carry_forward_pl_max=policy_data.carry_forward_pl_max,
        # WFH
        wfh_max_days=policy_data.wfh_max_days,
        wfh_day_value=float(policy_data.wfh_day_value) if policy_data.wfh_day_value is not None else None,
        # Old rules
        probation_months=policy_data.probation_months,
        cl_pl_notice_days=policy_data.cl_pl_notice_days,
        cl_pl_monthly_cap=float(policy_data.cl_pl_monthly_cap) if policy_data.cl_pl_monthly_cap is not None else None,
        enforce_monthly_cap=policy_data.enforce_monthly_cap,
        enforce_notice_days=policy_data.enforce_notice_days,
        notice_days_cl_pl=policy_data.notice_days_cl_pl,
        # Sick intimation
        enforce_sick_intimation=policy_data.enforce_sick_intimation,
        sick_intimation_min_minutes=policy_data.sick_intimation_min_minutes,
        # Sandwich rule
        weekly_off_day=policy_data.weekly_off_day,
        sandwich_enabled=policy_data.sandwich_enabled,
        sandwich_include_weekly_off=policy_data.sandwich_include_weekly_off,
        sandwich_include_holidays=policy_data.sandwich_include_holidays,
        sandwich_include_rh=policy_data.sandwich_include_rh,
        treat_event_as_non_working_for_sandwich=policy_data.treat_event_as_non_working_for_sandwich,
        # HR override
        allow_hr_override=policy_data.allow_hr_override,
        actor_id=current_user.id
    )


@router.post("/year-close", status_code=200)
async def year_close_endpoint(
    year: int = Query(..., description="Year to close (e.g., 2026)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """
    Run year-end close process (Admin-only).
    
    Performs PL carry forward and encashment:
    - Carry forward: min(unused_pl, max=4)
    - Encash: unused_pl - carry_forward
    - CL and SL lapse (no carry forward)
    - Creates next year's balance with PL = carry_forward
    """
    result = run_year_close(db=db, year=year, actor_id=current_user.id)
    return result
