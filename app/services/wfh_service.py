"""
WFH (Work From Home) service
Per FINAL PDF:
- Max 12 days/year
- If WFH approved -> counts as 0.5 day
- If WFH not allowed -> treated as leave (do not auto-convert; let approver/HR decide)
"""
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException, status
from decimal import Decimal
from app.models.wfh import WFHRequest, WFHStatus
from app.models.employee import Employee, Role
from app.models.role import RoleModel
from app.models.policy import PolicySetting
from app.services.audit_service import log_audit
from app.services.policy_validator import get_or_create_policy_settings


def validate_wfh_yearly_cap(
    db: Session,
    employee_id: int,
    request_date: date,
    exclude_wfh_id: Optional[int] = None
) -> None:
    """
    Validate WFH yearly cap (12 days/year per FINAL PDF).
    
    Args:
        db: Database session
        employee_id: Employee ID
        request_date: WFH request date
        exclude_wfh_id: WFH request ID to exclude from count (for updates)
    
    Raises:
        HTTPException: If yearly cap exceeded
    """
    year = request_date.year
    
    # Get policy settings
    settings = get_or_create_policy_settings(db, year)
    wfh_max_days = settings.wfh_max_days if hasattr(settings, 'wfh_max_days') else 12
    
    # Count approved WFH requests for this year
    query = db.query(WFHRequest).filter(
        WFHRequest.employee_id == employee_id,
        WFHRequest.status == WFHStatus.APPROVED,
        WFHRequest.request_date >= date(year, 1, 1),
        WFHRequest.request_date <= date(year, 12, 31)
    )
    
    if exclude_wfh_id:
        query = query.filter(WFHRequest.id != exclude_wfh_id)
    
    approved_count = query.count()
    
    if approved_count >= wfh_max_days:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"WFH yearly cap exceeded. Maximum {wfh_max_days} WFH days per year allowed. "
                   f"Already approved: {approved_count} days."
        )


def compute_employee_wfh_balance(
    db: Session,
    employee_id: int,
    year: int,
) -> Tuple[int, int, int, int]:
    """
    Compute WFH balance for a specific employee and year.

    Returns (entitled, accrued, used, remaining).
    """
    # Entitled from policy (fallback 12)
    settings: PolicySetting = get_or_create_policy_settings(db, year)
    entitled = getattr(settings, "wfh_max_days", 12)

    # Used: count of APPROVED WFH requests for this employee in that year
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    used = (
        db.query(WFHRequest)
        .filter(
            WFHRequest.employee_id == employee_id,
            WFHRequest.status == WFHStatus.APPROVED,
            WFHRequest.request_date >= start,
            WFHRequest.request_date <= end,
        )
        .count()
    )

    # Accrued: if year == current year, 1 day per month elapsed; else full entitlement
    now_utc = datetime.now(timezone.utc)
    current_year = now_utc.year
    if year != current_year:
        accrued = entitled
    else:
        current_month = now_utc.month  # 1-12
        accrued = min(current_month, entitled)

    remaining = max(0, accrued - used)
    return entitled, accrued, used, remaining


