"""
Holiday calendar service - business logic for holiday management
"""
from datetime import date, datetime, timezone
from typing import List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException, status
from app.models.holiday import Holiday, RestrictedHoliday
from app.services.audit_service import log_audit


def create_holiday(
    db: Session,
    year: int,
    holiday_date: date,
    name: str,
    active: bool = True,
    actor_id: int = None
) -> Holiday:
    """
    Create a new holiday
    
    Args:
        db: Database session
        year: Calendar year
        holiday_date: Holiday date
        name: Holiday name
        active: Whether holiday is active
        actor_id: ID of user creating the holiday
    
    Returns:
        Created Holiday instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate date falls within year
    if holiday_date.year != year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date {holiday_date} does not fall within year {year}"
        )
    
    # Check for duplicate
    existing = db.query(Holiday).filter(
        Holiday.year == year,
        Holiday.date == holiday_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Holiday already exists for date {holiday_date} in year {year}"
        )
    
    # Explicitly set created_at/updated_at to avoid SQLite issues with server_default
    now = datetime.now(timezone.utc)
    holiday = Holiday(
        year=year,
        date=holiday_date,
        name=name,
        active=active,
        created_at=now,
        updated_at=now
    )
    
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    
    # Log audit
    if actor_id:
        log_audit(
            db=db,
            actor_id=actor_id,
            action="HOLIDAY_CREATE",
            entity_type="holidays",
            entity_id=holiday.id,
            meta={
                "year": year,
                "date": str(holiday_date),
                "name": name
            }
        )
    
    return holiday


def list_holidays(
    db: Session,
    year: Optional[int] = None,
    active_only: bool = False
) -> List[Holiday]:
    """
    List holidays
    
    Args:
        db: Database session
        year: Optional year filter
        active_only: If True, return only active holidays
    
    Returns:
        List of Holiday instances
    """
    query = db.query(Holiday)
    
    if year:
        query = query.filter(Holiday.year == year)
    
    if active_only:
        query = query.filter(Holiday.active == True)
    
    return query.order_by(Holiday.date).all()


def get_holiday(db: Session, holiday_id: int) -> Optional[Holiday]:
    """Get a holiday by ID"""
    return db.query(Holiday).filter(Holiday.id == holiday_id).first()


def update_holiday(
    db: Session,
    holiday_id: int,
    name: Optional[str] = None,
    active: Optional[bool] = None,
    actor_id: int = None
) -> Holiday:
    """
    Update a holiday
    
    Args:
        db: Database session
        holiday_id: Holiday ID
        name: Optional new name
        active: Optional new active status
        actor_id: ID of user updating the holiday
    
    Returns:
        Updated Holiday instance
    
    Raises:
        HTTPException: If holiday not found
    """
    holiday = get_holiday(db, holiday_id)
    if not holiday:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holiday with id {holiday_id} not found"
        )
    
    if name is not None:
        holiday.name = name
    if active is not None:
        holiday.active = active
    
    # Explicitly update updated_at for SQLite compatibility
    holiday.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(holiday)
    
    # Log audit
    if actor_id:
        log_audit(
            db=db,
            actor_id=actor_id,
            action="HOLIDAY_UPDATE",
            entity_type="holidays",
            entity_id=holiday.id,
            meta={
                "name": name,
                "active": active
            }
        )
    
    return holiday


def get_holidays_in_range(
    db: Session,
    from_date: date,
    to_date: date
) -> Set[date]:
    """
    Get set of active holiday dates within the given date range
    
    Args:
        db: Database session
        from_date: Start date (inclusive)
        to_date: End date (inclusive)
    
    Returns:
        Set of holiday dates
    """
    holidays = db.query(Holiday.date).filter(
        and_(
            Holiday.active == True,
            Holiday.date >= from_date,
            Holiday.date <= to_date
        )
    ).all()
    
    return {holiday_date for (holiday_date,) in holidays}


def create_rh(
    db: Session,
    year: int,
    rh_date: date,
    name: str,
    active: bool = True,
    actor_id: int = None
) -> RestrictedHoliday:
    """
    Create a new restricted holiday
    
    Args:
        db: Database session
        year: Calendar year
        rh_date: Restricted holiday date
        name: Restricted holiday name
        active: Whether restricted holiday is active
        actor_id: ID of user creating the restricted holiday
    
    Returns:
        Created RestrictedHoliday instance
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate date falls within year
    if rh_date.year != year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Date {rh_date} does not fall within year {year}"
        )
    
    # Check for duplicate
    existing = db.query(RestrictedHoliday).filter(
        RestrictedHoliday.year == year,
        RestrictedHoliday.date == rh_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Restricted holiday already exists for date {rh_date} in year {year}"
        )
    
    # Explicitly set created_at/updated_at to avoid SQLite issues with server_default
    now = datetime.now(timezone.utc)
    rh = RestrictedHoliday(
        year=year,
        date=rh_date,
        name=name,
        active=active,
        created_at=now,
        updated_at=now
    )
    
    db.add(rh)
    db.commit()
    db.refresh(rh)
    
    # Log audit
    if actor_id:
        log_audit(
            db=db,
            actor_id=actor_id,
            action="RH_CREATE",
            entity_type="restricted_holidays",
            entity_id=rh.id,
            meta={
                "year": year,
                "date": str(rh_date),
                "name": name
            }
        )
    
    return rh


