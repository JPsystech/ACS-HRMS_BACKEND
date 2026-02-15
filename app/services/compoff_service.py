"""
Comp-off service - business logic for comp-off management
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func as sql_func
from fastapi import HTTPException, status
from decimal import Decimal
from app.models.compoff import CompoffRequest, CompoffLedger, CompoffRequestStatus, CompoffLedgerType
from app.models.attendance_session import AttendanceSession
from app.models.employee import Employee, Role
from app.models.leave import LeaveRequest
from app.services.audit_service import log_audit
from app.services.holiday_service import get_holidays_in_range

logger = logging.getLogger(__name__)


def is_sunday(check_date: date) -> bool:
    """Check if a date is Sunday (weekly off)"""
    return check_date.weekday() == 6  # Monday=0, Sunday=6


def validate_compoff_eligibility(
    db: Session,
    employee_id: int,
    worked_date: date
) -> None:
    """
    Validate comp-off eligibility with detailed error messages.
    
    Rules:
    - Attendance must exist for (employee_id, worked_date)
    - Both punch-in and punch-out must be present
    - worked_date must be Sunday OR an active holiday
    
    Args:
        db: Database session
        employee_id: Employee ID
        worked_date: Date on which employee worked
    
    Raises:
        HTTPException: With specific error messages for each validation failure
    """
    # Check attendance exists - use same logic as /api/v1/attendance/today
    attendance = db.query(AttendanceSession).filter(
        AttendanceSession.employee_id == employee_id,
        AttendanceSession.work_date == worked_date
    ).first()
    
    # Check if worked_date is Sunday
    is_sunday_flag = is_sunday(worked_date)
    
    # Check if worked_date is an active holiday
    holidays = get_holidays_in_range(db, worked_date, worked_date)
    is_holiday = worked_date in holidays
    
    # Debug logging - detailed troubleshooting info
    logger.debug(
        f"Comp-off validation: employee_id={employee_id}, worked_date={worked_date} (weekday={worked_date.weekday()}), "
        f"is_sunday={is_sunday_flag}, is_holiday={is_holiday}, holidays_found={len(holidays)}"
    )
    
    if attendance:
        logger.debug(
            f"Attendance found: session_id={attendance.id}, "
            f"punch_in_at={attendance.punch_in_at}, punch_out_at={attendance.punch_out_at}, "
            f"work_date={attendance.work_date}, status={attendance.status}"
        )
    else:
        logger.debug(f"No attendance session found for employee {employee_id} on {worked_date}")
        # Additional debug: check if there are any sessions for this employee around this date
        recent_sessions = db.query(AttendanceSession).filter(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.work_date.between(
                worked_date - timedelta(days=3),
                worked_date + timedelta(days=3)
            )
        ).all()
        if recent_sessions:
            logger.debug(f"Found {len(recent_sessions)} recent sessions for employee {employee_id}:")
            for session in recent_sessions:
                logger.debug(f"  - {session.work_date}: {session.punch_in_at} to {session.punch_out_at}")
        else:
            logger.debug(f"No recent sessions found for employee {employee_id}")
    
    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No attendance found for selected date."
        )
    
    if not attendance.punch_in_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Punch-in missing for selected date."
        )
    
    if not attendance.punch_out_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance incomplete (punch-out missing)."
        )
    
    # Check if worked_date is Sunday or holiday
    if not is_sunday_flag and not is_holiday:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comp-off allowed only on Sunday or company holiday."
        )


def request_compoff(
    db: Session,
    employee_id: int,
    worked_date: date,
    reason: Optional[str] = None
) -> CompoffRequest:
    """
    Request comp-off earn for a worked date.
    
    Args:
        db: Database session
        employee_id: Employee ID requesting comp-off
        worked_date: Date on which employee worked
        reason: Optional reason
    
    Returns:
        Created CompoffRequest instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate eligibility with detailed error messages
    validate_compoff_eligibility(db, employee_id, worked_date)
    
    # Check for duplicate request
    existing = db.query(CompoffRequest).filter(
        CompoffRequest.employee_id == employee_id,
        CompoffRequest.worked_date == worked_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Comp-off request already exists for worked date {worked_date}"
        )
    
    # Create request
    compoff_request = CompoffRequest(
        employee_id=employee_id,
        worked_date=worked_date,
        reason=reason,
        status=CompoffRequestStatus.PENDING,
        requested_at=datetime.now(timezone.utc)
    )
    
    db.add(compoff_request)
    db.commit()
    db.refresh(compoff_request)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=employee_id,
        action="COMPOFF_EARN_REQUEST",
        entity_type="compoff_requests",
        entity_id=compoff_request.id,
        meta={
            "worked_date": str(worked_date),
            "reason": reason
        }
    )
    
    return compoff_request