def apply_wfh(
    db: Session,
    employee_id: int,
    request_date: date,
    reason: Optional[str] = None
) -> WFHRequest:
    """
    Apply for WFH (creates PENDING request).
    
    Args:
        db: Database session
        employee_id: Employee ID applying for WFH
        request_date: WFH date
        reason: Optional reason
    
    Returns:
        Created WFHRequest instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Get employee
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found"
        )

    # Enforce work mode WFH policy:
    # - If employee.work_mode == 'SITE', block WFH requests
    if employee.work_mode == "SITE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WFH is not allowed for Site employees."
        )

    # Enforce role-based WFH enablement:
    # - Look up matching role in roles master by name
    # - If not found or wfh_enabled is False, block the request
    role_row = (
        db.query(RoleModel)
        .filter(
            RoleModel.name == employee.role.value,
            RoleModel.is_active == True,
        )
        .first()
    )
    if not role_row or not role_row.wfh_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="WFH is not allowed for your role",
        )
    
    # Check for duplicate request
    existing = db.query(WFHRequest).filter(
        WFHRequest.employee_id == employee_id,
        WFHRequest.request_date == request_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"WFH request already exists for date {request_date}"
        )
    
    # Validate yearly cap (check approved count)
    validate_wfh_yearly_cap(db, employee_id, request_date)
    
    # Get policy settings for day_value
    year = request_date.year
    settings = get_or_create_policy_settings(db, year)
    day_value = Decimal(str(settings.wfh_day_value)) if hasattr(settings, 'wfh_day_value') else Decimal('0.5')
    
    # Create WFH request
    wfh_request = WFHRequest(
        employee_id=employee_id,
        request_date=request_date,
        reason=reason,
        status=WFHStatus.PENDING,
        day_value=day_value,
        applied_at=datetime.now(timezone.utc)
    )
    
    db.add(wfh_request)
    db.commit()
    db.refresh(wfh_request)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=employee_id,
        action="WFH_REQUEST",
        entity_type="wfh_requests",
        entity_id=wfh_request.id,
        meta={
            "request_date": str(request_date),
            "day_value": float(day_value)
        }
    )
    
    return wfh_request


def approve_wfh(
    db: Session,
    wfh_request_id: int,
    approver: Employee,
    remarks: Optional[str] = None
) -> WFHRequest:
    """
    Approve WFH request.
    
    Authority:
    - Direct reporting manager OR HR can approve
    
    Args:
        db: Database session
        wfh_request_id: WFH request ID
        approver: Approver employee
        remarks: Optional remarks
    
    Returns:
        Updated WFHRequest instance
    
    Raises:
        HTTPException: If validation fails
    """
    wfh_request = db.query(WFHRequest).filter(WFHRequest.id == wfh_request_id).first()
    if not wfh_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WFH request not found"
        )
    
    if wfh_request.status != WFHStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve WFH request with status {wfh_request.status.value}"
        )
    
    # Validate approval authority
    employee = db.query(Employee).filter(Employee.id == wfh_request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # Approval hierarchy:
    # - HR or ADMIN can approve any WFH
    # - Reporting manager can approve their direct reportees
    # - Others cannot approve
    if approver.role not in (Role.HR, Role.ADMIN):
        if employee.reporting_manager_id != approver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to approve this WFH"
            )
    
    # Cannot approve own request
    if approver.id == employee.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot approve own WFH request"
        )
    
    # Validate yearly cap again (in case it changed)
    validate_wfh_yearly_cap(db, employee.id, wfh_request.request_date, exclude_wfh_id=wfh_request_id)
    
    # Approve
    wfh_request.status = WFHStatus.APPROVED
    wfh_request.approved_by = approver.id
    wfh_request.approved_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(wfh_request)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=approver.id,
        action="WFH_APPROVE",
        entity_type="wfh_requests",
        entity_id=wfh_request.id,
        meta={
            "employee_id": employee.id,
            "request_date": str(wfh_request.request_date),
            "day_value": float(wfh_request.day_value)
        }
    )
    
    return wfh_request


def reject_wfh(
    db: Session,
    wfh_request_id: int,
    approver: Employee,
    remarks: str
) -> WFHRequest:
    """
    Reject WFH request.
    
    Authority: Same as approve
    
    Args:
        db: Database session
        wfh_request_id: WFH request ID
        approver: Approver employee
        remarks: Required remarks
    
    Returns:
        Updated WFHRequest instance
    """
    wfh_request = db.query(WFHRequest).filter(WFHRequest.id == wfh_request_id).first()
    if not wfh_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WFH request not found"
        )
    
    if wfh_request.status != WFHStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject WFH request with status {wfh_request.status.value}"
        )
    
    # Validate approval authority (same as approve)
    employee = db.query(Employee).filter(Employee.id == wfh_request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    if approver.role not in (Role.HR, Role.ADMIN):
        if employee.reporting_manager_id != approver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to reject this WFH"
            )
    
    # Reject
    wfh_request.status = WFHStatus.REJECTED
    wfh_request.approved_by = approver.id
    wfh_request.approved_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(wfh_request)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=approver.id,
        action="WFH_REJECT",
        entity_type="wfh_requests",
        entity_id=wfh_request.id,
        meta={
            "employee_id": employee.id,
            "request_date": str(wfh_request.request_date),
            "remarks": remarks
        }
    )
    
    return wfh_request


def list_wfh_requests(
    db: Session,
    current_user: Employee,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    employee_id: Optional[int] = None
) -> List[WFHRequest]:
    """
    List WFH requests with role-based scope.
    
    - HR: all requests
    - MANAGER: requests from direct reportees only
    - EMPLOYEE: own requests only
    
    Args:
        db: Database session
        current_user: Current authenticated user
        from_date: Optional start date filter
        to_date: Optional end date filter
        employee_id: Optional employee ID filter (HR only)
    
    Returns:
        List of WFHRequest instances
    """
    query = db.query(WFHRequest)
    
    # Apply role-based scope
    if current_user.role == Role.HR:
        # HR can see all
        if employee_id:
            query = query.filter(WFHRequest.employee_id == employee_id)
    elif current_user.role == Role.MANAGER:
        # Manager sees only direct reportees
        reportee_ids = db.query(Employee.id).filter(
            Employee.reporting_manager_id == current_user.id
        ).subquery()
        query = query.filter(WFHRequest.employee_id.in_(reportee_ids))
        if employee_id and employee_id in [r[0] for r in db.query(Employee.id).filter(
            Employee.reporting_manager_id == current_user.id
        ).all()]:
            query = query.filter(WFHRequest.employee_id == employee_id)
    else:
        # Employee sees only own
        query = query.filter(WFHRequest.employee_id == current_user.id)
    
    # Apply date filters
    if from_date:
        query = query.filter(WFHRequest.request_date >= from_date)
    if to_date:
        query = query.filter(WFHRequest.request_date <= to_date)
    
    return query.order_by(WFHRequest.request_date.desc()).all()


def list_pending_wfh_requests(
    db: Session,
    current_user: Employee
) -> List[WFHRequest]:
    """
    List pending WFH requests for approval.
    
    - HR: all pending
    - MANAGER: pending from direct reportees only
    - EMPLOYEE: empty list
    
    Args:
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        List of pending WFHRequest instances
    """
    query = db.query(WFHRequest).filter(WFHRequest.status == WFHStatus.PENDING)
    
    if current_user.role == Role.HR:
        # HR sees all pending
        pass
    elif current_user.role == Role.MANAGER:
        # Manager sees only direct reportees
        reportee_ids = db.query(Employee.id).filter(
            Employee.reporting_manager_id == current_user.id
        ).subquery()
        query = query.filter(WFHRequest.employee_id.in_(reportee_ids))
    else:
        # Employee sees none
        return []
    
    return query.order_by(WFHRequest.request_date.asc()).all()
