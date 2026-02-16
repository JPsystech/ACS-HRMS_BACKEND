"""
Employee service - business logic for employee management
"""
import logging
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from typing import List, Optional
from sqlalchemy import func, cast, String
from app.models.employee import Employee, Role
from app.models.department import Department
from app.models.role import RoleModel
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeOut,
    EmployeeMeOut,
    DepartmentRef,
    ReportingManagerRef,
)
from app.core.security import hash_password
from app.utils.enums import enum_to_str
from app.services.audit_service import log_audit


def _check_reporting_hierarchy_cycle(
    db: Session,
    employee_id: int,
    reporting_manager_id: int
) -> bool:
    """
    Check if setting reporting_manager_id would create a cycle
    
    Args:
        db: Database session
        employee_id: ID of employee being updated
        reporting_manager_id: Proposed reporting manager ID
    
    Returns:
        True if cycle would be created, False otherwise
    """
    if employee_id == reporting_manager_id:
        return True  # Self-reference creates a cycle
    
    # Walk up the chain from the proposed manager
    visited = set()
    current_id = reporting_manager_id
    
    while current_id is not None:
        if current_id == employee_id:
            return True  # Cycle detected
        
        if current_id in visited:
            break  # Already checked this path
        
        visited.add(current_id)
        manager = db.query(Employee).filter(Employee.id == current_id).first()
        if not manager or not manager.reporting_manager_id:
            break
        
        current_id = manager.reporting_manager_id
    
    return False


