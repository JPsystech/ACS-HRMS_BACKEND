"""
WFH (Work From Home) API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.schemas.wfh import (
    WFHApplyRequest,
    WFHRequestOut,
    WFHActionRequest,
    WFHListResponse,
    WFHBalanceMeOut,
)
from app.services.wfh_service import (
    apply_wfh,
    approve_wfh,
    reject_wfh,
    list_wfh_requests,
    list_pending_wfh_requests,
    compute_employee_wfh_balance,
)

router = APIRouter()


@router.post("/apply", response_model=WFHRequestOut, status_code=status.HTTP_201_CREATED)
async def apply_wfh_request(
    wfh_data: WFHApplyRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Apply for WFH (any authenticated user)"""
    wfh_request = apply_wfh(
        db=db,
        employee_id=current_user.id,
        request_date=wfh_data.request_date,
        reason=wfh_data.reason
    )
    return wfh_request


@router.get("/my", response_model=WFHListResponse)
async def get_my_wfh_requests(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Get current user's WFH requests"""
    requests = list_wfh_requests(
        db=db,
        current_user=current_user,
        from_date=from_date,
        to_date=to_date
    )
    return WFHListResponse(items=requests, total=len(requests))


@router.get("/balance/me", response_model=WFHBalanceMeOut)
async def get_my_wfh_balance(
    year: int = Query(..., description="Calendar year, e.g. 2026"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Get current user's WFH balance summary for a year.

    Response:
    {
      "year": 2026,
      "entitled": 12,
      "accrued": <credited>,
      "used": <approved_count>,
      "remaining": <accrued - used>
    }
    """
    entitled, accrued, used, remaining = compute_employee_wfh_balance(
        db, employee_id=current_user.id, year=year
    )
    return WFHBalanceMeOut(
        year=year,
        entitled=entitled,
        accrued=accrued,
        used=used,
        remaining=remaining,
    )


@router.get("/pending", response_model=WFHListResponse)
async def get_pending_wfh_requests(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Get pending WFH requests for approval (Manager/HR)"""
    requests = list_pending_wfh_requests(db=db, current_user=current_user)
    return WFHListResponse(items=requests, total=len(requests))


@router.post("/{wfh_id}/approve", response_model=WFHRequestOut)
async def approve_wfh_request(
    wfh_id: int,
    action_data: WFHActionRequest = Body(default={}),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Approve WFH request (reporting manager, HR, or Admin)"""
    wfh_request = approve_wfh(
        db=db,
        wfh_request_id=wfh_id,
        approver=current_user,
        remarks=action_data.remarks,
    )
    return wfh_request


@router.post("/{wfh_id}/reject", response_model=WFHRequestOut)
async def reject_wfh_request(
    wfh_id: int,
    action_data: WFHActionRequest = Body(default={}),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Reject WFH request (reporting manager, HR, or Admin)"""
    wfh_request = reject_wfh(
        db=db,
        wfh_request_id=wfh_id,
        approver=current_user,
        remarks=action_data.remarks or "",
    )
    return wfh_request
