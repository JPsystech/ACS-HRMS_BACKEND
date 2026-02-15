"""
Policy validation service - validates leave requests against policy rules
"""
from datetime import date, timedelta
from typing import Dict, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus
from app.models.employee import Employee, Role
from app.models.policy import PolicySetting
import json


def is_in_probation(join_date: date, today: date, probation_months: int) -> bool:
    """
    Check if employee is still in probation period.
    
    Probation ends at join_date + probation_months (calendar months).
    
    Args:
        join_date: Employee join date
        today: Current date
        probation_months: Number of months for probation
    
    Returns:
        True if employee is in probation, False otherwise
    """
    # Calculate probation end date by adding months
    year = join_date.year
    month = join_date.month
    day = join_date.day
    
    # Add months
    month += probation_months
    while month > 12:
        year += 1
        month -= 12
    
    # Handle month-end edge cases (e.g., Jan 31 + 1 month = Feb 28/29)
    try:
        probation_end_date = date(year, month, day)
    except ValueError:
        # If day doesn't exist in target month (e.g., Jan 31 -> Feb), use last day of month
        if month == 2:
            # Check for leap year
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                probation_end_date = date(year, 2, 29)
            else:
                probation_end_date = date(year, 2, 28)
        elif month in [4, 6, 9, 11]:
            probation_end_date = date(year, month, 30)
        else:
            probation_end_date = date(year, month, 31)
    
    return today < probation_end_date


def get_or_create_policy_settings(db: Session, year: int) -> PolicySetting:
    """
    Get policy settings for a year, creating default if not exists.
    
    Uses FINAL PDF policy defaults:
    - Annual entitlements: PL=7, CL=5, SL=6, RH=1
    - Monthly credit: +1 PL, +1 CL (SL is annual grant)
    - PL eligibility: 6 months
    - Backdated max: 7 days
    - Carry forward max: 4 PL
    - WFH: 12 days/year, 0.5 day value
    
    Args:
        db: Database session
        year: Calendar year
    
    Returns:
        PolicySetting instance
    """
    policy = db.query(PolicySetting).filter(PolicySetting.year == year).first()
    
    if not policy:
        # ACS default policy: PL=7, SL=6, CL=5, RH=1; public_holiday_total=14 (display only)
        policy = PolicySetting(
            year=year,
            # Annual entitlements
            annual_pl=7,
            annual_cl=5,
            annual_sl=6,
            annual_rh=1,
            public_holiday_total=14,
            # Monthly credits
            monthly_credit_pl=1.0,
            monthly_credit_cl=1.0,
            monthly_credit_sl=0.0,  # SL is annual grant, not monthly
            # PL eligibility (replaces probation lock)
            pl_eligibility_months=6,
            # Backdated leave
            backdated_max_days=7,
            # Carry forward / encashment
            carry_forward_pl_max=4,
            # WFH policy
            wfh_max_days=12,
            wfh_day_value=0.5,
            # Old rules (OFF by default)
            probation_months=3,  # DEPRECATED
            cl_pl_notice_days=3,
            cl_pl_monthly_cap=4.0,
            enforce_monthly_cap=False,  # OFF by default (not in PDF)
            enforce_notice_days=False,  # Configurable, default OFF
            notice_days_cl_pl=3,
            # Sick intimation (shift-dependent, default OFF)
            enforce_sick_intimation=False,
            sick_intimation_min_minutes=120,
            # Sandwich rule
            weekly_off_day=7,
            sandwich_enabled=True,
            sandwich_include_weekly_off=True,
            sandwich_include_holidays=True,
            sandwich_include_rh=False,
            treat_event_as_non_working_for_sandwich=True,
            # HR override
            allow_hr_override=True
        )
        db.add(policy)
        db.commit()
        db.refresh(policy)
    
    return policy


