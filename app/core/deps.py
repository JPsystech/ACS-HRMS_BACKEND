"""
Dependencies and guards for FastAPI endpoints
"""
from typing import Generator, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import SessionLocal
from app.core.security import decode_token
from app.models.employee import Employee, Role
from app.models.role import RoleModel


security = HTTPBearer()


def get_db() -> Generator:
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Employee:
    """
    Get current authenticated user from JWT token
    """
    token = credentials.credentials
    
    try:
        payload = decode_token(token)
        sub_value = payload.get("sub")
        if sub_value is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Convert string sub back to integer
        employee_id: int = int(sub_value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not employee.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return employee


def require_roles(*allowed_roles: Role):
    """
    Dependency factory for role-based access control

    Usage:
        @router.get("/hr-only")
        async def hr_endpoint(user: Employee = Depends(require_roles(Role.HR))):
            ...
    """
    def role_checker(current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)) -> Employee:
        # Allow ADMIN superuser access regardless of required roles
        if current_user.role == Role.ADMIN:
            return current_user
        
        # Check if user has role rank 1 (ADMIN equivalent)
        role_model = db.query(RoleModel).filter(
            func.lower(RoleModel.name) == func.lower(current_user.role)
        ).first()
        if role_model and role_model.role_rank == 1:
            return current_user
        
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker


def require_admin_attendance(current_user: Employee = Depends(get_current_user), db: Session = Depends(get_db)) -> Employee:
    """
    Allow access based on role-rank hierarchy (ADMIN/MD/VP: all; MANAGER: direct reportees; EMPLOYEE: none).
    Uses the same role-based scoping as leaves.
    """
    from app.services.leave_service import get_role_rank
    
    current_user_rank = get_role_rank(db, current_user)
    
    # ADMIN, MD, VP (role_rank <= 3) can access all attendance
    if current_user_rank <= 3:
        return current_user
    
    # MANAGER (role_rank == 4) can access attendance of direct reportees
    if current_user_rank == 4:
        return current_user
    
    # EMPLOYEE and others cannot access admin attendance
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied. Admin role required for admin attendance."
    )
