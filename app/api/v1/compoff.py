"""
Comp-off management endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.schemas.compoff import (
    CompoffEarnRequest,
    CompoffRequestOut,
    CompoffActionRequest,
    CompoffBalanceOut,
    CompoffListResponse
)
from app.services.compoff_service import (
    request_compoff,
    approve_compoff_request,
    reject_compoff_request,
    get_compoff_balance,
    list_compoff_requests,
    list_pending_compoff_requests
)
from datetime import date

router = APIRouter()


@router.post("/request", response_model=CompoffRequestOut, status_code=201)
async def request_compoff_endpoint(
    compoff_data: CompoffEarnRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Request comp-off earn for a worked date (any authenticated user)
    
    Eligibility:
    - Employee must have attendance (both punch-in and punch-out) on worked_date
    - worked_date must be Sunday OR an active holiday
    
    Requires valid JWT token.
    """
    compoff_request = request_compoff(
        db=db,
        employee_id=current_user.id,
        worked_date=compoff_data.worked_date,
        reason=compoff_data.reason
    )
    
    return compoff_request


@router.get("/my-requests", response_model=CompoffListResponse)
async def list_my_compoff_requests_endpoint(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    List own comp-off requests (any authenticated user)
    
    Returns all comp-off requests for the current user.
    """
    requests = list_compoff_requests(db=db, current_user=current_user)
    
    return CompoffListResponse(
        items=[CompoffRequestOut.from_orm(req) for req in requests],
        total=len(requests)
    )


@router.get("/balance", response_model=CompoffBalanceOut)
async def get_compoff_balance_endpoint(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Get comp-off balance for current user (any authenticated user)
    
    Returns:
    - available_days: Available comp-off days (credits - debits, excluding expired)
    - credits: Total credits (not expired)
    - debits: Total debits
    - expired_credits: Expired credits (for reference)
    """
    balance_info = get_compoff_balance(
        db=db,
        employee_id=current_user.id,
        today=date.today()
    )
    
    return CompoffBalanceOut(**balance_info)


@router.get("/pending", response_model=CompoffListResponse)
async def list_pending_compoff_requests_endpoint(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    List pending comp-off requests for approval
    
    Role-based scoping:
    - HR: all pending requests
    - MANAGER: pending requests of direct reportees only
    - EMPLOYEE: empty list (cannot approve)
    
    Requires valid JWT token.
    """
    pending_requests = list_pending_compoff_requests(db=db, current_user=current_user)
    
    return CompoffListResponse(
        items=[CompoffRequestOut.from_orm(req) for req in pending_requests],
        total=len(pending_requests)
    )


@router.post("/{request_id}/approve", response_model=CompoffRequestOut)
async def approve_compoff_request_endpoint(
    request_id: int,
    approval_data: CompoffActionRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Approve a comp-off earn request
    
    Approval authority:
    - HR can approve any employee's comp-off request
    - MANAGER can approve only direct reportees' comp-off request
    - Employee cannot approve their own comp-off request
    
    On approval:
    - Creates ledger CREDIT entry (1.0 day)
    - Sets expiry date (worked_date + 60 days)
    - Request status changes to APPROVED
    
    Requires valid JWT token.
    """
    compoff_request = approve_compoff_request(
        db=db,
        request_id=request_id,
        approver=current_user,
        remarks=approval_data.remarks
    )
    
    return compoff_request


@router.post("/{request_id}/reject", response_model=CompoffRequestOut)
async def reject_compoff_request_endpoint(
    request_id: int,
    reject_data: CompoffActionRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Reject a comp-off earn request
    
    Approval authority same as approve:
    - HR can reject any employee's comp-off request
    - MANAGER can reject only direct reportees' comp-off request
    - Employee cannot reject their own comp-off request
    
    On rejection:
    - Request status changes to REJECTED
    - No ledger entry created
    
    Requires valid JWT token.
    """
    compoff_request = reject_compoff_request(
        db=db,
        request_id=request_id,
        approver=current_user,
        remarks=reject_data.remarks
    )
    
    return compoff_request
