"""
Role master endpoints (HR/Admin)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.employee import Employee, Role
from app.schemas.role import RoleCreate, RoleUpdate, RoleOut
from app.services.role_service import create_role, list_roles, get_role, update_role


router = APIRouter()


@router.post("", response_model=RoleOut, status_code=201)
async def create_role_endpoint(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN)),
):
    """
    Create a new role (HR/Admin only).
    """
    return create_role(db, role_data, current_user.id)


@router.get("", response_model=List[RoleOut])
async def list_roles_endpoint(
    active_only: Optional[bool] = Query(
        True,
        description="If true, return only active roles",
    ),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN, Role.HR)),
):
    """
    List roles (HR/Admin only).
    """
    return list_roles(db, active_only=active_only)


@router.patch("/{role_id}", response_model=RoleOut)
async def update_role_endpoint(
    role_id: int,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN)),
):
    """
    Update a role (HR/Admin only).
    """
    return update_role(db, role_id, role_data, current_user.id)


@router.get("/{role_id}", response_model=RoleOut)
async def get_role_endpoint(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN, Role.HR)),
):
    """
    Get a role by ID (HR/Admin only).
    """
    role = get_role(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with id {role_id} not found",
        )
    return role