def approve_compoff_request(
    db: Session,
    request_id: int,
    approver: Employee,
    remarks: Optional[str] = None
) -> CompoffRequest:
    """
    Approve a comp-off earn request.
    
    Authority:
    - MANAGER: only if employee.reporting_manager_id == approver.id
    - HR: always
    - Cannot approve own request
    
    Actions:
    - Set status=APPROVED
    - Create ledger CREDIT entry with expiry (worked_date + 60 days)
    
    Args:
        db: Database session
        request_id: Comp-off request ID
        approver: Employee approving the request
        remarks: Optional remarks
    
    Returns:
        Updated CompoffRequest instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Get request
    compoff_request = db.query(CompoffRequest).filter(CompoffRequest.id == request_id).first()
    if not compoff_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comp-off request with id {request_id} not found"
        )
    
    # Validate status
    if compoff_request.status != CompoffRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve comp-off request with status {compoff_request.status.value}"
        )
    
    # Get employee
    employee = db.query(Employee).filter(Employee.id == compoff_request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # Validate approval authority (similar to leave approval)
    if approver.id == compoff_request.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee cannot approve their own comp-off request"
        )
    
    if approver.role == Role.HR:
        pass  # HR can approve
    elif approver.role == Role.MANAGER:
        if employee.reporting_manager_id != approver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the direct reporting manager can approve this comp-off request"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR or direct reporting manager can approve comp-off requests"
        )
    
    # Update status
    compoff_request.status = CompoffRequestStatus.APPROVED
    
    # Create ledger CREDIT entry
    expires_on = compoff_request.worked_date + timedelta(days=60)
    
    ledger_entry = CompoffLedger(
        employee_id=compoff_request.employee_id,
        entry_type=CompoffLedgerType.CREDIT,
        days=Decimal('1.0'),
        worked_date=compoff_request.worked_date,
        expires_on=expires_on,
        reference_id=compoff_request.id
    )
    
    db.add(ledger_entry)
    db.commit()
    db.refresh(compoff_request)
    db.refresh(ledger_entry)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=approver.id,
        action="COMPOFF_EARN_APPROVE",
        entity_type="compoff_requests",
        entity_id=compoff_request.id,
        meta={
            "worked_date": str(compoff_request.worked_date),
            "expires_on": str(expires_on),
            "remarks": remarks
        }
    )
    
    return compoff_request


def reject_compoff_request(
    db: Session,
    request_id: int,
    approver: Employee,
    remarks: Optional[str] = None
) -> CompoffRequest:
    """
    Reject a comp-off earn request.
    
    Authority: Same as approve (direct reporting manager or HR)
    
    Args:
        db: Database session
        request_id: Comp-off request ID
        approver: Employee rejecting the request
        remarks: Optional remarks
    
    Returns:
        Updated CompoffRequest instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Get request
    compoff_request = db.query(CompoffRequest).filter(CompoffRequest.id == request_id).first()
    if not compoff_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comp-off request with id {request_id} not found"
        )
    
    # Validate status
    if compoff_request.status != CompoffRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject comp-off request with status {compoff_request.status.value}"
        )
    
    # Get employee
    employee = db.query(Employee).filter(Employee.id == compoff_request.employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # Validate approval authority (same as approve)
    if approver.id == compoff_request.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee cannot reject their own comp-off request"
        )
    
    if approver.role == Role.HR:
        pass  # HR can reject
    elif approver.role == Role.MANAGER:
        if employee.reporting_manager_id != approver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the direct reporting manager can reject this comp-off request"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR or direct reporting manager can reject comp-off requests"
        )
    
    # Update status
    compoff_request.status = CompoffRequestStatus.REJECTED
    
    db.commit()
    db.refresh(compoff_request)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=approver.id,
        action="COMPOFF_EARN_REJECT",
        entity_type="compoff_requests",
        entity_id=compoff_request.id,
        meta={
            "worked_date": str(compoff_request.worked_date),
            "remarks": remarks
        }
    )
    
    return compoff_request


def get_compoff_balance(
    db: Session,
    employee_id: int,
    today: date
) -> Dict[str, float]:
    """
    Get comp-off balance for an employee.
    
    Calculates:
    - credits: sum of CREDIT entries where expires_on >= today
    - debits: sum of DEBIT entries
    - available: max(0, credits - debits)
    
    Args:
        db: Database session
        employee_id: Employee ID
        today: Current date (for expiry check)
    
    Returns:
        Dictionary with credits, debits, available_days, expired_credits
    """
    # Get credits (not expired)
    credits_query = db.query(sql_func.sum(CompoffLedger.days)).filter(
        CompoffLedger.employee_id == employee_id,
        CompoffLedger.entry_type == CompoffLedgerType.CREDIT,
        CompoffLedger.expires_on >= today
    )
    credits = credits_query.scalar() or Decimal('0')
    
    # Get expired credits (for reference)
    expired_credits_query = db.query(sql_func.sum(CompoffLedger.days)).filter(
        CompoffLedger.employee_id == employee_id,
        CompoffLedger.entry_type == CompoffLedgerType.CREDIT,
        CompoffLedger.expires_on < today
    )
    expired_credits = expired_credits_query.scalar() or Decimal('0')
    
    # Get debits
    debits_query = db.query(sql_func.sum(CompoffLedger.days)).filter(
        CompoffLedger.employee_id == employee_id,
        CompoffLedger.entry_type == CompoffLedgerType.DEBIT
    )
    debits = debits_query.scalar() or Decimal('0')
    
    available = max(Decimal('0'), credits - debits)
    
    return {
        "employee_id": employee_id,
        "credits": float(credits),
        "debits": float(debits),
        "available_days": float(available),
        "expired_credits": float(expired_credits)
    }


