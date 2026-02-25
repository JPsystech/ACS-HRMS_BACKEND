"""
Admin user management endpoints
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Employee, Role
from app.schemas.auth import AdminResetPasswordRequest
from app.core.security import validate_strong_password, hash_password
from app.services.audit_service import log_audit
import secrets
import string

router = APIRouter()


def _generate_strong_temp_password(length: int = 12) -> str:
    """Generate a strong temporary password."""
    if length < 8:
        length = 8
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        try:
            validate_strong_password(pwd)
            return pwd
        except ValueError:
            continue


@router.post("/{user_id}/reset-password")
async def admin_reset_password_endpoint(
    user_id: int,
    payload: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN)),
):
    """
    Reset a user's password (ADMIN only).
    - Accepts new_password or generate_random=true.
    - Sets must_change_password=true.
    - Logs audit with action PASSWORD_RESET.
    - Returns temp password if generated (one-time display).
    """
    target = db.query(Employee).filter(Employee.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if payload.generate_random:
        temp_password = _generate_strong_temp_password(12)
        new_password = temp_password
    else:
        if not payload.new_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new_password is required when generate_random is false")
        try:
            new_password = validate_strong_password(payload.new_password)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
        temp_password = None
    
    target.password_hash = hash_password(new_password)
    target.must_change_password = True
    target.password_changed_at = None
    db.add(target)
    db.commit()
    
    # Audit: PASSWORD_RESET
    try:
        log_audit(
            db=db,
            actor_id=current_user.id,
            action="PASSWORD_RESET",
            entity_type="employee",
            entity_id=target.id,
            meta={"target_user_id": target.id, "generated": payload.generate_random},
        )
    except Exception:
        pass
    
    resp = {"message": "Password reset successfully"}
    if temp_password:
        resp["temp_password"] = temp_password
    return resp