def validate_pl_eligibility(
    user: Employee,
    leave_type: LeaveType,
    from_date: date,
    settings: PolicySetting,
    today: date,
    override_policy: bool = False
) -> None:
    """
    Validate PL eligibility rule (replaces old probation lock).
    
    Per FINAL PDF:
    - CL is allowed in joining month (no lock)
    - PL is allowed only after 6 months completion (join_date + 6 months)
    - SL, COMPOFF, RH, LWP are not affected by this rule
    - HR override can bypass this rule
    
    Args:
        user: Employee applying for leave
        leave_type: Type of leave
        from_date: Leave start date
        settings: Policy settings
        today: Current date
        override_policy: Whether override is enabled
    
    Raises:
        HTTPException: If validation fails
    """
    if leave_type != LeaveType.PL:
        return  # Only PL is restricted by eligibility rule
    
    if override_policy:
        return  # Override bypasses PL eligibility check
    
    # Calculate PL eligibility date (join_date + 6 months)
    join_date = user.join_date
    year = join_date.year
    month = join_date.month
    day = join_date.day
    
    # Add 6 months
    month += settings.pl_eligibility_months
    while month > 12:
        year += 1
        month -= 12
    
    # Handle month-end edge cases
    try:
        pl_eligible_date = date(year, month, day)
    except ValueError:
        # If day doesn't exist in target month, use last day of month
        if month == 2:
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                pl_eligible_date = date(year, 2, 29)
            else:
                pl_eligible_date = date(year, 2, 28)
        elif month in [4, 6, 9, 11]:
            pl_eligible_date = date(year, month, 30)
        else:
            pl_eligible_date = date(year, month, 31)
    
    # Check if from_date is before PL eligibility date
    if from_date < pl_eligible_date:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"PL leave is allowed only after {settings.pl_eligibility_months} months from join date. "
                   f"Join date: {join_date}, PL eligible from: {pl_eligible_date}, "
                   f"Requested from date: {from_date}. HR override available with remark."
        )


# Keep old function for backward compatibility but mark as deprecated
def validate_probation(
    user: Employee,
    leave_type: LeaveType,
    from_date: date,
    settings: PolicySetting,
    today: date,
    override_policy: bool = False
) -> None:
    """
    DEPRECATED: Use validate_pl_eligibility instead.
    
    This function is kept for backward compatibility but now calls validate_pl_eligibility.
    """
    validate_pl_eligibility(user, leave_type, from_date, settings, today, override_policy)


def validate_notice(
    leave_type: LeaveType,
    from_date: date,
    settings: PolicySetting,
    today: date,
    override_policy: bool = False
) -> None:
    """
    Validate advance notice rule (configurable, default OFF).
    
    CL and PL must be applied at least N calendar days before from_date.
    COMPOFF is exempt from notice rule.
    This rule is configurable via enforce_notice_days flag and does NOT block backdated emergency leave.
    
    Args:
        leave_type: Type of leave
        from_date: Leave start date
        settings: Policy settings
        today: Current date
        override_policy: Whether override is enabled
    
    Raises:
        HTTPException: If validation fails
    """
    # Only apply if enforcement is enabled
    if not settings.enforce_notice_days:
        return
    
    if leave_type not in (LeaveType.CL, LeaveType.PL):
        return  # Notice rule applies only to CL and PL (COMPOFF exempt)
    
    if override_policy:
        return  # Override bypasses notice check
    
    # Backdated leave is handled separately (backdated_max_days rule)
    # Don't block backdated leave here
    if from_date < today:
        return  # Backdated leave validation is handled elsewhere
    
    days_notice = (from_date - today).days
    notice_days = settings.notice_days_cl_pl or settings.cl_pl_notice_days
    
    if days_notice < notice_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{leave_type.value} leave must be applied at least {notice_days} calendar days before the start date. "
                   f"Current notice: {days_notice} days."
        )


