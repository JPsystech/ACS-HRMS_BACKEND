"""
Department management endpoints (HR-only)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Role, Employee
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentOut
from app.services.department_service import (
    create_department,
    list_departments,
    get_department,
    update_department
)

router = APIRouter()


@router.post("", response_model=DepartmentOut, status_code=201)
async def create_department_endpoint(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN, Role.HR))
):
    """Create a new department (HR-only)"""
    return create_department(db, department_data, current_user.id)


@router.get("", response_model=List[DepartmentOut])
async def list_departments_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    active_only: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN, Role.HR))
):
    """List departments (Admin/HR only)"""
    return list_departments(db, skip=skip, limit=limit, active_only=active_only)


@router.get("/{department_id}", response_model=DepartmentOut)
async def get_department_endpoint(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Get a department by ID (Admin/HR only)"""
    department = get_department(db, department_id)
    if not department:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )
    return department


@router.patch("/{department_id}", response_model=DepartmentOut)
async def update_department_endpoint(
    department_id: int,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Update a department (Admin-only)"""
    return update_department(db, department_id, department_data, current_user.id)
