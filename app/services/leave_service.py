"""
Leave service - business logic for leave management
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple, Dict, Set
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from fastapi import HTTPException, status
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus, LeaveBalance, LeaveApproval, ApprovalAction
from app.models.employee import Employee, Role
from app.models.role import RoleModel
from app.services.audit_service import log_audit

logger = logging.getLogger(__name__)

# Statuses that must never be auto-reset to PENDING (approve/reject/cancel are final)
TERMINAL_LEAVE_STATUSES = frozenset({
    LeaveStatus.APPROVED,
    LeaveStatus.REJECTED,
    LeaveStatus.CANCELLED,
    LeaveStatus.CANCELLED_BY_COMPANY,
})
from app.services.holiday_service import get_holidays_in_range, is_rh_date
from app.services.policy_validator import (
    get_or_create_policy_settings,
    validate_pl_eligibility,
    validate_probation,  # Keep for backward compatibility
    validate_notice,
    validate_monthly_cap,
    validate_override,
    validate_backdated_leave,
    validate_company_event_block
)
from app.services.compoff_service import consume_compoff_on_leave_approval
from app.services import leave_wallet_service as wallet
from app.models.leave import WALLET_LEAVE_TYPES
from decimal import Decimal
import json


def is_sunday(check_date: date) -> bool:
    """Check if a date is Sunday (weekly off)"""
    return check_date.weekday() == 6  # Monday=0, Sunday=6


def get_subordinate_ids(db: Session, manager_id: int) -> List[int]:
    """
    Recursively fetch all subordinate employee IDs in the reporting hierarchy.
    Uses iterative approach for better reliability across different databases.
    
    Args:
        db: Database session
        manager_id: ID of the manager to fetch subordinates for
        
    Returns:
        List of employee IDs for all direct and indirect reports
    """
    # Use iterative approach for better reliability
    subordinate_ids = []
    
    from collections import deque
    
    queue = deque([manager_id])
    
    while queue:
        current_manager_id = queue.popleft()
        
        # Get direct reports of current manager
        direct_reports = db.query(Employee.id).filter(
            Employee.reporting_manager_id == current_manager_id,
            Employee.active == True
        ).all()
        
        for (employee_id,) in direct_reports:
            subordinate_ids.append(employee_id)
            queue.append(employee_id)  # Add to queue to process their subordinates
    
    return subordinate_ids


def get_manager_chain_ids(db: Session, employee_id: int) -> List[int]:
    """
    Get the upward chain of manager IDs for an employee (recursive reporting hierarchy).
    
    Args:
        db: Database session
        employee_id: ID of the employee to get manager chain for
        
    Returns:
        List of manager IDs in the chain (employee -> manager -> manager...)
    """
    manager_chain = []
    current_id = employee_id
    
    # Prevent infinite loops with a safety limit
    max_depth = 20
    depth = 0
    
    while current_id and depth < max_depth:
        depth += 1
        
        # Get current employee's reporting manager
        employee = db.query(Employee).filter(
            Employee.id == current_id,
            Employee.active == True
        ).first()
        
        if not employee or not employee.reporting_manager_id:
            break
            
        # Add manager to chain and move up
        manager_chain.append(employee.reporting_manager_id)
        current_id = employee.reporting_manager_id
    
    return manager_chain


def get_role_rank(db: Session, employee: Employee) -> int:
    """
    Get the role_rank for an employee.
    
    Args:
        db: Database session
        employee: Employee instance
        
    Returns:
        role_rank value for the employee's role
    """
    role_row = db.query(RoleModel).filter(
        RoleModel.name == employee.role,
        RoleModel.is_active == True
    ).first()
    
    if not role_row:
        # Default to high rank if role not found (restrictive)
        return 99
    
    return role_row.role_rank


def get_non_working_days_in_range(
    db: Session,
    from_date: date,
    to_date: date,
    include_company_events: bool = True
) -> Set[date]:
    """
    Get set of non-working days (Sundays + active holidays + company events) within the given date range.
    
    This excludes Restricted Holidays (RH) as they are separate from regular holidays
    and are not included in sandwich calculations.
    
    Per FINAL PDF: Company events are treated as non-working for sandwich rule.
    
    Args:
        db: Database session
        from_date: Start date (inclusive)
        to_date: End date (inclusive)
        include_company_events: Whether to include company events (default True)
    
    Returns:
        Set of non-working dates (Sundays + active holidays + company events)
    """
    from app.models.event import CompanyEvent
    
    non_working = set()
    
    # Add all Sundays in range
    current_date = from_date
    while current_date <= to_date:
        if is_sunday(current_date):
            non_working.add(current_date)
        current_date += timedelta(days=1)
    
    # Add active holidays in range
    holiday_set = get_holidays_in_range(db, from_date, to_date)
    non_working.update(holiday_set)
    
    # Add company events if enabled
    if include_company_events:
        year = from_date.year
        events = db.query(CompanyEvent).filter(
            CompanyEvent.year == year,
            CompanyEvent.active == True,
            CompanyEvent.date >= from_date,
            CompanyEvent.date <= to_date
        ).all()
        for event in events:
            non_working.add(event.date)
    
    return non_working


def calculate_days_baseline(
    db: Session,
    from_date: date,
    to_date: date
) -> float:
    """
    Calculate leave days between from_date and to_date (inclusive),
    excluding Sundays and holidays.
    
    Baseline implementation:
    - Counts all days in range inclusive
    - Excludes Sundays (weekly off)
    - Excludes active holidays from holidays table
    - Returns float for future 0.5 day support
    
    Args:
        db: Database session (for holiday lookup)
        from_date: Start date
        to_date: End date
    
    Returns:
        Number of leave days (float)
    """
    if from_date > to_date:
        return 0.0
    
    # Get active holidays in range
    holiday_set = get_holidays_in_range(db, from_date, to_date)
    
    current_date = from_date
    day_count = 0.0
    
    while current_date <= to_date:
        # Exclude Sundays
        if not is_sunday(current_date):
            # Exclude holidays
            if current_date not in holiday_set:
                day_count += 1.0
        current_date += timedelta(days=1)
    
    return day_count


def calculate_days_with_sandwich(
    db: Session,
    leave_type: LeaveType,
    from_date: date,
    to_date: date
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate leave days with sandwich rule applied for applicable leave types.
    
    Sandwich Rule:
    - Applies to CL, PL, SL only
    - Does NOT apply to RH, COMPOFF, LWP
    - If leave exists on both sides of a Sunday/holiday, then that intervening
      Sunday/holiday is counted as leave.
    - Only Sundays/holidays BETWEEN counted leave days are included (not at edges)
    
    Args:
        db: Database session
        leave_type: Type of leave
        from_date: Start date
        to_date: End date
    
    Returns:
        Tuple of (total_days: float, by_month: dict[str, float])
        where by_month keys are "YYYY-MM" format and values are day counts
    """
    if from_date > to_date:
        return 0.0, {}
    
    # Get policy settings to check if company events should be included
    year = from_date.year
    try:
        settings = get_or_create_policy_settings(db, year)
        include_events = getattr(settings, 'treat_event_as_non_working_for_sandwich', True)
    except Exception:
        # Fallback if policy settings not available
        include_events = True
    
    # Get non-working days (Sundays + holidays + company events if enabled) in range
    non_working_days = get_non_working_days_in_range(db, from_date, to_date, include_company_events=include_events)
    
    # First, compute baseline counted days (excluding Sundays and holidays)
    baseline_counted = set()
    current_date = from_date
    
    while current_date <= to_date:
        if current_date not in non_working_days:
            baseline_counted.add(current_date)
        current_date += timedelta(days=1)
    
    # If leave type does NOT support sandwich, return baseline only
    if leave_type not in (LeaveType.CL, LeaveType.PL, LeaveType.SL):
        # Build by_month from baseline only
        by_month: Dict[str, float] = {}
        for d in baseline_counted:
            month_key = f"{d.year}-{d.month:02d}"
            by_month[month_key] = by_month.get(month_key, 0.0) + 1.0
        
        return float(len(baseline_counted)), by_month
    
    # Sandwich applies: find non-working days that are BETWEEN counted leave days
    sandwich_included = set()
    
    # For each non-working day in range, check if it's sandwiched
    for non_working_date in non_working_days:
        if non_working_date < from_date or non_working_date > to_date:
            continue
        
        # Check if there's at least one counted day before AND after this non-working day
        has_before = any(d < non_working_date for d in baseline_counted)
        has_after = any(d > non_working_date for d in baseline_counted)
        
        if has_before and has_after:
            sandwich_included.add(non_working_date)
    
    # Combine baseline counted days with sandwich-included non-working days
    all_included_days = baseline_counted | sandwich_included
    
    # Build by_month dictionary
    by_month: Dict[str, float] = {}
    for d in all_included_days:
        month_key = f"{d.year}-{d.month:02d}"
        by_month[month_key] = by_month.get(month_key, 0.0) + 1.0
    
    total_days = float(len(all_included_days))
    
    return total_days, by_month


