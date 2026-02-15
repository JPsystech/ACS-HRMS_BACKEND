"""
Manager-Department service - business logic for manager-department assignments
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from app.models.employee import Employee, Role
from app.models.department import Department
from app.models.manager_department import ManagerDepartment
from app.services.audit_service import log_audit


def assign_departments_to_manager(
    db: Session,
    manager_id: int,
    department_ids: List[int],
    actor_id: int
) -> List[ManagerDepartment]:
    """
    Assign multiple departments to a manager
    
    Args:
        db: Database session
        manager_id: ID of the manager
        department_ids: List of department IDs to assign
        actor_id: ID of the user performing the assignment
    
    Returns:
        List of created ManagerDepartment instances
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate manager exists and is MANAGER role
    manager = db.query(Employee).filter(Employee.id == manager_id).first()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manager with id {manager_id} not found"
        )
    
    if manager.role != Role.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Employee with id {manager_id} is not a MANAGER. Only MANAGER role can be assigned departments."
        )
    
    # Validate all departments exist and are active
    departments = db.query(Department).filter(Department.id.in_(department_ids)).all()
    found_ids = {d.id for d in departments}
    missing_ids = set(department_ids) - found_ids
    
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Departments not found: {list(missing_ids)}"
        )
    
    inactive_departments = [d.id for d in departments if not d.active]
    if inactive_departments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign inactive departments: {inactive_departments}"
        )
    
    # Remove existing assignments for this manager
    db.query(ManagerDepartment).filter(ManagerDepartment.manager_id == manager_id).delete()
    
    # Create new assignments
    assignments = []
    for dept_id in department_ids:
        assignment = ManagerDepartment(
            manager_id=manager_id,
            department_id=dept_id
        )
        db.add(assignment)
        assignments.append(assignment)
    
    db.commit()
    
    # Refresh all assignments
    for assignment in assignments:
        db.refresh(assignment)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=actor_id,
        action="ASSIGN",
        entity_type="manager_department",
        entity_id=manager_id,
        meta={
            "manager_id": manager_id,
            "department_ids": department_ids
        }
    )
    
    return assignments


def list_manager_departments(
    db: Session,
    manager_id: int
) -> List[ManagerDepartment]:
    """
    List all departments assigned to a manager
    
    Args:
        db: Database session
        manager_id: ID of the manager
    
    Returns:
        List of ManagerDepartment instances
    """
    return db.query(ManagerDepartment).filter(
        ManagerDepartment.manager_id == manager_id
    ).all()


def remove_department_from_manager(
    db: Session,
    manager_id: int,
    department_id: int,
    actor_id: int
) -> None:
    """
    Remove a department assignment from a manager
    
    Args:
        db: Database session
        manager_id: ID of the manager
        department_id: ID of the department to remove
        actor_id: ID of the user performing the removal
    
    Raises:
        HTTPException: If assignment not found
    """
    assignment = db.query(ManagerDepartment).filter(
        ManagerDepartment.manager_id == manager_id,
        ManagerDepartment.department_id == department_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department {department_id} is not assigned to manager {manager_id}"
        )
    
    db.delete(assignment)
    db.commit()
    
    # Log audit
    log_audit(
        db=db,
        actor_id=actor_id,
        action="DELETE",
        entity_type="manager_department",
        entity_id=manager_id,
        meta={
            "manager_id": manager_id,
            "department_id": department_id
        }
    )
