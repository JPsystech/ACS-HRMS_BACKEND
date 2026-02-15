"""
Department service - business logic for department management
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from typing import List, Optional
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services.audit_service import log_audit


def create_department(
    db: Session,
    department_data: DepartmentCreate,
    actor_id: int
) -> Department:
    """
    Create a new department
    
    Args:
        db: Database session
        department_data: Department creation data
        actor_id: ID of the user creating the department
    
    Returns:
        Created Department instance
    
    Raises:
        HTTPException: If department name already exists
    """
    # Check for duplicate name (case-insensitive)
    existing = db.query(Department).filter(
        func.lower(Department.name) == func.lower(department_data.name)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with name '{department_data.name}' already exists"
        )
    
    department = Department(
        name=department_data.name,
        active=department_data.active
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=actor_id,
        action="CREATE",
        entity_type="department",
        entity_id=department.id,
        meta={"name": department.name, "active": department.active}
    )
    
    return department


def list_departments(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    active_only: Optional[bool] = None
) -> List[Department]:
    """
    List departments with optional filtering
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        active_only: If True, return only active departments
    
    Returns:
        List of Department instances
    """
    query = db.query(Department)
    
    if active_only is not None:
        query = query.filter(Department.active == active_only)
    
    return query.offset(skip).limit(limit).all()


def get_department(db: Session, department_id: int) -> Optional[Department]:
    """Get a department by ID"""
    return db.query(Department).filter(Department.id == department_id).first()


def update_department(
    db: Session,
    department_id: int,
    department_data: DepartmentUpdate,
    actor_id: int
) -> Department:
    """
    Update a department
    
    Args:
        db: Database session
        department_id: ID of department to update
        department_data: Department update data
        actor_id: ID of the user updating the department
    
    Returns:
        Updated Department instance
    
    Raises:
        HTTPException: If department not found or name conflict
    """
    department = get_department(db, department_id)
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )
    
    # Check for duplicate name if name is being updated
    if department_data.name is not None:
        existing = db.query(Department).filter(
            func.lower(Department.name) == func.lower(department_data.name),
            Department.id != department_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with name '{department_data.name}' already exists"
            )
        department.name = department_data.name
    
    if department_data.active is not None:
        department.active = department_data.active
    
    db.commit()
    db.refresh(department)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=actor_id,
        action="UPDATE",
        entity_type="department",
        entity_id=department.id,
        meta={
            "name": department.name,
            "active": department.active,
            "updated_fields": department_data.dict(exclude_unset=True)
        }
    )
    
    return department
