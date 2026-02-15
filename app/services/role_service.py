"""
Role service - business logic for role master management
"""
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.role import RoleModel
from app.schemas.role import RoleCreate, RoleUpdate
from app.services.audit_service import log_audit


def create_role(
    db: Session,
    role_data: RoleCreate,
    actor_id: int,
) -> RoleModel:
    """
    Create a new role.

    Name is treated as case-insensitive unique.
    """
    existing = (
        db.query(RoleModel)
        .filter(func.lower(RoleModel.name) == func.lower(role_data.name))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with name '{role_data.name}' already exists",
        )

    role = RoleModel(
        name=role_data.name,
        role_rank=role_data.role_rank,
        wfh_enabled=role_data.wfh_enabled,
        is_active=role_data.is_active,
    )
    db.add(role)
    db.commit()
    db.refresh(role)

    log_audit(
        db=db,
        actor_id=actor_id,
        action="CREATE",
        entity_type="role",
        entity_id=role.id,
        meta={
            "name": role.name,
            "role_rank": role.role_rank,
            "wfh_enabled": role.wfh_enabled,
            "is_active": role.is_active,
        },
    )

    return role


def list_roles(
    db: Session,
    active_only: Optional[bool] = True,
) -> List[RoleModel]:
    """
    List roles, optionally filtered by active flag.
    """
    query = db.query(RoleModel)
    if active_only is not None:
        query = query.filter(RoleModel.is_active == active_only)
    return query.order_by(RoleModel.name.asc()).all()


def get_role(db: Session, role_id: int) -> Optional[RoleModel]:
    """Get a role by ID."""
    return db.query(RoleModel).filter(RoleModel.id == role_id).first()


def update_role(
    db: Session,
    role_id: int,
    role_data: RoleUpdate,
    actor_id: int,
) -> RoleModel:
    """
    Update a role.
    """
    role = get_role(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with id {role_id} not found",
        )

    update_dict = role_data.dict(exclude_unset=True)

    # Enforce unique name if being updated
    if "name" in update_dict and update_dict["name"] is not None:
        new_name = update_dict["name"]
        existing = (
            db.query(RoleModel)
            .filter(
                func.lower(RoleModel.name) == func.lower(new_name),
                RoleModel.id != role_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role with name '{new_name}' already exists",
            )
        role.name = new_name

    if "wfh_enabled" in update_dict and update_dict["wfh_enabled"] is not None:
        role.wfh_enabled = update_dict["wfh_enabled"]

    if "is_active" in update_dict and update_dict["is_active"] is not None:
        role.is_active = update_dict["is_active"]

    if "role_rank" in update_dict and update_dict["role_rank"] is not None:
        role.role_rank = update_dict["role_rank"]

    db.commit()
    db.refresh(role)

    log_audit(
        db=db,
        actor_id=actor_id,
        action="UPDATE",
        entity_type="role",
        entity_id=role.id,
        meta=update_dict,
    )

    return role