def consume_compoff_on_leave_approval(
    db: Session,
    employee_id: int,
    leave_request_id: int,
    required_days: float,
    today: date
) -> Tuple[Decimal, Decimal]:
    """
    Consume comp-off balance when approving a COMPOFF leave request.
    
    Args:
        db: Database session
        employee_id: Employee ID
        leave_request_id: Leave request ID
        required_days: Number of days required (from leave_request.computed_days)
        today: Current date (for expiry check)
    
    Returns:
        Tuple of (paid_days, lwp_days)
        - paid_days: Days covered by comp-off balance
        - lwp_days: Remaining days converted to LWP
    """
    # Get available balance
    balance_info = get_compoff_balance(db, employee_id, today)
    available = Decimal(str(balance_info["available_days"]))
    
    # Calculate paid and LWP
    required = Decimal(str(required_days))
    paid_days = min(required, available)
    lwp_days = max(Decimal('0'), required - paid_days)
    
    # Create DEBIT entry if paid_days > 0
    if paid_days > 0:
        ledger_entry = CompoffLedger(
            employee_id=employee_id,
            entry_type=CompoffLedgerType.DEBIT,
            days=paid_days,
            leave_request_id=leave_request_id
        )
        db.add(ledger_entry)
        db.commit()
        db.refresh(ledger_entry)
    
    return paid_days, lwp_days


def list_compoff_requests(
    db: Session,
    current_user: Employee,
    employee_id: Optional[int] = None
) -> list[CompoffRequest]:
    """
    List comp-off requests with role-based scoping.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        employee_id: Optional employee ID filter
    
    Returns:
        List of CompoffRequest instances
    """
    query = db.query(CompoffRequest)
    
    if current_user.role == Role.HR:
        # HR can see all
        if employee_id:
            query = query.filter(CompoffRequest.employee_id == employee_id)
    elif current_user.role == Role.MANAGER:
        # MANAGER can see only direct reportees
        from app.models.employee import Employee as EmpModel
        reportee_ids = [
            emp_id for (emp_id,) in db.query(EmpModel.id).filter(
                EmpModel.reporting_manager_id == current_user.id
            ).all()
        ]
        
        if employee_id:
            if employee_id not in reportee_ids:
                return []
            query = query.filter(CompoffRequest.employee_id == employee_id)
        else:
            if reportee_ids:
                query = query.filter(CompoffRequest.employee_id.in_(reportee_ids))
            else:
                query = query.filter(CompoffRequest.employee_id == -1)  # Impossible condition
    else:
        # EMPLOYEE can see only their own
        query = query.filter(CompoffRequest.employee_id == current_user.id)
        if employee_id and employee_id != current_user.id:
            return []
    
    return query.order_by(CompoffRequest.requested_at.desc()).all()


def list_pending_compoff_requests(
    db: Session,
    current_user: Employee
) -> list[CompoffRequest]:
    """
    List pending comp-off requests for approval.
    
    Role-based scoping:
    - HR: all pending requests
    - MANAGER: pending requests of direct reportees only
    - EMPLOYEE: empty list (cannot approve)
    
    Args:
        db: Database session
        current_user: Current authenticated user
    
    Returns:
        List of pending CompoffRequest instances
    """
    query = db.query(CompoffRequest).filter(
        CompoffRequest.status == CompoffRequestStatus.PENDING
    )
    
    if current_user.role == Role.HR:
        # HR can see all pending
        pass
    elif current_user.role == Role.MANAGER:
        # MANAGER can see only direct reportees' pending requests
        from app.models.employee import Employee as EmpModel
        reportee_ids = [
            emp_id for (emp_id,) in db.query(EmpModel.id).filter(
                EmpModel.reporting_manager_id == current_user.id
            ).all()
        ]
        
        if reportee_ids:
            query = query.filter(CompoffRequest.employee_id.in_(reportee_ids))
        else:
            query = query.filter(CompoffRequest.employee_id == -1)  # Impossible condition
    else:
        # EMPLOYEE cannot approve, return empty list
        return []
    
    # Order by requested_at ascending (oldest first)
    return query.order_by(CompoffRequest.requested_at.asc()).all()
