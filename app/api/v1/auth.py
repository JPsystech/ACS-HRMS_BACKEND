"""
Authentication endpoints
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.core.security import verify_password, create_access_token, validate_strong_password, hash_password
from app.models.employee import Employee
from app.schemas.auth import LoginRequest, TokenResponse, ChangePasswordRequest

router = APIRouter()


@router.post("/login-mobile", response_model=TokenResponse)
async def login_mobile(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Mobile-friendly login endpoint - simplified for mobile apps
    Returns token without must_change_password complexity
    """
    # Find employee by emp_code
    employee = db.query(Employee).filter(Employee.emp_code == login_data.emp_code).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee code or password"
        )
    
    # Check if employee is active
    if not employee.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Verify password
    if employee.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No password set for this account"
        )
    
    if not verify_password(login_data.password, employee.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee code or password"
        )
    
    # Get role_rank
    from app.models.role import RoleModel
    role_rank_map = {
        "ADMIN": 1,
        "MD": 2,
        "VP": 3,
        "MANAGER": 4,
        "HR": 5,
        "EMPLOYEE": 99
    }
    try:
        role_model = db.query(RoleModel).filter(
            RoleModel.name == employee.role
        ).first()
        role_rank = role_model.role_rank if role_model else role_rank_map.get(employee.role, 99)
    except Exception:
        role_rank = role_rank_map.get(employee.role, 99)
    
    # Create access token
    token_data = {
        "sub": str(employee.id),
        "emp_code": employee.emp_code,
        "role": employee.role,
        "role_rank": role_rank
    }
    access_token = create_access_token(data=token_data)
    
    # Update last_login_at
    try:
        employee.last_login_at = datetime.utcnow()
        db.add(employee)
        db.commit()
    except Exception:
        db.rollback()
    
    # Return simple token response (always false for mobile)
    return TokenResponse(access_token=access_token, token_type="bearer", must_change_password=False)


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token
    
    Validates emp_code and password, rejects inactive employees.
    Returns access token with employee_id, emp_code, role, and credit.
    """
    # Find employee by emp_code
    employee = db.query(Employee).filter(Employee.emp_code == login_data.emp_code).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee code or password"
        )
    
    # Check if employee is active
    if not employee.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Verify password - handle case where employee has no password set
    if employee.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No password set for this account"
        )
    
    if not verify_password(login_data.password, employee.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee code or password"
        )
    
    # Get role_rank from roles table
    from app.models.role import RoleModel
    role_rank_map = {
        "ADMIN": 1,
        "MD": 2,
        "VP": 3,
        "MANAGER": 4,
        "HR": 5,
        "EMPLOYEE": 99
    }
    try:
        role_model = db.query(RoleModel).filter(
            RoleModel.name == employee.role
        ).first()
        role_rank = role_model.role_rank if role_model else role_rank_map.get(employee.role, 99)
    except Exception:
        role_rank = role_rank_map.get(employee.role, 99)
    
    # Restrict admin panel login to role_rank 1-4 only (ADMIN, MD, VP, MANAGER)
    # Commented out for development/testing - allows all roles to login
    # if role_rank > 4:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Admin panel access is restricted to ADMIN, MD, VP, and MANAGER roles only"
    #     )
    
    # Create access token
    # Note: JWT 'sub' claim must be a string per JWT spec
    
    token_data = {
        "sub": str(employee.id),
        "emp_code": employee.emp_code,
        "role": employee.role,
        "role_rank": role_rank
    }
    access_token = create_access_token(data=token_data)
    
    # Update last_login_at timestamp
    try:
        employee.last_login_at = datetime.utcnow()
        db.add(employee)
        db.commit()
    except Exception:
        db.rollback()
    
    # Log audit (successful login) - don't fail login if audit fails
    try:
        from app.services.audit_service import log_audit
        log_audit(
            db=db,
            actor_id=employee.id,
            action="AUTH_LOGIN_SUCCESS",
            entity_type="auth",
            entity_id=None,
            meta={"emp_code": employee.emp_code, "role": employee.role}
        )
    except Exception as e:
        # Log error but don't fail login
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to log audit for login: {e}")
    
    return TokenResponse(access_token=access_token, token_type="bearer", must_change_password=bool(getattr(employee, "must_change_password", False)))


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Employee-initiated password change.
    - Verifies current password.
    - Enforces strong password rules.
    - Updates password_hash, password_changed_at, sets must_change_password=false.
    """
    user = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not user or user.password_hash is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")
    
    try:
        new_pw = validate_strong_password(payload.new_password)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    
    user.password_hash = hash_password(new_pw)
    user.password_changed_at = datetime.utcnow()
    user.must_change_password = False
    db.add(user)
    db.commit()
    
    # Audit: PASSWORD_CHANGED
    try:
        from app.services.audit_service import log_audit
        log_audit(
            db=db,
            actor_id=current_user.id,
            action="PASSWORD_CHANGED",
            entity_type="auth",
            entity_id=current_user.id,
            meta={"target_user_id": current_user.id}
        )
    except Exception:
        pass
    
    return {"message": "Password changed successfully"}