def list_rhs(
    db: Session,
    year: Optional[int] = None,
    active_only: bool = False
) -> List[RestrictedHoliday]:
    """
    List restricted holidays
    
    Args:
        db: Database session
        year: Optional year filter
        active_only: If True, return only active restricted holidays
    
    Returns:
        List of RestrictedHoliday instances
    """
    query = db.query(RestrictedHoliday)
    
    if year:
        query = query.filter(RestrictedHoliday.year == year)
    
    if active_only:
        query = query.filter(RestrictedHoliday.active == True)
    
    return query.order_by(RestrictedHoliday.date).all()


def get_rh(db: Session, rh_id: int) -> Optional[RestrictedHoliday]:
    """Get a restricted holiday by ID"""
    return db.query(RestrictedHoliday).filter(RestrictedHoliday.id == rh_id).first()


def update_rh(
    db: Session,
    rh_id: int,
    name: Optional[str] = None,
    active: Optional[bool] = None,
    actor_id: int = None
) -> RestrictedHoliday:
    """
    Update a restricted holiday
    
    Args:
        db: Database session
        rh_id: Restricted holiday ID
        name: Optional new name
        active: Optional new active status
        actor_id: ID of user updating the restricted holiday
    
    Returns:
        Updated RestrictedHoliday instance
    
    Raises:
        HTTPException: If restricted holiday not found
    """
    rh = get_rh(db, rh_id)
    if not rh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Restricted holiday with id {rh_id} not found"
        )
    
    if name is not None:
        rh.name = name
    if active is not None:
        rh.active = active
    
    # Explicitly update updated_at for SQLite compatibility
    rh.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(rh)
    
    # Log audit
    if actor_id:
        log_audit(
            db=db,
            actor_id=actor_id,
            action="RH_UPDATE",
            entity_type="restricted_holidays",
            entity_id=rh.id,
            meta={
                "name": name,
                "active": active
            }
        )
    
    return rh


def is_rh_date(db: Session, year: int, check_date: date) -> bool:
    """
    Check if a date is a restricted holiday
    
    Args:
        db: Database session
        year: Calendar year
        check_date: Date to check
    
    Returns:
        True if date is an active restricted holiday, False otherwise
    """
    rh = db.query(RestrictedHoliday).filter(
        RestrictedHoliday.year == year,
        RestrictedHoliday.date == check_date,
        RestrictedHoliday.active == True
    ).first()
    
    return rh is not None


def get_rh_dates_in_range(
    db: Session,
    from_date: date,
    to_date: date
) -> Set[date]:
    """
    Get set of active restricted holiday dates within the given date range
    
    Args:
        db: Database session
        from_date: Start date (inclusive)
        to_date: End date (inclusive)
    
    Returns:
        Set of restricted holiday dates
    """
    rhs = db.query(RestrictedHoliday.date).filter(
        and_(
            RestrictedHoliday.active == True,
            RestrictedHoliday.date >= from_date,
            RestrictedHoliday.date <= to_date
        )
    ).all()
    
    return {rh_date for (rh_date,) in rhs}