def validate_monthly_cap(
    db: Session,
    employee_id: int,
    request_by_month: Dict[str, float],
    settings: PolicySetting,
    year: int,
    exclude_leave_request_id: Optional[int] = None
) -> None:
    """
    Validate monthly cap rule (configurable, default OFF).
    
    Monthly cap applies to APPROVED days only, of leave types CL, PL, and RH.
    COMPOFF is exempt from monthly cap.
    RH counts as PL for monthly limit.
    Counts total approved leave days (computed_days) regardless of paid vs LWP.
    
    This rule is NOT in FINAL PDF, so enforce_monthly_cap defaults to False.
    
    Args:
        db: Database session
        employee_id: Employee ID
        request_by_month: computed_days_by_month from the new request (dict with "YYYY-MM" keys)
        settings: Policy settings
        year: Calendar year
        exclude_leave_request_id: Leave request ID to exclude from existing totals (for approval-time validation)
    
    Raises:
        HTTPException: If validation fails
    """
    # Only apply if enforcement is enabled
    if not settings.enforce_monthly_cap:
        return
    
    # Get all approved leave requests for this employee in this year
    # Types: CL, PL, RH (RH counts as PL for monthly cap)
    # COMPOFF is excluded from monthly cap
    query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status == LeaveStatus.APPROVED,
        LeaveRequest.leave_type.in_([LeaveType.CL, LeaveType.PL, LeaveType.RH]),
        LeaveRequest.from_date >= date(year, 1, 1),
        LeaveRequest.to_date <= date(year, 12, 31)
    )
    
    if exclude_leave_request_id:
        query = query.filter(LeaveRequest.id != exclude_leave_request_id)
    
    approved_requests = query.all()
    
    # Build monthly totals from existing approved requests
    existing_by_month: Dict[str, float] = {}
    
    for req in approved_requests:
        if req.computed_days_by_month:
            try:
                req_by_month = json.loads(req.computed_days_by_month)
                for month_key, days in req_by_month.items():
                    existing_by_month[month_key] = existing_by_month.get(month_key, 0.0) + float(days)
            except (json.JSONDecodeError, TypeError):
                # Fallback: if JSON parsing fails, estimate from date range
                # This shouldn't happen if computed_days_by_month was set correctly
                pass
    
    # Check each month in the new request
    for month_key, request_days in request_by_month.items():
        existing_days = existing_by_month.get(month_key, 0.0)
        total_days = existing_days + float(request_days)
        
        if total_days > float(settings.cl_pl_monthly_cap):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Monthly cap exceeded for {month_key}. "
                       f"Existing approved days: {existing_days:.1f}, "
                       f"Requested days: {request_days:.1f}, "
                       f"Total: {total_days:.1f}, "
                       f"Cap: {settings.cl_pl_monthly_cap}"
            )


def validate_backdated_leave(
    from_date: date,
    settings: PolicySetting,
    today: date
) -> tuple[bool, Optional[str]]:
    """
    Validate backdated leave rule.
    
    Per FINAL PDF:
    - Backdated leave allowed up to 7 days (emergency)
    - Beyond 7 days: auto-convert to LWP
    
    Args:
        from_date: Leave start date
        settings: Policy settings
        today: Current date
    
    Returns:
        Tuple of (is_backdated, auto_lwp_reason)
        - is_backdated: True if leave is backdated
        - auto_lwp_reason: Reason for auto-conversion if applicable, None otherwise
    """
    if from_date >= today:
        return False, None  # Not backdated
    
    days_back = (today - from_date).days
    
    if days_back <= settings.backdated_max_days:
        return True, None  # Backdated but within allowed limit (emergency)
    else:
        # Beyond limit: auto-convert to LWP
        return True, f"backdated_over_limit_{days_back}_days_max_{settings.backdated_max_days}"


def validate_company_event_block(
    db: Session,
    from_date: date,
    to_date: date,
    year: int,
    override_policy: bool = False
) -> None:
    """
    Validate company event blocking rule.
    
    Per FINAL PDF:
    - Leave not permitted on event/celebration days (unless management approval/HR override)
    
    Args:
        db: Database session
        from_date: Leave start date
        to_date: Leave end date
        year: Calendar year
        override_policy: Whether override is enabled
    
    Raises:
        HTTPException: If validation fails
    """
    from app.models.event import CompanyEvent
    
    if override_policy:
        return  # HR override bypasses event block
    
    # Check for active company events in the date range
    events = db.query(CompanyEvent).filter(
        CompanyEvent.year == year,
        CompanyEvent.active == True,
        CompanyEvent.date >= from_date,
        CompanyEvent.date <= to_date
    ).all()
    
    if events:
        event_dates = [str(e.date) for e in events]
        event_names = [e.name for e in events]
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Leave is not permitted on company event/celebration days: {', '.join(event_names)} "
                   f"on {', '.join(event_dates)}. Management approval/HR override required with remark."
        )


def validate_override(
    current_user: Employee,
    override_policy: bool,
    override_remark: Optional[str]
) -> None:
    """
    Validate HR override fields.
    
    Only HR can set override_policy to true.
    If override_policy is true, override_remark is required.
    
    Args:
        current_user: Current authenticated user
        override_policy: Whether override is enabled
        override_remark: Override remark
    
    Raises:
        HTTPException: If validation fails
    """
    if override_policy:
        if current_user.role != Role.HR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR can override policy rules"
            )
        
        if not override_remark or not override_remark.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="override_remark is required when override_policy is true"
            )
