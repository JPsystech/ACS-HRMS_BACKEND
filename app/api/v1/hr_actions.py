"""
HR Policy Actions API endpoints
HR-only endpoints for recording penalties and administrative actions
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.deps import get_db, get_current_user, require_roles
from app.models.employee import Employee, Role
from app.models.hr_actions import HRPolicyAction, HRPolicyActionType
from app.schemas.hr_actions import (
    HRPolicyActionCreate,
    HRPolicyActionOut,
    HRPolicyActionListResponse,
    CancelLeaveRequest
)
from app.services.hr_actions_service import (
    create_hr_action,
    deduct_pl_penalty,
    cancel_approved_leave,
    list_hr_actions
)

router = APIRouter()


@router.post("", response_model=HRPolicyActionOut, status_code=status.HTTP_201_CREATED)
async def create_hr_policy_action(
    action_data: HRPolicyActionCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """Create an HR policy action (HR only)"""
    hr_action = create_hr_action(
        db=db,
        employee_id=action_data.employee_id,
        action_type=action_data.action_type,
        action_by=current_user,
        reference_entity_type=action_data.reference_entity_type,
        reference_entity_id=action_data.reference_entity_id,
        meta_json=action_data.meta_json,
        remarks=action_data.remarks
    )
    return hr_action


@router.post("/deduct-pl", response_model=HRPolicyActionOut)
async def deduct_pl_penalty_endpoint(
    employee_id: int,
    days: int = Query(3, description="Number of PL days to deduct"),
    remarks: Optional[str] = Query(None, description="Optional remarks"),
    reference_entity_type: Optional[str] = Query(None),
    reference_entity_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """Deduct PL as penalty (e.g., unauthorized leave) - HR only"""
    hr_action = deduct_pl_penalty(
        db=db,
        employee_id=employee_id,
        action_by=current_user,
        days=days,
        remarks=remarks,
        reference_entity_type=reference_entity_type,
        reference_entity_id=reference_entity_id
    )
    return hr_action


@router.post("/cancel-leave/{leave_request_id}", response_model=HRPolicyActionOut)
async def cancel_approved_leave_endpoint(
    leave_request_id: int,
    cancel_data: CancelLeaveRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """Cancel approved CL/PL leave (company emergency) - HR only"""
    hr_action = cancel_approved_leave(
        db=db,
        leave_request_id=leave_request_id,
        action_by=current_user,
        recredit=cancel_data.recredit,
        remarks=cancel_data.remarks
    )
    return hr_action


@router.get("", response_model=HRPolicyActionListResponse)
async def list_hr_policy_actions(
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    action_type: Optional[HRPolicyActionType] = Query(None, description="Filter by action type"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """List HR policy actions with role-based scope"""
    actions = list_hr_actions(
        db=db,
        current_user=current_user,
        employee_id=employee_id,
        action_type=action_type
    )
    return HRPolicyActionListResponse(items=actions, total=len(actions))


@router.get("/{action_id}", response_model=HRPolicyActionOut)
async def get_hr_policy_action(
    action_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Get HR policy action by ID"""
    action = db.query(HRPolicyAction).filter(HRPolicyAction.id == action_id).first()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HR policy action not found"
        )
    
    # Check access (same scope rules as list)
    if current_user.role != Role.HR:
        if current_user.role == Role.MANAGER:
            # Manager can see only direct reportees
            employee = db.query(Employee).filter(Employee.id == action.employee_id).first()
            if not employee or employee.reporting_manager_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        else:
            # Employee can see only own
            if action.employee_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
    
    return action
