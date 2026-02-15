"""
Restricted Holiday management endpoints (HR-only)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Role, Employee
from app.schemas.holiday import RHCreate, RHUpdate, RHOut
from app.services.holiday_service import (
    create_rh,
    list_rhs,
    get_rh,
    update_rh
)

router = APIRouter()


@router.post("", response_model=RHOut, status_code=201)
async def create_rh_endpoint(
    rh_data: RHCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Create a new restricted holiday (Admin-only)"""
    return create_rh(
        db=db,
        year=rh_data.year,
        rh_date=rh_data.date,
        name=rh_data.name,
        active=rh_data.active,
        actor_id=current_user.id
    )


@router.get("", response_model=List[RHOut])
async def list_rhs_endpoint(
    year: Optional[int] = Query(None, description="Filter by year"),
    active_only: bool = Query(False, description="Return only active restricted holidays"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """List restricted holidays (Admin-only)"""
    return list_rhs(db, year=year, active_only=active_only)


@router.get("/{rh_id}", response_model=RHOut)
async def get_rh_endpoint(
    rh_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Get a restricted holiday by ID (Admin-only)"""
    rh = get_rh(db, rh_id)
    if not rh:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restricted holiday with id {rh_id} not found"
        )
    return rh


@router.patch("/{rh_id}", response_model=RHOut)
async def update_rh_endpoint(
    rh_id: int,
    rh_data: RHUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Update a restricted holiday (Admin-only)"""
    return update_rh(
        db=db,
        rh_id=rh_id,
        name=rh_data.name,
        active=rh_data.active,
        actor_id=current_user.id
    )
