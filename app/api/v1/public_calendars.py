"""
Public calendar endpoints (any authenticated user can read)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.schemas.holiday import HolidayOut, RHOut
from app.services.holiday_service import list_holidays, list_rhs

router = APIRouter()


@router.get("/holidays", response_model=List[HolidayOut])
async def get_holidays_calendar(
    year: Optional[int] = Query(None, description="Filter by year"),
    active_only: bool = Query(True, description="Return only active holidays"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Get holiday calendar (any authenticated user)"""
    return list_holidays(db, year=year, active_only=active_only)


@router.get("/restricted-holidays", response_model=List[RHOut])
async def get_restricted_holidays_calendar(
    year: Optional[int] = Query(None, description="Filter by year"),
    active_only: bool = Query(True, description="Return only active restricted holidays"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Get restricted holiday calendar (any authenticated user)"""
    return list_rhs(db, year=year, active_only=active_only)