def create_employee(
    db: Session,
    employee_data: EmployeeCreate,
    actor_id: int
) -> Employee:
    """
    Create a new employee
    
    Args:
        db: Database session
        employee_data: Employee creation data
        actor_id: ID of the user creating the employee
    
    Returns:
        Created Employee instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Check emp_code uniqueness
    existing = db.query(Employee).filter(Employee.emp_code == employee_data.emp_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Employee with emp_code '{employee_data.emp_code}' already exists"
        )
    
    # Validate department exists and is active
    department = db.query(Department).filter(Department.id == employee_data.department_id).first()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with id {employee_data.department_id} not found"
        )
    if not department.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with id {employee_data.department_id} is inactive"
        )
    
    # RBAC Permission Validation
    actor = db.query(Employee).filter(Employee.id == actor_id).first()
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid actor"
        )
    
    # Get actor's role rank
    actor_role_row = db.query(RoleModel).filter(
        func.lower(RoleModel.name) == func.lower(cast(actor.role, String))
    ).first()
    if not actor_role_row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Actor role configuration not found"
        )
    actor_rank = actor_role_row.role_rank
    
    # Get employee's role rank
    employee_role_row = db.query(RoleModel).filter(
        func.lower(RoleModel.name) == func.lower(cast(employee_data.role, String))
    ).first()
    if not employee_role_row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role configuration not found for {employee_data.role}",
        )
    employee_rank = employee_role_row.role_rank
    
    # Dynamic permission rules based on role hierarchy:
    # 1. ADMIN (rank=1) can create any role
    # 2. Users can only create roles with higher rank numbers (lower authority)
    # 3. Users cannot create roles with same or lower rank numbers
    # 4. Users cannot create roles with rank <= their own rank
    
    # Check if actor has permission to create this role
    if actor_rank > 1:  # Not ADMIN
        # Get all roles from database to understand the hierarchy
        all_roles = db.query(RoleModel).filter(RoleModel.is_active == True).all()
        
        # Find the actor's role name for better error messages
        actor_role_name = next((r.name for r in all_roles if r.role_rank == actor_rank), f"rank_{actor_rank}")
        
        # Dynamic validation rules:
        # - Cannot create roles with same or lower rank (same or higher authority)
        if employee_rank <= actor_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{actor_role_name} cannot create roles with same or higher authority"
            )
        
        # - Cannot create roles that don't exist in the system
        valid_ranks = {r.role_rank for r in all_roles}
        if employee_rank not in valid_ranks:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid role rank {employee_rank}"
            )
        
        # - For specific role-based restrictions (like VP cannot create other VPs)
        #   This is handled by the rank comparison above since employee_rank <= actor_rank would catch same rank

    # Validate reporting manager with role_rank rules
    manager_id = employee_data.reporting_manager_id

    # Get all roles to find the highest authority role (lowest rank number)
    all_roles = db.query(RoleModel).filter(RoleModel.is_active == True).all()
    highest_authority_rank = min(r.role_rank for r in all_roles) if all_roles else 1
    
    # If employee has highest authority role, force reporting_manager_id to be null
    if employee_rank == highest_authority_rank and manager_id is not None:
        highest_role_name = next((r.name for r in all_roles if r.role_rank == highest_authority_rank), "highest authority role")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{highest_role_name} cannot have a reporting manager",
        )

    # If employee doesn't have highest authority role, reporting manager is compulsory
    if employee_rank != highest_authority_rank and not manager_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reporting manager is required for this role",
        )

    if manager_id:
        # Self-reporting is not allowed
        # Note: employee_id doesn't exist yet for create, but we can check if manager_id matches
        # any existing employee with same emp_code (though this is unlikely during creation)
        # For create operation, we'll rely on the cycle check function
        if _check_reporting_hierarchy_cycle(db, 0, manager_id):  # Using 0 as placeholder for new employee
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot set reporting manager: would create invalid hierarchy",
            )

        reporting_manager = db.query(Employee).filter(Employee.id == manager_id).first()
        if not reporting_manager:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Reporting manager with id {manager_id} not found",
            )

        manager_role_row = (
            db.query(RoleModel)
            .filter(func.lower(RoleModel.name) == func.lower(cast(reporting_manager.role, String)))
            .first()
        )
        if not manager_role_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role configuration not found for reporting manager role {reporting_manager.role}",
            )

        manager_rank = manager_role_row.role_rank

        # Manager must have higher authority (smaller rank)
        if manager_rank >= employee_rank:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reporting manager must have a higher role rank than the employee",
            )
        
        # Dynamic reporting hierarchy validation
        # Manager must have higher authority (lower rank number) than employee
        # This replaces hardcoded lists with a flexible system
        
        # Get all roles to understand the hierarchy for better error messages
        all_roles = db.query(RoleModel).filter(RoleModel.is_active == True).all()
        
        # Find valid manager roles (roles with rank < employee_rank)
        valid_manager_ranks = [r.role_rank for r in all_roles if r.role_rank < employee_rank]
        
        if manager_rank not in valid_manager_ranks:
            # Generate descriptive error message
            employee_role_name = next((r.name for r in all_roles if r.role_rank == employee_rank), f"rank_{employee_rank}")
            valid_manager_names = [r.name for r in all_roles if r.role_rank in valid_manager_ranks]
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{employee_role_name} can only report to roles with higher authority: {', '.join(valid_manager_names)}",
            )
        
        # Validate manager is from same department (unless Admin override)
        if reporting_manager.department_id != employee_data.department_id:
            # Check if actor is Admin (can override department restriction)
            actor = db.query(Employee).filter(Employee.id == actor_id).first()
            if not actor or actor.role != Role.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reporting manager must be from the same department",
                )
    
    # Handle password - always generate a password hash to satisfy NOT NULL constraint
    from app.core.security import validate_password, hash_password
    
    if employee_data.password:
        # Use provided password if available
        try:
            validated_password = validate_password(employee_data.password)
            password_hash = hash_password(validated_password)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
    else:
        # Generate default password if none provided
        default_password = "Welcome@123"
        password_hash = hash_password(default_password)
        # Log the generated password for local development
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Generated default password for new employee %s", employee_data.emp_code)
    
    employee = Employee(
        emp_code=employee_data.emp_code,
        name=employee_data.name,
        mobile_number=employee_data.mobile_number,
        role=employee_data.role,
        department_id=employee_data.department_id,
        reporting_manager_id=employee_data.reporting_manager_id,
        password_hash=password_hash,  # Can be None if no password provided
        join_date=employee_data.join_date,
        active=employee_data.active
    )
    
    db.add(employee)
    db.commit()
    db.refresh(employee)

    # Auto-initialize leave balances for current year (PL/CL/SL/RH per policy)
    from datetime import date
    from app.services import leave_wallet_service as wallet
    try:
        wallet.ensure_wallet_for_employee(db, employee.id, date.today().year)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning("Could not init leave wallet for new employee %s: %s", employee.id, e)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=actor_id,
        action="CREATE",
        entity_type="employee",
        entity_id=employee.id,
        meta={
            "emp_code": employee.emp_code,
            "name": employee.name,
            "role": enum_to_str(employee.role),
            "department_id": employee.department_id
        }
    )
    
    return employee


def delete_employee(
    db: Session,
    employee_id: int,
    actor_id: int
) -> bool:
    """
    Delete an employee
    
    Args:
        db: Database session
        employee_id: ID of employee to delete
        actor_id: ID of the user deleting the employee
    
    Returns:
        True if employee was deleted, False if not found
    
    Raises:
        HTTPException: If validation fails or employee cannot be deleted
    """
    employee = get_employee(db, employee_id)
    if not employee:
        return False
    
    # Check if employee has any direct reports
    direct_reports = get_employees_by_reporting_manager(db, employee_id)
    if direct_reports:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete employee who has direct reports. Please reassign reports first."
        )
    
    # Check if employee has any associated data that would prevent deletion
    # For example: leave requests, attendance records, etc.
    # This is a placeholder for future validation if needed
    
    # Log audit before deletion
    log_audit(
        db=db,
        actor_id=actor_id,
        action="DELETE",
        entity_type="employee",
        entity_id=employee.id,
        meta={
            "emp_code": employee.emp_code,
            "name": employee.name,
            "role": enum_to_str(employee.role),
            "department_id": employee.department_id
        }
    )
    
    # Delete the employee
    db.delete(employee)
    db.commit()
    
    return True


def list_employees(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    department_id: Optional[int] = None,
    active_only: Optional[bool] = None
) -> List[EmployeeOut]:
    """
    List employees with optional filtering
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        department_id: Filter by department ID
        active_only: If True, return only active employees
    
    Returns:
        List of EmployeeOut instances with reporting_manager data and role_rank
    """
    # Join with RoleModel to get role_rank
    query = (
        db.query(Employee, RoleModel.role_rank.label('_role_rank'))
        .join(RoleModel, RoleModel.name == Employee.role)
        .options(joinedload(Employee.reporting_manager))
    )
    
    if department_id is not None:
        query = query.filter(Employee.department_id == department_id)
    
    if active_only is not None:
        query = query.filter(Employee.active == active_only)
    
    # Execute query and get results with role_rank
    results = query.offset(skip).limit(limit).all()
    
    # Extract employees with their role_rank
    employees_with_rank = []
    for result in results:
        employee = result[0]
        employee._role_rank = result[1]  # Set the role_rank as an attribute
        employees_with_rank.append(employee)
    
    # Convert to EmployeeOut schema with reporting_manager data
    return [_employee_to_employee_out(emp) for emp in employees_with_rank]


def list_manager_candidates(
    db: Session,
    max_role_rank: int,
    search: Optional[str] = None,
    limit: int = 50,
) -> List[Employee]:
    """
    List potential reporting managers for a given employee role rank.

    - Returns employees whose role_rank < max_role_rank
    - Only active employees
    - Optional search by name or emp_code
    - Company-wide hierarchy (no department filtering)
    """
    # Protection: return empty list if max_role_rank <= 1
    if max_role_rank <= 1:
        return []
    
    # Join Employee -> RoleModel using proper ORM relationship
    query = (
        db.query(Employee)
        .join(RoleModel, RoleModel.name == Employee.role)
        .filter(
            Employee.active == True,  # noqa: E712
            RoleModel.role_rank < max_role_rank,
        )
    )

    if search:
        pattern = f"%{search.lower()}%"
        query = query.filter(
            func.lower(Employee.name).like(pattern)
            | func.lower(Employee.emp_code).like(pattern)
        )

    return query.order_by(Employee.name.asc()).limit(limit).all()


def get_employee(db: Session, employee_id: int) -> Optional[Employee]:
    """Get an employee by ID"""
    return (
        db.query(Employee)
        .options(joinedload(Employee.reporting_manager))
        .filter(Employee.id == employee_id)
        .first()
    )


def get_employee_me(db: Session, employee_id: int) -> Optional[EmployeeMeOut]:
    """
    Get current user profile with department and reporting_manager (for GET /employees/me).
    """
    # Join with RoleModel to get role_rank
    result = (
        db.query(Employee, RoleModel.role_rank.label('_role_rank'))
        .join(RoleModel, RoleModel.name == Employee.role)
        .options(
            joinedload(Employee.department),
            joinedload(Employee.reporting_manager),
        )
        .filter(Employee.id == employee_id)
        .first()
    )
    
    if not result:
        return None
    
    emp, role_rank = result[0], result[1]
    
    return EmployeeMeOut(
        id=emp.id,
        emp_code=emp.emp_code,
        name=emp.name,
        mobile_number=emp.mobile_number,
        department=DepartmentRef.model_validate(emp.department) if emp.department else None,
        reporting_manager=ReportingManagerRef.model_validate(emp.reporting_manager) if emp.reporting_manager else None,
        role=emp.role,
        role_rank=role_rank,
        join_date=emp.join_date,
        is_active=emp.active,
        work_mode=emp.work_mode,
    )


def _employee_to_employee_out(employee: Employee) -> EmployeeOut:
    """Convert Employee instance to EmployeeOut schema with reporting_manager"""
    from app.schemas.employee import EmployeeOut, ReportingManagerRef
    
    # Get role rank from RoleModel
    role_rank = None
    
    # If employee has role information, try to get the role rank
    if employee.role:
        # Try to get role rank from joined load if available
        if hasattr(employee, '_role_rank'):
            role_rank = getattr(employee, '_role_rank', None)
    
    return EmployeeOut(
        id=employee.id,
        emp_code=employee.emp_code,
        name=employee.name,
        mobile_number=employee.mobile_number,
        role=employee.role,
        role_rank=role_rank,
        department_id=employee.department_id,
        reporting_manager_id=employee.reporting_manager_id,
        reporting_manager=ReportingManagerRef.model_validate(employee.reporting_manager) if employee.reporting_manager else None,
        join_date=employee.join_date,
        active=employee.active,
        work_mode=employee.work_mode,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


def update_employee(
    db: Session,
    employee_id: int,
    employee_data: EmployeeUpdate,
    actor_id: int
) -> Employee:
    """
    Update an employee
    
    Args:
        db: Database session
        employee_id: ID of employee to update
        employee_data: Employee update data
        actor_id: ID of the user updating the employee
    
    Returns:
        Updated Employee instance
    
    Raises:
        HTTPException: If validation fails
    """
    employee = get_employee(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found"
        )
    
    update_dict = employee_data.dict(exclude_unset=True)
    
    # Update department if provided
    if "department_id" in update_dict:
        department = db.query(Department).filter(Department.id == update_dict["department_id"]).first()
        if not department:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with id {update_dict['department_id']} not found"
            )
        if not department.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with id {update_dict['department_id']} is inactive"
            )
        employee.department_id = update_dict["department_id"]
    
    # Check if actor is HR trying to update to Admin role
    if "role" in update_dict:
        actor = db.query(Employee).filter(Employee.id == actor_id).first()
        if actor and actor.role == Role.HR and update_dict["role"] == Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="HR cannot assign Admin role"
            )
    
    # Determine effective role after update (new value or existing)
    effective_role: Role = update_dict.get("role", employee.role)

    role_row = (
        db.query(RoleModel)
        .filter(func.lower(RoleModel.name) == func.lower(enum_to_str(effective_role)))
        .first()
    )
    if not role_row:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role configuration not found for {enum_to_str(effective_role)}",
        )
    employee_rank = role_row.role_rank

    # Determine effective reporting manager after update
    effective_manager_id = (
        update_dict["reporting_manager_id"]
        if "reporting_manager_id" in update_dict
        else employee.reporting_manager_id
    )

    # Get all roles to find the highest authority role (lowest rank number)
    all_roles = db.query(RoleModel).filter(RoleModel.is_active == True).all()
    highest_authority_rank = min(r.role_rank for r in all_roles) if all_roles else 1
    
    # If employee doesn't have highest authority role, reporting manager is compulsory
    if employee_rank != highest_authority_rank and not effective_manager_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reporting manager is required for this role",
        )

    if effective_manager_id is not None:
        # Self-reporting is not allowed
        if effective_manager_id == employee_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee cannot be their own reporting manager",
            )

        # Check for cycle
        if _check_reporting_hierarchy_cycle(db, employee_id, effective_manager_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot set reporting manager: would create a cycle in hierarchy",
            )

        # Validate manager exists
        reporting_manager = (
            db.query(Employee).filter(Employee.id == effective_manager_id).first()
        )
        if not reporting_manager:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Reporting manager with id {effective_manager_id} not found",
            )

        manager_role_row = (
            db.query(RoleModel)
            .filter(func.lower(RoleModel.name) == func.lower(cast(reporting_manager.role, String)))
            .first()
        )
        if not manager_role_row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role configuration not found for reporting manager role {reporting_manager.role}",
            )

        manager_rank = manager_role_row.role_rank

        # Manager must have higher authority (smaller rank)
        if manager_rank >= employee_rank:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reporting manager must have a higher role rank than the employee",
            )

    # Apply reporting manager update if explicitly provided
    if "reporting_manager_id" in update_dict:
        employee.reporting_manager_id = update_dict["reporting_manager_id"]
    
    # Update other fields
    if "name" in update_dict:
        employee.name = update_dict["name"]
    if "mobile_number" in update_dict:
        employee.mobile_number = update_dict["mobile_number"]
    if "role" in update_dict:
        employee.role = update_dict["role"]
    if "join_date" in update_dict:
        employee.join_date = update_dict["join_date"]
    if "active" in update_dict:
        employee.active = update_dict["active"]
    
    db.commit()
    db.refresh(employee)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=actor_id,
        action="UPDATE",
        entity_type="employee",
        entity_id=employee.id,
        meta={
            "emp_code": employee.emp_code,
            "updated_fields": update_dict
        }
    )
    
    return employee


def get_employees_by_reporting_manager(
    db: Session,
    reporting_manager_id: int
) -> List[Employee]:
    """
    Get all employees who report to a specific manager
    
    Args:
        db: Database session
        reporting_manager_id: ID of the reporting manager
        
    Returns:
        List of Employee instances
    """
    return db.query(Employee).filter(
        Employee.reporting_manager_id == reporting_manager_id,
        Employee.active == True
    ).order_by(Employee.name).all()


def reset_password(
    db: Session,
    employee_id: int,
    new_password: str,
    actor_id: int
) -> Employee:
    """
    Reset an employee's password
    
    Args:
        db: Database session
        employee_id: ID of employee
        new_password: New password
        actor_id: ID of the user resetting the password
    
    Returns:
        Updated Employee instance
    
    Raises:
        HTTPException: If employee not found
    """
    employee = get_employee(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found"
        )
    
    employee.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(employee)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=actor_id,
        action="UPDATE",
        entity_type="employee",
        entity_id=employee.id,
        meta={"action": "password_reset"}
    )
    
    return employee
