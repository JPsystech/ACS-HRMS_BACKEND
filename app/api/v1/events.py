"""
Company events API endpoints
HR-only endpoints for managing company events/celebrations
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.core.deps import get_db, get_current_user, require_roles
from app.models.employee import Employee, Role
from app.models.event import CompanyEvent
from app.schemas.event import CompanyEventCreate, CompanyEventUpdate, CompanyEventOut
from app.services.audit_service import log_audit
from app.services.r2_storage import get_r2_storage_service
from app.core.config import settings
from datetime import datetime
import re

router = APIRouter()


@router.post("", response_model=CompanyEventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: CompanyEventCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """Create a company event (HR only)"""
    # Check for duplicate
    existing = db.query(CompanyEvent).filter(
        CompanyEvent.year == event_data.year,
        CompanyEvent.date == event_data.date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Company event already exists for date {event_data.date} in year {event_data.year}"
        )
    
    event = CompanyEvent(
        year=event_data.year,
        date=event_data.date,
        name=event_data.name,
        active=event_data.active,
        description=event_data.description,
        image_url=event_data.image_url,
        location=event_data.location
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="EVENT_CREATE",
        entity_type="company_events",
        entity_id=event.id,
        meta={"year": event_data.year, "date": str(event_data.date), "name": event_data.name}
    )
    
    return event


@router.get("", response_model=List[CompanyEventOut])
async def list_events(
    year: Optional[int] = Query(None, description="Filter by year"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """List company events (all authenticated users can view)"""
    query = db.query(CompanyEvent)
    
    if year:
        query = query.filter(CompanyEvent.year == year)
    if active is not None:
        query = query.filter(CompanyEvent.active == active)
    
    return query.order_by(CompanyEvent.date.asc()).all()


@router.get("/{event_id}", response_model=CompanyEventOut)
async def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """Get company event by ID"""
    event = db.query(CompanyEvent).filter(CompanyEvent.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company event not found"
        )
    return event


@router.patch("/{event_id}", response_model=CompanyEventOut)
async def update_event(
    event_id: int,
    event_data: CompanyEventUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """Update company event (HR only)"""
    event = db.query(CompanyEvent).filter(CompanyEvent.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company event not found"
        )
    
    if event_data.name is not None:
        event.name = event_data.name
    if event_data.active is not None:
        event.active = event_data.active
    if event_data.description is not None:
        event.description = event_data.description
    if event_data.image_url is not None:
        event.image_url = event_data.image_url
    if event_data.location is not None:
        event.location = event_data.location
    
    db.commit()
    db.refresh(event)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="EVENT_UPDATE",
        entity_type="company_events",
        entity_id=event.id,
        meta={"name": event.name, "active": event.active}
    )
    
    return event


@router.post("/{event_id}/image", response_model=CompanyEventOut)
async def upload_event_image(
    event_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    event = db.query(CompanyEvent).filter(CompanyEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company event not found")

    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Allowed: jpg, jpeg, png, webp")

    max_size = 5 * 1024 * 1024
    file_data = await file.read()
    if len(file_data) > max_size:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large. Maximum size: 5MB")

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_filename = re.sub(r'[^a-zA-Z0-9.-]', '', file.filename or "image")
    if not safe_filename:
        safe_filename = "image"
    object_key = f"events/{timestamp}_{safe_filename}"

    ok = get_r2_storage_service().upload_file(
        file_data=file_data,
        object_key=object_key,
        content_type=file.content_type
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed")

    base = settings.PUBLIC_BASE_URL.rstrip("/")
    event.image_url = f"{base}/api/v1/events/image/{object_key}"
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/image/{key:path}")
async def get_event_image(
    key: str,
    db: Session = Depends(get_db),
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


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    """Delete company event (HR only)"""
    event = db.query(CompanyEvent).filter(CompanyEvent.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company event not found"
        )
    
    db.delete(event)
    db.commit()
    
    # Log audit
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="EVENT_DELETE",
        entity_type="company_events",
        entity_id=event_id,
        meta={"year": event.year, "date": str(event.date), "name": event.name}
    )