def validate_leave_year(from_date: date, to_date: date) -> None:
    """
    Validate that both dates fall within the same calendar year.
    
    Rejects cross-year leave requests (e.g., Dec 31 to Jan 2).
    
    Args:
        from_date: Start date
        to_date: End date
    
    Raises:
        HTTPException: If dates cross year boundary
    """
    from_year = from_date.year
    to_year = to_date.year
    
    if from_year != to_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave cannot span across years. From date year: {from_year}, To date year: {to_year}"
        )
    
    # Ensure dates are within current calendar year (Jan 1 to Dec 31)
    year_start = date(from_year, 1, 1)
    year_end = date(from_year, 12, 31)
    
    if from_date < year_start or to_date > year_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave dates must be within the calendar year {from_year}"
        )


def validate_overlap(
    db: Session,
    employee_id: int,
    from_date: date,
    to_date: date,
    exclude_leave_id: Optional[int] = None
) -> None:
    """
    Validate that the leave request doesn't overlap with existing
    PENDING or APPROVED leave requests.
    
    Args:
        db: Database session
        employee_id: Employee ID
        from_date: Start date of new leave
        to_date: End date of new leave
        exclude_leave_id: Leave request ID to exclude from check (for updates)
    
    Raises:
        HTTPException: If overlap detected (409 Conflict)
    """
    # Overlap condition: NOT (existing.to_date < new.from_date OR existing.from_date > new.to_date)
    # Which means: existing.to_date >= new.from_date AND existing.from_date <= new.to_date
    
    query = db.query(LeaveRequest).options(
        joinedload(LeaveRequest.employee),
        joinedload(LeaveRequest.approver)
    ).options(
        joinedload(LeaveRequest.employee),
        joinedload(LeaveRequest.approver)
    ).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
        LeaveRequest.to_date >= from_date,
        LeaveRequest.from_date <= to_date
    )
    
    if exclude_leave_id:
        query = query.filter(LeaveRequest.id != exclude_leave_id)
    
    overlapping = query.first()
    
    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Leave request overlaps with existing leave from {overlapping.from_date} to {overlapping.to_date}"
        )


