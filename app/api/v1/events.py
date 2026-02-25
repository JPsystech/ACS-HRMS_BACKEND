"""
Company events API endpoints
HR-only endpoints for managing company events/celebrations
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from app.core.deps import get_db, get_current_user, require_roles
from app.models.employee import Employee, Role
from app.models.event import CompanyEvent
from app.schemas.event import CompanyEventCreate, CompanyEventUpdate, CompanyEventOut
from app.services.audit_service import log_audit

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
        active=event_data.active
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
