"""
HR Policy Actions service - records penalties and administrative actions
Per FINAL PDF:
- Unauthorized leave penalties: deduct 3 PL
- Medical leave >1 day without certificate: penalty
- Absent >3 days without info: mark as absconded
- Company can cancel approved CL/PL: re-credit/adjust as per management
"""
import logging
from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from decimal import Decimal
from fastapi import HTTPException, status
from app.models.hr_actions import HRPolicyAction, HRPolicyActionType
from app.models.leave import LeaveRequest, LeaveStatus, LeaveType
from app.models.employee import Employee, Role
from app.services.audit_service import log_audit
from app.utils.json_serializer import sanitize_for_json

logger = logging.getLogger(__name__)


def create_hr_action(
    db: Session,
    employee_id: int,
    action_type: HRPolicyActionType,
    action_by: Employee,
    reference_entity_type: Optional[str] = None,
    reference_entity_id: Optional[int] = None,
    meta_json: Optional[Dict[str, Any]] = None,
    remarks: Optional[str] = None
) -> HRPolicyAction:
    """
    Create an HR policy action record.
    
    Only HR can create policy actions.
    
    Args:
        db: Database session
        employee_id: Employee ID affected
        action_type: Type of action
        action_by: HR employee performing action
        reference_entity_type: Optional entity type (e.g., "leave_requests")
        reference_entity_id: Optional entity ID
        meta_json: Optional metadata dictionary
        remarks: Optional remarks
    
    Returns:
        Created HRPolicyAction instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Only HR can create policy actions
    if action_by.role != Role.HR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR can create policy actions"
        )
    
    # Verify employee exists
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found"
        )
    
    # Create action record (sanitize meta_json for JSON column)
    hr_action = HRPolicyAction(
        employee_id=employee_id,
        action_type=action_type,
        reference_entity_type=reference_entity_type,
        reference_entity_id=reference_entity_id,
        meta_json=sanitize_for_json(meta_json) if meta_json is not None else None,
        action_by=action_by.id,
        remarks=remarks
    )
    
    db.add(hr_action)
    db.commit()
    db.refresh(hr_action)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=action_by.id,
        action="HR_POLICY_ACTION",
        entity_type="hr_policy_actions",
        entity_id=hr_action.id,
        meta={
            "employee_id": employee_id,
            "action_type": action_type.value,
            "reference_entity_type": reference_entity_type,
            "reference_entity_id": reference_entity_id
        }
    )
    
    return hr_action


def deduct_pl_penalty(
    db: Session,
    employee_id: int,
    action_by: Employee,
    days: int = 3,
    remarks: Optional[str] = None,
    reference_entity_type: Optional[str] = None,
    reference_entity_id: Optional[int] = None
) -> HRPolicyAction:
    """
    Deduct PL as penalty (e.g., unauthorized leave).
    
    Per FINAL PDF: If leave not approved / explanation not satisfactory -> deduct 3 PL.
    
    Args:
        db: Database session
        employee_id: Employee ID
        action_by: HR employee
        days: Number of days to deduct (default 3)
        remarks: Optional remarks
        reference_entity_type: Optional reference entity type
        reference_entity_id: Optional reference entity ID
    
    Returns:
        Created HRPolicyAction instance
    """
    from app.services import leave_wallet_service as wallet
    from app.models.leave import LeaveBalance, LeaveTransaction, LeaveTransactionAction

    year = date.today().year
    wallet.ensure_wallet_for_employee(db, employee_id, year)
    pl_balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.year == year,
        LeaveBalance.leave_type == LeaveType.PL,
    ).first()
    if not pl_balance:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No PL balance row found for employee"
        )
    before_remaining = float(pl_balance.remaining)
    pl_balance.used = pl_balance.used + Decimal(str(days))
    pl_balance.remaining = pl_balance.opening + pl_balance.accrued + pl_balance.carry_forward - pl_balance.used
    t = LeaveTransaction(
        employee_id=employee_id,
        leave_id=None,
        year=year,
        leave_type=LeaveType.PL,
        delta_days=Decimal(str(-days)),
        action=LeaveTransactionAction.MANUAL_ADJUST.value,
        remarks=remarks or "PL penalty deduction",
        action_by_employee_id=action_by.id,
    )
    db.add(t)
    db.commit()
    db.refresh(pl_balance)

    meta_json = {
        "deducted_days": days,
        "pl_remaining_before": before_remaining,
        "pl_remaining_after": float(pl_balance.remaining),
        "year": year
    }
    
    hr_action = create_hr_action(
        db=db,
        employee_id=employee_id,
        action_type=HRPolicyActionType.DEDUCT_PL_3,
        action_by=action_by,
        reference_entity_type=reference_entity_type,
        reference_entity_id=reference_entity_id,
        meta_json=meta_json,
        remarks=remarks or f"Deducted {days} PL as policy penalty"
    )
    
    return hr_action


def cancel_approved_leave(
    db: Session,
    leave_request_id: int,
    action_by: Employee,
    recredit: bool = False,
    remarks: Optional[str] = None
) -> HRPolicyAction:
    """
    Cancel approved leave (company can cancel approved CL/PL in emergency).

    Does NOT delete the leave record: it is kept in history with status CANCELLED (never PENDING).
    Does NOT overwrite the employee's original reason.
    List APIs (/leaves/list, /leaves/my) return all statuses including CANCELLED.

    Per FINAL PDF: Company can cancel approved CL/PL in emergency (HR-only action).
    Re-credit/adjust as per management (store recredit decision).

    Args:
        db: Database session
        leave_request_id: Leave request ID to cancel
        action_by: HR employee
        recredit: Whether to re-credit paid days back to balance
        remarks: Optional remarks (stored as cancelled_remark)

    Returns:
        Created HRPolicyAction instance

    Raises:
        HTTPException: If validation fails
    """
    leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found"
        )
    
    if leave_request.status != LeaveStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel leave request with status {leave_request.status.value}. Only APPROVED leaves can be cancelled."
        )
    
    if leave_request.leave_type not in (LeaveType.CL, LeaveType.PL):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CL and PL leaves can be cancelled by company"
        )

    from app.services import leave_wallet_service as wallet
    wallet.apply_leave_cancel(db, leave_request_id, action_by.id, remarks, recredit=recredit)
    db.refresh(leave_request)
    logger.info(
        "leave status transition: leave_request_id=%s before=APPROVED after=CANCELLED action=cancel",
        leave_request_id,
    )

    # Create action record
    meta_json = {
        "leave_request_id": leave_request_id,
        "leave_type": leave_request.leave_type.value,
        "from_date": str(leave_request.from_date),
        "to_date": str(leave_request.to_date),
        "paid_days": float(leave_request.paid_days),
        "recredit": recredit
    }
    
    hr_action = create_hr_action(
        db=db,
        employee_id=leave_request.employee_id,
        action_type=HRPolicyActionType.CANCEL_APPROVED_LEAVE,
        action_by=action_by,
        reference_entity_type="leave_requests",
        reference_entity_id=leave_request_id,
        meta_json=meta_json,
        remarks=remarks or f"Company cancelled approved {leave_request.leave_type.value} leave"
    )
    
    # Also create leave approval record for cancellation (leave status already committed)
    from app.models.leave import LeaveApproval, ApprovalAction
    approval = LeaveApproval(
        leave_request_id=leave_request_id,
        action_by=action_by.id,
        action=ApprovalAction.CANCEL,
        remarks=remarks or "Cancelled by company"
    )
    db.add(approval)
    db.commit()
    # Re-fetch leave to confirm status was not overwritten (must be CANCELLED, never PENDING)
    leave_check = db.query(LeaveRequest).filter(LeaveRequest.id == leave_request_id).first()
    if leave_check and leave_check.status != LeaveStatus.CANCELLED:
        logger.error(
            "leave status overwritten after cancel: leave_request_id=%s expected=CANCELLED got=%s",
            leave_request_id, leave_check.status.value,
        )
    return hr_action


def list_hr_actions(
    db: Session,
    current_user: Employee,
    employee_id: Optional[int] = None,
    action_type: Optional[HRPolicyActionType] = None
) -> List[HRPolicyAction]:
    """
    List HR policy actions with role-based scope.
    
    - HR: all actions
    - MANAGER: actions for direct reportees only
    - EMPLOYEE: own actions only
    
    Args:
        db: Database session
        current_user: Current authenticated user
        employee_id: Optional employee ID filter
        action_type: Optional action type filter
    
    Returns:
        List of HRPolicyAction instances
    """
    query = db.query(HRPolicyAction)
    
    # Apply role-based scope
    if current_user.role == Role.HR:
        # HR can see all
        if employee_id:
            query = query.filter(HRPolicyAction.employee_id == employee_id)
    elif current_user.role == Role.MANAGER:
        # Manager sees only direct reportees
        reportee_ids = db.query(Employee.id).filter(
            Employee.reporting_manager_id == current_user.id
        ).subquery()
        query = query.filter(HRPolicyAction.employee_id.in_(reportee_ids))
        if employee_id and employee_id in [r[0] for r in db.query(Employee.id).filter(
            Employee.reporting_manager_id == current_user.id
        ).all()]:
            query = query.filter(HRPolicyAction.employee_id == employee_id)
    else:
        # Employee sees only own
        query = query.filter(HRPolicyAction.employee_id == current_user.id)
    
    # Apply action type filter
    if action_type:
        query = query.filter(HRPolicyAction.action_type == action_type)
    
    return query.order_by(HRPolicyAction.action_at.desc()).all()