def apply_leave(
    db: Session,
    employee_id: int,
    leave_type: LeaveType,
    from_date: date,
    to_date: date,
    reason: Optional[str] = None,
    override_policy: bool = False,
    override_remark: Optional[str] = None,
    current_user: Optional[Employee] = None
) -> LeaveRequest:
    """
    Apply for leave (creates PENDING request)
    
    Args:
        db: Database session
        employee_id: Employee ID applying for leave
        leave_type: Type of leave
        from_date: Start date
        to_date: End date
        reason: Optional reason
        override_policy: Whether to override policy rules (HR only)
        override_remark: Remark for override (required if override_policy is True)
        current_user: Current authenticated user (for override validation)
    
    Returns:
        Created LeaveRequest instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate date order
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be less than or equal to to_date"
        )
    
    # Validate leave year
    validate_leave_year(from_date, to_date)
    
    # RH-specific validations
    if leave_type == LeaveType.RH:
        # RH must be single day
        if from_date != to_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Restricted Holiday (RH) must be applied for a single day only"
            )
        
        # RH date must be a valid restricted holiday
        year = from_date.year
        if not is_rh_date(db, year, from_date):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Date {from_date} is not a valid Restricted Holiday (RH) date for year {year}"
            )
        
        # Check if employee already has an approved RH in this year
        existing_approved_rh = db.query(LeaveRequest).filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.leave_type == LeaveType.RH,
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.from_date >= date(year, 1, 1),
            LeaveRequest.to_date <= date(year, 12, 31)
        ).first()
        
        if existing_approved_rh:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee has already used their Restricted Holiday (RH) quota for year {year}. Only one RH per year is allowed."
            )
    
    # Validate overlap
    validate_overlap(db, employee_id, from_date, to_date)
    
    # Get employee for policy validations
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found"
        )

    # Ensure leave balances exist for this employee+year before any balance checks (auto-init)
    year = from_date.year
    wallet.ensure_wallet_for_employee(db, employee_id, year)
    
    # Validate reporting manager exists (except for MD role)
    if employee.role != Role.MD and not employee.reporting_manager_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reporting manager not set"
        )
    
    # Validate override fields (if provided)
    if current_user:
        validate_override(current_user, override_policy, override_remark)
    elif override_policy:
        # If override_policy is set but no current_user provided, reject
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="override_policy can only be set by authenticated HR users"
        )
    
    # Calculate days with sandwich rule (applies to CL/PL/SL, not to RH/COMPOFF/LWP)
    computed_days, by_month = calculate_days_with_sandwich(db, leave_type, from_date, to_date)
    
    if computed_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave request must have at least one valid day (excluding Sundays and holidays)"
        )
    
    # Get policy settings for the year
    year = from_date.year
    settings = get_or_create_policy_settings(db, year)
    today = date.today()
    
    # Store original leave_type for validations
    original_leave_type = leave_type
    
    # Validate backdated leave rule (applies to all leave types)
    is_backdated, auto_lwp_reason = validate_backdated_leave(from_date, settings, today)
    
    # If backdated beyond limit, auto-convert to LWP
    if auto_lwp_reason:
        # Convert leave_type to LWP automatically
        leave_type = LeaveType.LWP
        # Note: computed_days remains the same, but it will be treated as LWP
    
    # Validate company event blocking (unless override or LWP)
    # LWP doesn't need event blocking (it's already a penalty/conversion)
    if leave_type != LeaveType.LWP and not override_policy:
        validate_company_event_block(db, from_date, to_date, year, override_policy)
    
    # Run policy validations (unless override is enabled or LWP)
    # COMPOFF and LWP are exempt from PL eligibility, notice, and monthly cap
    if leave_type not in (LeaveType.COMPOFF, LeaveType.LWP):
        # Use new PL eligibility rule (replaces probation lock)
        validate_pl_eligibility(employee, leave_type, from_date, settings, today, override_policy)
        validate_notice(leave_type, from_date, settings, today, override_policy)
        # Validate monthly cap (check approved history) - only if enforcement is enabled
        validate_monthly_cap(db, employee_id, by_month, settings, year)
    
    # Convert by_month dict to JSON string for storage
    computed_days_by_month_json = json.dumps(by_month) if by_month else None
    
    # Create leave request
    leave_request = LeaveRequest(
        employee_id=employee_id,
        approver_id=employee.reporting_manager_id,
        leave_type=leave_type,
        from_date=from_date,
        to_date=to_date,
        reason=reason,
        status=LeaveStatus.PENDING,
        computed_days=Decimal(str(computed_days)),
        computed_days_by_month=computed_days_by_month_json,
        paid_days=Decimal('0'),
        lwp_days=Decimal('0'),
        override_policy=override_policy,
        override_remark=override_remark,
        auto_converted_to_lwp=(auto_lwp_reason is not None),
        auto_lwp_reason=auto_lwp_reason,
        applied_at=datetime.now(timezone.utc)
    )
    
    db.add(leave_request)
    db.commit()
    db.refresh(leave_request)
    
    # Log audit
    audit_meta = {
        "leave_type": leave_type.value,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "computed_days": float(computed_days),
        "status": LeaveStatus.PENDING.value
    }
    
    if override_policy:
        audit_meta["override_policy"] = True
        audit_meta["override_remark"] = override_remark
        if current_user:
            audit_meta["override_by"] = current_user.id
    
    log_audit(
        db=db,
        actor_id=employee_id,
        action="LEAVE_APPLY",
        entity_type="leave_requests",
        entity_id=leave_request.id,
        meta=audit_meta
    )
    
    return leave_request


def list_leaves(
    db: Session,
    current_user: Employee,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    employee_id: Optional[int] = None
) -> List[LeaveRequest]:
    """
    List leave requests with role-based scoping.
    Includes ALL statuses (PENDING, APPROVED, REJECTED, CANCELLED). Do NOT filter out CANCELLED.
    Never transform or overwrite status (e.g. never return PENDING for a cancelled leave).
    """
    query = db.query(LeaveRequest).options(
        joinedload(LeaveRequest.employee),
        joinedload(LeaveRequest.approver),
        joinedload(LeaveRequest.rejected_by),
        joinedload(LeaveRequest.cancelled_by)
    )

    # Get current user's role_rank for permission checking
    current_user_rank = get_role_rank(db, current_user)
    
    # Apply role_rank-based scoping with department separation
    if current_user_rank <= 2:  # ADMIN (1) and MD (2) have global access
        # ADMIN and MD can see all employees across all departments
        if employee_id:
            query = query.filter(LeaveRequest.employee_id == employee_id)
    else:
        # For roles with rank 3+ (VP, MANAGER, EMPLOYEE, etc.)
        # They can only see employees in the same department
        
        # First, get all subordinate IDs in the hierarchy (same department only)
        subordinate_ids = []
        if current_user_rank <= 4:  # VP (3) and MANAGER (4) can see their hierarchy
            # Get all subordinates in the reporting hierarchy
            all_subordinate_ids = get_subordinate_ids(db, current_user.id)
            
            # Filter subordinates to only those in the same department
            for sub_id in all_subordinate_ids:
                # Check if subordinate is in the same department
                sub_employee = db.query(Employee).filter(Employee.id == sub_id).first()
                if sub_employee and sub_employee.department_id == current_user.department_id:
                    subordinate_ids.append(sub_id)
        
        # Always include the current user's own leaves
        subordinate_ids.append(current_user.id)
        
        if employee_id:
            # Specific employee requested
            if employee_id == current_user.id:
                # "My leaves" for current user
                query = query.filter(LeaveRequest.employee_id == current_user.id)
            elif employee_id not in subordinate_ids:
                # Employee not in visible hierarchy or different department
                return []
            else:
                # Employee is in visible hierarchy and same department
                query = query.filter(LeaveRequest.employee_id == employee_id)
        else:
            # No specific employee requested, show all visible leaves
            if subordinate_ids:
                # Show leaves for all visible employees (same department hierarchy)
                query = query.filter(LeaveRequest.employee_id.in_(subordinate_ids))
            else:
                # No visible subordinates, return only current user's own leaves
                query = query.filter(LeaveRequest.employee_id == current_user.id)
        
        # Additional department filter to ensure only same department leaves are visible
        query = query.join(Employee, LeaveRequest.employee_id == Employee.id)
        query = query.filter(Employee.department_id == current_user.department_id)
    
    # Apply date filters
    if from_date:
        query = query.filter(LeaveRequest.to_date >= from_date)
    if to_date:
        query = query.filter(LeaveRequest.from_date <= to_date)
    
    # Order by applied_at descending (most recent first)
    return query.order_by(LeaveRequest.applied_at.desc()).all()


def get_or_create_balance(
    db: Session,
    employee_id: int,
    year: int
) -> Optional[LeaveBalance]:
    """
    Ensure wallet exists for employee/year and return the CL balance row (for backward compat).
    Prefer using leave_wallet_service.get_wallet_balances for per-type balances.
    """
    wallet.ensure_wallet_for_employee(db, employee_id, year)
    return (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year,
            LeaveBalance.leave_type == LeaveType.CL,
        )
        .first()
    )


def get_balance_bucket(leave_type: LeaveType) -> Optional[str]:
    """
    Legacy: balance is now per-type in leave_balances. Returns None for wallet types (use wallet API).
    COMPOFF/LWP still return None.
    """
    if leave_type in (LeaveType.CL, LeaveType.SL, LeaveType.PL, LeaveType.RH):
        return "remaining"  # wallet row has 'remaining'
    if leave_type in (LeaveType.COMPOFF, LeaveType.LWP):
        return None
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown leave type: {leave_type}",
    )


def validate_approval_authority(
    db: Session,
    leave_request: LeaveRequest,
    approver: Employee
) -> None:
    """
    Validate that the approver has authority to approve the leave request
    
    Approval authority rules (role_rank-based):
    - ADMIN (rank=1) and MD (rank=2): Can approve any leave across all departments
    - VP (rank=3) and MANAGER (rank=4): Can approve leaves for their hierarchical subordinates (recursive)
    - EMPLOYEE (rank=5+): No approval authority
    
    Args:
        db: Database session
        leave_request: Leave request to approve
        approver: Employee attempting to approve
    
    Raises:
        HTTPException: If approver doesn't have authority
    """
    # Employee cannot approve own leave
    if approver.id == leave_request.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee cannot approve their own leave"
        )
    
    # Get approver's role_rank for permission checking
    approver_rank = get_role_rank(db, approver)
    
    # ADMIN (rank=1) and MD (rank=2) can approve any leave across all departments
    if approver_rank <= 2:
        return
    
    # Get the employee who applied for the leave
    employee = db.query(Employee).filter(Employee.id == leave_request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {leave_request.employee_id} not found"
        )
    
    # VP (rank=3) and MANAGER (rank=4) can approve leaves for their hierarchical subordinates (recursive)
    if approver_rank <= 4:  # VP and MANAGER
        # Check if employee is in the approver's hierarchical subtree (recursive, all departments)
        subordinate_ids = get_subordinate_ids(db, approver.id)
        
        if leave_request.employee_id in subordinate_ids:
            return
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only approve leaves for your hierarchical subordinates"
            )
    
    # No approval authority for other roles (EMPLOYEE, etc.)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have approval authority for this leave request"
    )


def can_approve_leave(
    db: Session,
    approver: Employee,
    leave_request: LeaveRequest
) -> bool:
    """
    Check if an approver can approve a leave request based on hierarchical rules
    
    Approval rules:
    - ADMIN and MD: Can approve any leave
    - VP and MANAGER: Can approve if employee is in their hierarchical subtree
    - Self-approval is always blocked
    
    Args:
        db: Database session
        approver: Employee attempting to approve
        leave_request: Leave request to approve
        
    Returns:
        bool: True if approver has authority, False otherwise
    """
    # Block self-approval
    if approver.id == leave_request.employee_id:
        return False
    
    # Get approver's role_rank for permission checking
    approver_rank = get_role_rank(db, approver)
    
    # ADMIN (rank=1) and MD (rank=2) can approve any leave
    if approver_rank <= 2:
        return True
    
    # VP (rank=3) and MANAGER (rank=4) can approve leaves for their hierarchical subordinates
    if approver_rank <= 4:
        subordinate_ids = get_subordinate_ids(db, approver.id)
        return leave_request.employee_id in subordinate_ids
    
    # No approval authority for other roles (EMPLOYEE, etc.)
    return False


def approve_leave(
    db: Session,
    leave_request_id: int,
    approver: Employee,
    remarks: Optional[str] = None
) -> LeaveRequest:
    """
    Approve a leave request with balance deduction and LWP conversion
    
    Args:
        db: Database session
        leave_request_id: ID of leave request to approve
        approver: Employee approving the leave
        remarks: Optional remarks
    
    Returns:
        Updated LeaveRequest instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Get leave request
    leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request with id {leave_request_id} not found"
        )
    
    # Validate status is PENDING
    if leave_request.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve leave request with status {leave_request.status.value}"
        )
    
    # Validate approval authority
    validate_approval_authority(db, leave_request, approver)
    
    # Re-run policy validations at approval time (unless override is enabled)
    # Get employee
    employee = db.query(Employee).filter(Employee.id == leave_request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # Get policy settings
    year = leave_request.from_date.year
    settings = get_or_create_policy_settings(db, year)
    today = date.today()
    
    # If override_policy is true, validate that approver is HR and remark is present
    if leave_request.override_policy:
        if approver.role != Role.HR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR can approve leave requests with override_policy enabled"
            )
        if not leave_request.override_remark or not leave_request.override_remark.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="override_remark is required when override_policy is true"
            )
    else:
        # Re-run validations (probation and notice use from_date, so they may have changed)
        # COMPOFF is exempt from probation, notice, and monthly cap
        if leave_request.leave_type != LeaveType.COMPOFF:
            # Note: from_date might be in the past now, so notice validation might fail
            # We'll skip notice validation if from_date is in the past (already applied)
            if leave_request.from_date >= today:
                validate_notice(leave_request.leave_type, leave_request.from_date, settings, today, False)
            
            # Use new PL eligibility rule (replaces probation lock)
            validate_pl_eligibility(employee, leave_request.leave_type, leave_request.from_date, settings, today, False)
            
            # Validate monthly cap (exclude current request from existing totals)
            if leave_request.computed_days_by_month:
                try:
                    by_month = json.loads(leave_request.computed_days_by_month)
                    validate_monthly_cap(db, leave_request.employee_id, by_month, settings, year, exclude_leave_request_id=leave_request_id)
                except (json.JSONDecodeError, TypeError):
                    # If JSON parsing fails, skip monthly cap validation
                    pass
    
    # Handle balance deduction and LWP conversion
    total_days = float(leave_request.computed_days)
    paid_days = Decimal('0')
    lwp_days = Decimal('0')

    if leave_request.leave_type == LeaveType.LWP:
        paid_days = Decimal('0')
        lwp_days = Decimal(str(total_days))
    elif leave_request.leave_type == LeaveType.COMPOFF:
        today = date.today()
        paid_days, lwp_days = consume_compoff_on_leave_approval(
            db=db,
            employee_id=leave_request.employee_id,
            leave_request_id=leave_request.id,
            required_days=total_days,
            today=today
        )
    elif leave_request.leave_type in WALLET_LEAVE_TYPES:
        # Wallet: deduct and set paid_days/lwp_days, approver/remark/at
        wallet.apply_leave_approval(db, leave_request_id, approver.id, remarks)
        db.refresh(leave_request)
        paid_days = leave_request.paid_days
        lwp_days = leave_request.lwp_days
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown leave type {leave_request.leave_type}",
        )

    # Update leave request status (wallet already set approver/remark/at for CL/SL/PL/RH)
    before_status = leave_request.status.value
    leave_request.status = LeaveStatus.APPROVED
    leave_request.paid_days = paid_days
    leave_request.lwp_days = lwp_days
    if leave_request.leave_type not in WALLET_LEAVE_TYPES:
        leave_request.approver_id = approver.id
        leave_request.approved_remark = remarks
        leave_request.approved_at = datetime.utcnow()
    logger.info(
        "leave status transition: leave_request_id=%s before=%s after=APPROVED action=approve",
        leave_request_id, before_status,
    )

    # Create approval record
    approval = LeaveApproval(
        leave_request_id=leave_request.id,
        action_by=approver.id,
        action=ApprovalAction.APPROVE,
        remarks=remarks
    )
    db.add(approval)
    db.commit()
    db.refresh(leave_request)
    db.refresh(approval)
    
    # Log audit
    audit_action = "LEAVE_APPROVE_COMPOFF" if leave_request.leave_type == LeaveType.COMPOFF else "LEAVE_APPROVE"
    audit_meta = {
        "leave_request_id": leave_request.id,
        "employee_id": leave_request.employee_id,
        "leave_type": leave_request.leave_type.value,
        "paid_days": float(paid_days),
        "lwp_days": float(lwp_days),
        "remarks": remarks
    }
    
    if leave_request.override_policy:
        audit_meta["override_policy"] = True
        audit_meta["override_remark"] = leave_request.override_remark
    
    log_audit(
        db=db,
        actor_id=approver.id,
        action=audit_action,
        entity_type="leave_requests",
        entity_id=leave_request.id,
        meta=audit_meta
    )
    
    return leave_request


