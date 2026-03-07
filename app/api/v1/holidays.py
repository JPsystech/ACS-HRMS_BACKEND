"""
Holiday management endpoints (HR-only)
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from datetime import datetime
import re
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.models.employee import Role, Employee
from app.models.holiday import Holiday
from app.schemas.holiday import HolidayCreate, HolidayUpdate, HolidayOut
from app.services.holiday_service import (
    create_holiday,
    list_holidays,
    get_holiday,
    update_holiday
)
from app.services.r2_storage import get_r2_storage_service

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
        description=holiday_data.description,
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
        description=holiday_data.description,
        actor_id=current_user.id
    )


@router.post("/{holiday_id}/image", response_model=HolidayOut)
async def upload_holiday_image(
    holiday_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    h = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not h:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")

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
    object_key = f"holidays/{timestamp}_{safe_filename}"

    try:
        ok = get_r2_storage_service().upload_file(
            file_data=file_data,
            object_key=object_key,
            content_type=file.content_type
        )
        if not ok:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")
        h.image_key = object_key
        db.add(h)
        db.commit()
        db.refresh(h)
        return h
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")


@router.get("/image/{key:path}")
async def get_holiday_image(
    key: str,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    try:
        file_data = get_r2_storage_service().get_file(key)
        if file_data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

        content_type = "image/jpeg"
        lk = key.lower()
        if lk.endswith(".png"):
            content_type = "image/png"
        elif lk.endswith(".webp"):
            content_type = "image/webp"
        headers = {
            "Cache-Control": "public, max-age=3600",
            "Content-Type": content_type,
        }
        return StreamingResponse(iter([file_data]), headers=headers, media_type=content_type)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve image")
