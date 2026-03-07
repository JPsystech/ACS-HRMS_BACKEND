"""
Restricted Holiday management endpoints (HR-only)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from datetime import datetime
import re
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Role, Employee
from app.models.holiday import RestrictedHoliday
from app.schemas.holiday import RHCreate, RHUpdate, RHOut
from app.services.holiday_service import (
    create_rh,
    list_rhs,
    get_rh,
    update_rh
)
from app.services.r2_storage import get_r2_storage_service

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
        description=rh_data.description,
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
        description=rh_data.description,
        actor_id=current_user.id
    )


@router.post("/{rh_id}/image", response_model=RHOut)
async def upload_restricted_holiday_image(
    rh_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    rh = db.query(RestrictedHoliday).filter(RestrictedHoliday.id == rh_id).first()
    if not rh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restricted holiday not found")

    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: jpg, jpeg, png, webp"
        )

    max_size = 5 * 1024 * 1024
    file_data = await file.read()
    if len(file_data) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size: 5MB"
        )

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_filename = re.sub(r'[^a-zA-Z0-9.-]', '', file.filename or "image")
    if not safe_filename:
        safe_filename = "image"
    object_key = f"restricted_holidays/{timestamp}_{safe_filename}"

    try:
        ok = get_r2_storage_service().upload_file(
            file_data=file_data,
            object_key=object_key,
            content_type=file.content_type
        )
        if not ok:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")
        rh.image_key = object_key
        db.add(rh)
        db.commit()
        db.refresh(rh)
        return rh
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")
