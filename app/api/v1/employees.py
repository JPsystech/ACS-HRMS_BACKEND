"""
Employee management endpoints (HR-only)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Role, Employee
from app.models.role import RoleModel
from app.models.department import Department
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeOut,
    EmployeeMeOut,
    PasswordReset,
    ManagerOptions,
)
from app.services.employee_service import (
    create_employee,
    list_employees,
    get_employee,
    get_employee_me,
    update_employee,
    reset_password,
    get_employees_by_reporting_manager,
    list_manager_candidates,
    _employee_to_employee_out,
    delete_employee,
)

router = APIRouter()


@router.post("", response_model=EmployeeOut, status_code=201)
async def create_employee_endpoint(
    employee_data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Create a new employee (ADMIN-only)"""
    return create_employee(db, employee_data, current_user.id)


@router.get("/me", response_model=EmployeeMeOut)
async def get_me_endpoint(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Get current authenticated user's profile (auth required).
    Returns profile with department and reporting_manager as nested objects.
    """
    profile = get_employee_me(db, current_user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return profile


@router.get("/my-team", response_model=List[EmployeeOut])
async def get_my_team_endpoint(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.MANAGER, Role.HR, Role.ADMIN, Role.MD))
):
    """
    Get the current user's team (employees who report to them)
    
    Roles allowed: MANAGER, HR, ADMIN, MD
    """
    return get_employees_by_reporting_manager(db, current_user.id)


@router.get("", response_model=List[EmployeeOut])
async def list_employees_endpoint(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    department_id: Optional[int] = Query(None),
    active_only: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN, Role.MD, Role.VP, Role.MANAGER, Role.HR))
):
    """List employees (ADMIN/MD/VP/MANAGER/HR read-only)"""
    return list_employees(
        db,
        skip=skip,
        limit=limit,
        department_id=department_id,
        active_only=active_only
    )


@router.get("/manager-options", response_model=List[ManagerOptions])
async def list_manager_options_endpoint(
    target_role_rank: int = Query(..., ge=1, description="Target employee role rank (required)"),
    department_id: Optional[int] = Query(None, description="Department ID for same-department preference (only for EMPLOYEE rank)"),
    search: Optional[str] = Query(None, description="Search by name or employee code"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN)),
):
    """
    Get eligible reporting managers for a given employee role rank.
    
    Returns active employees where role.role_rank < target_role_rank (higher authority).
    
    Rules:
    - ADMIN (rank 1): return empty list (no manager)
    - MD (rank 2): eligible managers = ADMIN only
    - VP (rank 3): eligible managers = ADMIN or MD
    - MANAGER (rank 4): eligible managers = ADMIN, MD, or VP
    - EMPLOYEE (rank >=5): eligible managers = anyone with higher authority (lower role_rank)
      - Prefer MANAGER from same department first
      - If none, show VP/MD/ADMIN etc. ordered by authority
    """
    # ADMIN (rank 1): no manager options available
    if target_role_rank == 1:
        return []
    
    # Build base query - employees with higher authority (lower role_rank)
    query = (
        db.query(
            Employee.id,
            Employee.emp_code,
            Employee.name,
            RoleModel.id.label("role_id"),
            RoleModel.name.label("role_name"),
            RoleModel.role_rank,
            Employee.department_id,
            Department.name.label("department_name")
        )
        .join(RoleModel, func.lower(RoleModel.name) == func.lower(Employee.role))
        .join(Department, Department.id == Employee.department_id)
        .filter(
            Employee.active == True,
            RoleModel.role_rank < target_role_rank  # Higher authority only
        )
    )
    
    # Apply search filter
    if search:
        pattern = f"%{search.lower()}%"
        query = query.filter(
            (func.lower(Employee.name).like(pattern)) |
            (func.lower(Employee.emp_code).like(pattern))
        )
    
    # For EMPLOYEE rank (>=5): prefer same-department MANAGER first
    if target_role_rank >= 5:
        # For rank 5 (EMPLOYEE): prefer same-department MANAGER first
        if target_role_rank == 5:
            # First get same-department MANAGERS (role_rank = 4) if department_id provided
            same_dept_managers = []
            if department_id is not None:
                same_dept_managers = (
                    query.filter(
                        Employee.department_id == department_id,
                        RoleModel.role_rank == 4  # MANAGER rank
                    )
                    .order_by(Employee.name.asc())
                    .all()
                )

            
            # Then get all other eligible managers (ranks 1-3 and other department managers)
            other_managers_query = query.filter(RoleModel.role_rank.in_([1, 2, 3]))
            if department_id is not None:
                # Include other department managers (rank 4) as fallback
                other_dept_managers = (
                    query.filter(
                        Employee.department_id != department_id,
                        RoleModel.role_rank == 4
                    )
                    .all()
                )
                other_managers = other_managers_query.all() + other_dept_managers
            else:
                other_managers = other_managers_query.all()
            
            # Remove duplicates and sort other managers by role_rank then name
            other_managers = list({m.id: m for m in other_managers}.values())
            other_managers.sort(key=lambda m: (m.role_rank, m.name))
            
            # Convert SQLAlchemy Row objects to ManagerOptions objects and mark fallback options
            same_dept_managers_options = [
                ManagerOptions(
                    id=m.id,
                    emp_code=m.emp_code,
                    name=m.name,
                    role_id=m.role_id,
                    role_name=m.role_name,
                    role_rank=m.role_rank,
                    department_id=m.department_id,
                    department_name=m.department_name,
                    is_fallback=False
                ) for m in same_dept_managers
            ]
            
            other_managers_options = [
                ManagerOptions(
                    id=m.id,
                    emp_code=m.emp_code,
                    name=m.name,
                    role_id=m.role_id,
                    role_name=m.role_name,
                    role_rank=m.role_rank,
                    department_id=m.department_id,
                    department_name=m.department_name,
                    is_fallback=True
                ) for m in other_managers
            ]
            
            results = same_dept_managers_options + other_managers_options

        
        else:
            # For rank 6+ roles: return ALL employees with higher authority (lower rank numbers)
            # No department preference logic for higher ranks
            # Create a completely fresh query to avoid any contamination from rank 5 logic
            fresh_query = (
                db.query(
                    Employee.id,
                    Employee.emp_code,
                    Employee.name,
                    RoleModel.id.label("role_id"),
                    RoleModel.name.label("role_name"),
                    RoleModel.role_rank,
                    Employee.department_id,
                    Department.name.label("department_name")
                )
                .join(RoleModel, RoleModel.name == Employee.role)
                .join(Department, Department.id == Employee.department_id)
                .filter(
                    Employee.active == True,
                    RoleModel.role_rank < target_role_rank  # Higher authority only
                )
            )
            
            # Apply search filter if provided
            if search:
                pattern = f"%{search.lower()}%"
                fresh_query = fresh_query.filter(
                    (func.lower(Employee.name).like(pattern)) |
                    (func.lower(Employee.emp_code).like(pattern))
                )
            
            results = fresh_query.order_by(RoleModel.role_rank.asc(), Employee.name.asc()).all()

    
    else:
        # For ranks 2-4 (MD/VP/MANAGER): no department preference, just order by authority
        # Apply role-specific eligibility rules
        if target_role_rank == 2:  # MD: only ADMIN (rank 1)
            query = query.filter(RoleModel.role_rank == 1)
        elif target_role_rank == 3:  # VP: ADMIN or MD (rank 1-2)
            query = query.filter(RoleModel.role_rank.in_([1, 2]))
        elif target_role_rank == 4:  # MANAGER: ADMIN, MD, or VP (rank 1-3)
            query = query.filter(RoleModel.role_rank.in_([1, 2, 3]))
        
        results = query.order_by(RoleModel.role_rank.asc(), Employee.name.asc()).all()

    
    # Ensure results is always a list
    if 'results' not in locals():
        results = []
    
    # Convert query results to ManagerOptions objects
    manager_options = []
    for result in results:
        manager_options.append(ManagerOptions(
            id=result.id,
            emp_code=result.emp_code,
            name=result.name,
            role_id=result.role_id,
            role_name=result.role_name,
            role_rank=result.role_rank,
            department_id=result.department_id,
            department_name=result.department_name,
            is_fallback=getattr(result, 'is_fallback', False)
        ))
    
    return manager_options


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee_endpoint(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN, Role.MD, Role.VP, Role.MANAGER, Role.HR))
):
    """Get an employee by ID (ADMIN/MD/VP/MANAGER/HR read-only)"""
    employee = get_employee(db, employee_id)
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found"
        )
    return _employee_to_employee_out(employee)


@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee_endpoint(
    employee_id: int,
    employee_data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Update an employee (ADMIN-only)"""
    return update_employee(db, employee_id, employee_data, current_user.id)


@router.post("/{employee_id}/reset-password", response_model=EmployeeOut)
async def reset_password_endpoint(
    employee_id: int,
    password_data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Reset an employee's password (ADMIN-only)"""
    return reset_password(db, employee_id, password_data.new_password, current_user.id)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee_endpoint(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """
    Delete an employee (ADMIN-only)
    
    Returns 204 No Content on successful deletion.
    Returns 404 if employee not found.
    Returns 400 if employee has direct reports and cannot be deleted.
    """
    deleted = delete_employee(db, employee_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {employee_id} not found"
        )
    return None
