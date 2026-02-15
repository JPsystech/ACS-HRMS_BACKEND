"""
Attendance service - business logic for attendance management
"""
from datetime import datetime, date, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status
from app.models.attendance import AttendanceLog
from app.models.employee import Employee, Role
from app.models.manager_department import ManagerDepartment
from app.services.audit_service import log_audit


def get_punch_date() -> date:
    """
    Get punch date from server UTC time.
    
    Returns the current date in UTC timezone.
    Note: For production, this may need to be adjusted to Asia/Kolkata timezone
    for determining the "business day", but for now we use UTC consistently.
    """
    return datetime.now(timezone.utc).date()


def punch_in(
    db: Session,
    employee_id: int,
    lat: float,
    lng: float,
    source: str = "mobile"
) -> AttendanceLog:
    """
    Record employee punch-in with GPS coordinates
    
    Args:
        db: Database session
        employee_id: ID of the employee punching in
        lat: GPS latitude
        lng: GPS longitude
        source: Source of punch-in (e.g., "mobile", "web")
    
    Returns:
        Created AttendanceLog instance
    
    Raises:
        HTTPException: If employee already punched in today (409 Conflict)
    """
    # Determine punch_date from server UTC date
    punch_date = get_punch_date()
    
    # Check if employee already punched in today
    existing = db.query(AttendanceLog).filter(
        AttendanceLog.employee_id == employee_id,
        AttendanceLog.punch_date == punch_date
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already punched in today"
        )
    
    # Create attendance log entry
    attendance_log = AttendanceLog(
        employee_id=employee_id,
        punch_date=punch_date,
        in_time=datetime.now(timezone.utc),  # Server UTC timestamp
        in_lat=lat,
        in_lng=lng,
        source=source
    )
    
    db.add(attendance_log)
    db.commit()
    db.refresh(attendance_log)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=employee_id,
        action="ATTENDANCE_PUNCH_IN",
        entity_type="attendance_logs",
        entity_id=attendance_log.id,
        meta={
            "punch_date": str(punch_date),
            "lat": lat,
            "lng": lng,
            "source": source
        }
    )
    
    return attendance_log


def punch_out(
    db: Session,
    employee_id: int,
    lat: float,
    lng: float,
    source: str = "mobile"
) -> AttendanceLog:
    """
    Record employee punch-out with GPS coordinates
    
    Args:
        db: Database session
        employee_id: ID of the employee punching out
        lat: GPS latitude
        lng: GPS longitude
        source: Source of punch-out (e.g., "mobile", "web")
    
    Returns:
        Updated AttendanceLog instance
    
    Raises:
        HTTPException: If punch-in not found (404) or already punched out (409)
    """
    # Determine punch_date from server UTC date (same method as punch_in)
    punch_date = get_punch_date()
    
    # Fetch attendance log for today
    attendance_log = db.query(AttendanceLog).filter(
        AttendanceLog.employee_id == employee_id,
        AttendanceLog.punch_date == punch_date
    ).first()
    
    if not attendance_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Punch-in not found for today"
        )
    
    if attendance_log.out_time is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already punched out today"
        )
    
    # Validate out_time > in_time (should be naturally true, but check anyway)
    now = datetime.now(timezone.utc)
    if now <= attendance_log.in_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Punch-out time must be after punch-in time"
        )
    
    # Update record with punch-out details
    attendance_log.out_time = now
    attendance_log.out_lat = lat
    attendance_log.out_lng = lng
    # Keep original source; optionally could add out_source field later
    
    db.commit()
    db.refresh(attendance_log)
    
    # Log audit
    log_audit(
        db=db,
        actor_id=employee_id,
        action="ATTENDANCE_PUNCH_OUT",
        entity_type="attendance_logs",
        entity_id=attendance_log.id,
        meta={
            "punch_date": str(punch_date),
            "lat": lat,
            "lng": lng,
            "source": source
        }
    )
    
    return attendance_log


def list_attendance(
    db: Session,
    current_user: Employee,
    from_date: date,
    to_date: date
) -> List[AttendanceLog]:
    """
    List attendance records with role-based scoping
    
    Args:
        db: Database session
        current_user: Current authenticated user
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
    
    Returns:
        List of AttendanceLog instances ordered by punch_date, employee_id
    
    Role-based scoping:
        - HR: can list all employees
        - MANAGER: can list only employees in departments mapped to them (manager_departments)
        - EMPLOYEE: only their own records
    """
    # Validate date range
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be less than or equal to to_date"
        )
    
    # Base query
    query = db.query(AttendanceLog).filter(
        AttendanceLog.punch_date >= from_date,
        AttendanceLog.punch_date <= to_date
    )
    
    # Apply role-based scoping
    if current_user.role == Role.HR:
        # HR can see all employees
        pass
    elif current_user.role == Role.MANAGER:
        # MANAGER can see only employees in departments mapped to them
        # Get department IDs that this manager manages
        manager_dept_ids = [
            dept_id for (dept_id,) in db.query(ManagerDepartment.department_id).filter(
                ManagerDepartment.manager_id == current_user.id
            ).all()
        ]
        
        if manager_dept_ids:
            # Filter employees by their department_id being in manager's departments
            employee_ids = [
                emp_id for (emp_id,) in db.query(Employee.id).filter(
                    Employee.department_id.in_(manager_dept_ids)
                ).all()
            ]
            
            if employee_ids:
                query = query.filter(AttendanceLog.employee_id.in_(employee_ids))
            else:
                # No employees in managed departments, return empty result
                query = query.filter(AttendanceLog.employee_id == -1)  # Impossible condition
        else:
            # Manager has no departments mapped, return empty result
            query = query.filter(AttendanceLog.employee_id == -1)  # Impossible condition
    else:
        # EMPLOYEE can see only their own records
        query = query.filter(AttendanceLog.employee_id == current_user.id)
    
    # Order by punch_date, then employee_id
    return query.order_by(AttendanceLog.punch_date, AttendanceLog.employee_id).all()
