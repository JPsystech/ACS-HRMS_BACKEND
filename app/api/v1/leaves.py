"""
Leave endpoints
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.models.leave import WALLET_LEAVE_TYPES
from app.schemas.leave import (
    LeaveApplyRequest,
    LeaveOut,
    LeaveListResponse,
    LeaveListItemOut,
    ApprovalActionRequest,
    RejectActionRequest,
    BalanceMeResponse,
    BalanceSummaryMeResponse,
    BalanceItemOut,
    BalanceSummaryItemOut,
    BalanceTypeOut,
)
from app.services.leave_service import (
    apply_leave,
    list_leaves,
    approve_leave,
    reject_leave,
    list_pending_for_approver
)
from app.services import leave_wallet_service as wallet

router = APIRouter()


@router.get("/balance/me", response_model=BalanceMeResponse)
async def balance_me(
    year: int = Query(..., description="Calendar year (e.g. 2026)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Get current user's leave balances for the year.
    Returns total_entitlement, opening, accrued, used, remaining, eligible (PL only), notes.
    """
    balances = wallet.get_wallet_balances(db, current_user.id, year)
    employee = current_user
    acc = wallet.compute_accrual(db, employee, year)
    items = []
    balances_dict = {}
    for b in balances:
        if b.leave_type not in WALLET_LEAVE_TYPES:
            continue
        info = acc.get(b.leave_type, {})
        eligible = info.get("eligible", True)
        notes = None
        if b.leave_type.value == "PL" and not eligible:
            notes = "PL usable only after 6 months from join date"
        allocated = float(info.get("total_entitlement", 0)) + float(b.opening) + float(b.carry_forward)
        items.append(
            BalanceItemOut(
                leave_type=b.leave_type,
                total_entitlement=float(info.get("total_entitlement", 0)),
                opening=float(b.opening),
                accrued=float(b.accrued),
                used=float(b.used),
                remaining=float(b.remaining),
                eligible=eligible,
                notes=notes,
            )
        )
        balances_dict[b.leave_type.value] = BalanceTypeOut(
            allocated=allocated,
            used=float(b.used),
            remaining=float(b.remaining),
            entitled=allocated,
            available=float(b.remaining),
        )
    return BalanceMeResponse(year=year, employee_id=current_user.id, items=items, balances=balances_dict)