def reject_leave(
    db: Session,
    leave_request_id: int,
    approver: Employee,
    remarks: str
) -> LeaveRequest:
    """
    Reject a leave request
    
    Args:
        db: Database session
        leave_request_id: ID of leave request to reject
        approver: Employee rejecting the leave
        remarks: Remarks for rejection (required)
    
    Returns:
        Updated LeaveRequest instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Get leave request
    leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave request with id {leave_request_id} not found"
        )
    
    if leave_request.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject leave request with status {leave_request.status.value}"
        )
    validate_approval_authority(db, leave_request, approver)

    before_status = leave_request.status.value
    wallet.apply_leave_rejection(db, leave_request_id, approver.id, remarks)
    db.refresh(leave_request)
    logger.info(
        "leave status transition: leave_request_id=%s before=%s after=REJECTED action=reject",
        leave_request_id, before_status,
    )

    approval = LeaveApproval(
        leave_request_id=leave_request.id,
        action_by=approver.id,
        action=ApprovalAction.REJECT,
        remarks=remarks
    )
    db.add(approval)
    db.commit()
    db.refresh(leave_request)
    db.refresh(approval)

    # Log audit
    log_audit(
        db=db,
        actor_id=approver.id,
        action="LEAVE_REJECT",
        entity_type="leave_requests",
        entity_id=leave_request.id,
        meta={
            "leave_request_id": leave_request.id,
            "employee_id": leave_request.employee_id,
            "leave_type": leave_request.leave_type.value,
            "remarks": remarks
        }
    )

    return leave_request


def list_pending_for_approver(
    db: Session,
    current_user: Employee
) -> List[LeaveRequest]:
    """
    List pending leave requests for the current user based on role_rank and reporting hierarchy
    
    Args:
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        List of pending LeaveRequest instances
    
    Role_rank-based scoping:
        - ADMIN (rank=1) and MD (rank=2): all pending requests across all departments
        - VP (rank=3) and MANAGER (rank=4): pending requests for hierarchical subordinates (recursive)
        - EMPLOYEE (rank=5+): empty list (cannot approve)
    """
    query = db.query(LeaveRequest).options(
        joinedload(LeaveRequest.employee),
        joinedload(LeaveRequest.approver),
        joinedload(LeaveRequest.rejected_by),
        joinedload(LeaveRequest.cancelled_by)
    ).filter(LeaveRequest.status == LeaveStatus.PENDING)

    # Get current user's role_rank for permission checking
    current_user_rank = get_role_rank(db, current_user)
    
    # ADMIN (rank=1) and MD (rank=2) can see all pending requests across all departments
    if current_user_rank <= 2:
        pass  # No additional filtering needed
    
    # VP (rank=3) and MANAGER (rank=4) can see pending requests for hierarchical subordinates (recursive)
    elif current_user_rank <= 4:
        # Get all subordinate IDs in the hierarchy (recursive, all departments)
        subordinate_ids = get_subordinate_ids(db, current_user.id)
        
        if subordinate_ids:
            # Show leaves from hierarchical subordinates (recursive reporting tree)
            query = query.filter(LeaveRequest.employee_id.in_(subordinate_ids))
        else:
            # No subordinates, return empty list
            query = query.filter(LeaveRequest.employee_id == -1)  # Force empty result
    
    else:
        # EMPLOYEE (rank=5+) and other roles: empty list (cannot approve)
        query = query.filter(LeaveRequest.employee_id == -1)  # Force empty result
    
    # Order by applied_at ascending (oldest first, so approvers see oldest requests first)
    return query.order_by(LeaveRequest.applied_at.asc()).all()
