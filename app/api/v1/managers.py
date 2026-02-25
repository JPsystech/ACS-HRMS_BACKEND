"""
Manager-Department assignment endpoints (HR-only)
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Role, Employee
from app.schemas.manager_department import (
    AssignDepartmentsRequest,
    ManagerDepartmentOut
)
from app.services.manager_department_service import (
    assign_departments_to_manager,
    list_manager_departments,
    remove_department_from_manager
)

router = APIRouter()


@router.post("/{manager_id}/departments", response_model=List[ManagerDepartmentOut], status_code=201)
async def assign_departments_endpoint(
    manager_id: int,
    request: AssignDepartmentsRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """Assign departments to a manager (HR-only)"""
    assignments = assign_departments_to_manager(
        db,
        manager_id,
        request.department_ids,
        current_user.id
    )
    return [
        ManagerDepartmentOut(manager_id=a.manager_id, department_id=a.department_id)
        for a in assignments
    ]


@router.get("/{manager_id}/departments", response_model=List[ManagerDepartmentOut])
async def list_manager_departments_endpoint(
    manager_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """List departments assigned to a manager (HR-only)"""
    assignments = list_manager_departments(db, manager_id)
    return [
        ManagerDepartmentOut(manager_id=a.manager_id, department_id=a.department_id)
        for a in assignments
    ]


@router.delete("/{manager_id}/departments/{department_id}", status_code=204)
async def remove_department_endpoint(
    manager_id: int,
    department_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """Remove a department assignment from a manager (HR-only)"""
    remove_department_from_manager(db, manager_id, department_id, current_user.id)
    return None
