"""
Holiday management endpoints (HR-only)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Role, Employee
from app.schemas.holiday import HolidayCreate, HolidayUpdate, HolidayOut
from app.services.holiday_service import (
    create_holiday,
    list_holidays,
    get_holiday,
    update_holiday
)

router = APIRouter()


@router.post("", response_model=HolidayOut, status_code=201)
async def create_holiday_endpoint(
    holiday_data: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Create a new holiday (Admin-only)"""
    return create_holiday(
        db=db,
        year=holiday_data.year,
        holiday_date=holiday_data.date,
        name=holiday_data.name,
        active=holiday_data.active,
        actor_id=current_user.id
    )


@router.get("", response_model=List[HolidayOut])
async def list_holidays_endpoint(
    year: Optional[int] = Query(None, description="Filter by year"),
    active_only: bool = Query(False, description="Return only active holidays"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """List holidays (Admin-only)"""
    return list_holidays(db, year=year, active_only=active_only)


@router.get("/{holiday_id}", response_model=HolidayOut)
async def get_holiday_endpoint(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Get a holiday by ID (Admin-only)"""
    holiday = get_holiday(db, holiday_id)
    if not holiday:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holiday with id {holiday_id} not found"
        )
    return holiday


@router.patch("/{holiday_id}", response_model=HolidayOut)
async def update_holiday_endpoint(
    holiday_id: int,
    holiday_data: HolidayUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """Update a holiday (Admin-only)"""
    return update_holiday(
        db=db,
        holiday_id=holiday_id,
        name=holiday_data.name,
        active=holiday_data.active,
        actor_id=current_user.id
    )