@router.get("/balance/summary/me", response_model=BalanceSummaryMeResponse)
async def balance_summary_me(
    year: int = Query(..., description="Calendar year (e.g. 2026)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Shorter balance summary for current user."""
    balances = wallet.get_wallet_balances(db, current_user.id, year)
    acc = wallet.compute_accrual(db, current_user, year)
    items = []
    for b in balances:
        if b.leave_type not in WALLET_LEAVE_TYPES:
            continue
        info = acc.get(b.leave_type, {})
        items.append(
            BalanceSummaryItemOut(
                leave_type=b.leave_type,
                remaining=float(b.remaining),
                used=float(b.used),
                eligible=info.get("eligible", True),
            )
        )
    return BalanceSummaryMeResponse(year=year, items=items)


@router.post("/apply", response_model=LeaveOut, status_code=201)
async def apply_leave_endpoint(
    leave_data: LeaveApplyRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Apply for leave (creates PENDING request)
    
    Any authenticated user (EMPLOYEE, MANAGER, HR) can apply for leave for themselves only.
    Requires valid JWT token.
    
    Validations:
    - Date order (from_date <= to_date)
    - Leave year (both dates in same calendar year)
    - Overlap prevention (no overlap with PENDING/APPROVED leaves)
    - Day calculation excludes Sundays and holidays
    """
    leave_request = apply_leave(
        db=db,
        employee_id=current_user.id,
        leave_type=leave_data.leave_type,
        from_date=leave_data.from_date,
        to_date=leave_data.to_date,
        reason=leave_data.reason,
        override_policy=getattr(leave_data, 'override_policy', False),
        override_remark=getattr(leave_data, 'override_remark', None),
        current_user=current_user
    )
    
    return leave_request


@router.get("/my", response_model=LeaveListResponse)
async def list_my_leaves_endpoint(
    from_date: Optional[date] = Query(None, alias="from", description="Start date filter (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, alias="to", description="End date filter (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    List current user's leave requests (all statuses including CANCELLED).
    Cancelled leaves return status=CANCELLED with cancel_remark, cancelled_by, cancelled_at.
    Never returns PENDING for a leave that was cancelled (status is CANCELLED).
    """
    leave_requests = list_leaves(
        db=db,
        current_user=current_user,
        from_date=from_date,
        to_date=to_date,
        employee_id=current_user.id,  # only own leaves
    )
    return LeaveListResponse(
        items=[LeaveListItemOut.from_orm(req) for req in leave_requests],
        total=len(leave_requests)
    )


@router.get("/list", response_model=LeaveListResponse)
async def list_leaves_endpoint(
    from_date: Optional[date] = Query(None, alias="from", description="Start date filter (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, alias="to", description="End date filter (YYYY-MM-DD)"),
    employee_id: Optional[int] = Query(None, description="Employee ID filter (for HR/Manager)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    List leave requests with role-based scoping
    
    - HR: can list all employees
    - MANAGER: can list only direct reportees (employees.reporting_manager_id == manager.id)
    - EMPLOYEE: only their own records
    
    Requires valid JWT token.
    """
    leave_requests = list_leaves(
        db=db,
        current_user=current_user,
        from_date=from_date,
        to_date=to_date,
        employee_id=employee_id
    )
    
    return LeaveListResponse(
        items=[LeaveListItemOut.from_orm(req) for req in leave_requests],
        total=len(leave_requests)
    )


@router.post("/{leave_request_id}/approve", response_model=LeaveOut)
async def approve_leave_endpoint(
    leave_request_id: int,
    approval_data: ApprovalActionRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Approve a leave request
    
    Approval authority based on reporting hierarchy:
    - ADMIN (rank=1) and MD (rank=2): can approve any leave across all departments
    - VP (rank=3) and MANAGER (rank=4): can approve only leaves of hierarchical subordinates (direct + indirect reports)
    - Employee cannot approve their own leave
    
    On approval:
    - Balance is deducted (for CL/PL/SL/RH)
    - Excess days are converted to LWP if balance is insufficient
    - Leave status changes to APPROVED
    - Approval history is recorded
    
    Approval is controlled by reporting hierarchy, not department boundaries.
    Requires valid JWT token.
    """
    leave_request = approve_leave(
        db=db,
        leave_request_id=leave_request_id,
        approver=current_user,
        remarks=approval_data.remarks
    )
    
    return leave_request


@router.post("/{leave_request_id}/reject", response_model=LeaveOut)
async def reject_leave_endpoint(
    leave_request_id: int,
    reject_data: RejectActionRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Reject a leave request
    
    Approval authority same as approve:
    - ADMIN (rank=1) and MD (rank=2): can reject any leave across all departments
    - VP (rank=3) and MANAGER (rank=4): can reject only leaves of hierarchical subordinates (direct + indirect reports)
    - Employee cannot reject their own leave
    
    On rejection:
    - Leave status changes to REJECTED
    - No balance deduction
    - Rejection history is recorded
    
    Rejection is controlled by reporting hierarchy, not department boundaries.
    Requires valid JWT token.
    """
    leave_request = reject_leave(
        db=db,
        leave_request_id=leave_request_id,
        approver=current_user,
        remarks=reject_data.remarks
    )
    
    return leave_request


@router.get("/pending", response_model=LeaveListResponse)
async def list_pending_leaves_endpoint(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    List pending leave requests for approval
    
    Role-based scoping based on reporting hierarchy:
    - ADMIN (rank=1) and MD (rank=2): all pending requests across all departments
    - VP (rank=3) and MANAGER (rank=4): pending requests of hierarchical subordinates (direct + indirect reports)
    - EMPLOYEE (rank=5+): empty list (cannot approve)
    
    Visibility is controlled by reporting hierarchy, not department boundaries.
    Requires valid JWT token.
    """
    pending_requests = list_pending_for_approver(db=db, current_user=current_user)
    
    return LeaveListResponse(
        items=[LeaveListItemOut.from_orm(req) for req in pending_requests],
        total=len(pending_requests)
    )
