"""
Attendance session service: punch in/out with Asia/Kolkata work_date, admin edit/force-close.
All timestamps stored in UTC (server time). Persists punch_in_geo, punch_out_geo, device_id.
"""
import logging
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from fastapi import HTTPException, status

_log = logging.getLogger(__name__)

from app.core.config import settings
from app.models.attendance_session import (
    AttendanceSession,
    AttendanceEvent,
    SessionStatus,
    AttendanceEventType,
)
from app.models.employee import Employee, Role
from app.models.manager_department import ManagerDepartment
from app.services.audit_service import log_audit
from app.utils.json_serializer import sanitize_for_json
from app.utils.datetime_utils import now_utc, ensure_utc

TZ = ZoneInfo("Asia/Kolkata")


def get_work_date(utc_now: Optional[datetime] = None) -> date:
    """Return work_date (date in Asia/Kolkata) for the given UTC time (default now)."""
    now = utc_now or now_utc()
    return now.astimezone(TZ).date()


def punch_in(
    db: Session,
    employee_id: int,
    now: Optional[datetime] = None,
    *,
    source: str = "WEB",
    punch_in_ip: Optional[str] = None,
    punch_in_device_id: Optional[str] = None,
    punch_in_geo: Optional[dict] = None,
    is_mocked: Optional[bool] = None,
) -> AttendanceSession:
    """
    Punch in: use server UTC time (never client time). work_date = Asia/Kolkata date.
    """
    now = now or now_utc()
    work_date = get_work_date(now)

    if is_mocked is True and getattr(settings, "REJECT_MOCK_LOCATION_PUNCH", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mock location is not allowed for punch-in",
        )

    initial_status = SessionStatus.SUSPICIOUS if is_mocked is True else SessionStatus.OPEN

    existing = (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.work_date == work_date,
            AttendanceSession.status == SessionStatus.OPEN,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already punched in",
        )

    punch_in_geo_safe = sanitize_for_json(punch_in_geo) if punch_in_geo else None
    _log.debug(
        "punch_in persist: employee_id=%s punch_in_geo=%s punch_in_device_id=%s punch_in_ip=%s",
        employee_id, "set" if punch_in_geo_safe else None, punch_in_device_id, punch_in_ip,
    )
    session = AttendanceSession(
        employee_id=employee_id,
        work_date=work_date,
        punch_in_at=now,
        punch_out_at=None,
        status=initial_status,
        punch_in_source=source,
        punch_out_source=None,
        punch_in_ip=punch_in_ip,
        punch_out_ip=None,
        punch_in_device_id=punch_in_device_id,
        punch_out_device_id=None,
        punch_in_geo=punch_in_geo_safe,
        punch_out_geo=None,
        remarks=None,
    )
    db.add(session)
    db.flush()

    event = AttendanceEvent(
        session_id=session.id,
        employee_id=employee_id,
        event_type=AttendanceEventType.IN,
        event_at=now,
        meta_json=sanitize_for_json({
            "source": source,
            "ip": punch_in_ip,
            "device_id": punch_in_device_id,
            "geo": punch_in_geo,
        }) if any([source, punch_in_ip, punch_in_device_id, punch_in_geo]) else None,
        created_by=employee_id,
    )
    db.add(event)
    db.commit()
    db.refresh(session)

    log_audit(
        db=db,
        actor_id=employee_id,
        action="ATTENDANCE_SESSION_PUNCH_IN",
        entity_type="attendance_sessions",
        entity_id=session.id,
        meta={
            "work_date": str(work_date),
            "punch_in_at": now.isoformat(),
            "source": source,
        },
    )
    return session


def punch_out(
    db: Session,
    employee_id: int,
    now: Optional[datetime] = None,
    *,
    source: str = "WEB",
    punch_out_ip: Optional[str] = None,
    punch_out_device_id: Optional[str] = None,
    punch_out_geo: Optional[dict] = None,
    is_mocked: Optional[bool] = None,
) -> AttendanceSession:
    """
    Punch out: find OPEN or SUSPICIOUS session for employee for today (work_date); if none => 400 "No active session";
    if punch_out_at already set => 400 "Already punched out". When is_mocked=True: 403 if REJECT_MOCK_LOCATION_PUNCH else mark SUSPICIOUS.
    """
    now = now or now_utc()
    work_date = get_work_date(now)

    if is_mocked is True and getattr(settings, "REJECT_MOCK_LOCATION_PUNCH", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mock location is not allowed for punch-out",
        )

    session = (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.work_date == work_date,
            AttendanceSession.status.in_([SessionStatus.OPEN, SessionStatus.SUSPICIOUS]),
        )
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active session",
        )
    if session.punch_out_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already punched out",
        )

    session.punch_out_at = now
    session.status = SessionStatus.SUSPICIOUS if is_mocked is True else SessionStatus.CLOSED
    session.punch_out_source = source
    session.punch_out_ip = punch_out_ip
    session.punch_out_device_id = punch_out_device_id
    punch_out_geo_safe = sanitize_for_json(punch_out_geo) if punch_out_geo else None
    session.punch_out_geo = punch_out_geo_safe
    _log.debug(
        "punch_out persist: session_id=%s punch_out_geo=%s punch_out_device_id=%s",
        session.id, "set" if punch_out_geo_safe else None, punch_out_device_id,
    )

    event = AttendanceEvent(
        session_id=session.id,
        employee_id=employee_id,
        event_type=AttendanceEventType.OUT,
        event_at=now,
        meta_json=sanitize_for_json({
            "source": source,
            "ip": punch_out_ip,
            "device_id": punch_out_device_id,
            "geo": punch_out_geo,
        }) if any([source, punch_out_ip, punch_out_device_id, punch_out_geo]) else None,
        created_by=employee_id,
    )
    db.add(event)
    db.commit()
    db.refresh(session)

    log_audit(
        db=db,
        actor_id=employee_id,
        action="ATTENDANCE_SESSION_PUNCH_OUT",
        entity_type="attendance_sessions",
        entity_id=session.id,
        meta={
            "work_date": str(work_date),
            "punch_out_at": now.isoformat(),
            "source": source,
        },
    )
    return session


def get_today_session(db: Session, employee_id: int) -> Optional[AttendanceSession]:
    """Get today's session (by Asia/Kolkata work_date) for the employee."""
    work_date = get_work_date()
    return (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.work_date == work_date,
        )
        .first()
    )


def list_my_sessions(
    db: Session,
    employee_id: int,
    from_date: date,
    to_date: date,
) -> List[AttendanceSession]:
    """List sessions for the given employee in the date range (for /my endpoint)."""
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be less than or equal to to",
        )
    return (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.employee_id == employee_id,
            AttendanceSession.work_date >= from_date,
            AttendanceSession.work_date <= to_date,
        )
        .order_by(AttendanceSession.work_date.desc(), AttendanceSession.punch_in_at.desc())
        .all()
    )


def _get_sessions_for_employees(
    db: Session,
    employee_ids: List[int],
    from_date: date,
    to_date: date
) -> List[AttendanceSession]:
    """
    Get attendance sessions for multiple employees in date range.
    
    Args:
        db: Database session
        employee_ids: List of employee IDs to filter by
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        
    Returns:
        List of AttendanceSession instances ordered by work_date descending, punch_in_at descending
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be less than or equal to to",
        )
    
    if not employee_ids:
        return []
    
    return (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.employee_id.in_(employee_ids),
            AttendanceSession.work_date >= from_date,
            AttendanceSession.work_date <= to_date,
        )
        .order_by(AttendanceSession.work_date.desc(), AttendanceSession.punch_in_at.desc())
        .all()
    )


def _admin_employee_scope(db: Session, current_user: Employee):
    """Return list of employee_ids the current user can see (HR/ADMIN: all; MANAGER: department team)."""
    if current_user.role in (Role.HR, Role.ADMIN, Role.MD):
        return None  # no filter = all
    if current_user.role == Role.MANAGER:
        dept_ids = [
            row[0]
            for row in db.query(ManagerDepartment.department_id).filter(
                ManagerDepartment.manager_id == current_user.id
            ).all()
        ]
        if not dept_ids:
            return []  # no departments => no one
        from app.models.employee import Employee as Emp
        emp_ids = [row[0] for row in db.query(Emp.id).filter(Emp.department_id.in_(dept_ids)).all()]
        return emp_ids
    return [current_user.id]


def _admin_employee_scope_role_rank(db: Session, current_user: Employee):
    """
    Return list of employee_ids the current user can see based on role-rank hierarchy.
    ADMIN/MD/VP: None (all access)
    MANAGER: [current_user.id] + direct reportees
    EMPLOYEE: [current_user.id]
    """
    from app.services.leave_service import get_role_rank, get_subordinate_ids
    
    current_user_rank = get_role_rank(db, current_user)
    
    # ADMIN, MD, VP (role_rank <= 3): full access
    if current_user_rank <= 3:
        return None
    
    # MANAGER (role_rank == 4): self + direct reportees
    if current_user_rank == 4:
        subordinate_ids = get_subordinate_ids(db, current_user.id)
        return [current_user.id] + subordinate_ids
    
    # EMPLOYEE and others: only self
    return [current_user.id]


def admin_list_today(
    db: Session,
    current_user: Employee,
    department_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    q: Optional[str] = None,
) -> List[AttendanceSession]:
    """
    Admin: list today's sessions. HR/ADMIN see all; MANAGER only department/team.
    Filters: department_id, status (OPEN/CLOSED/AUTO_CLOSED), q (search name/emp_code).
    """
    work_date = get_work_date()
    from app.models.employee import Employee as Emp
    query = (
        db.query(AttendanceSession)
        .options(
            joinedload(AttendanceSession.employee).joinedload(Emp.department),
        )
        .join(Emp, AttendanceSession.employee_id == Emp.id)
        .filter(AttendanceSession.work_date == work_date)
    )

    emp_scope = _admin_employee_scope_role_rank(db, current_user)
    if emp_scope is not None:
        if emp_scope == []:
            return []
        query = query.filter(AttendanceSession.employee_id.in_(emp_scope))

    if department_id is not None:
        query = query.filter(Emp.department_id == department_id)
    if status_filter is not None:
        query = query.filter(AttendanceSession.status == status_filter)
    if q and q.strip():
        q = f"%{q.strip()}%"
        query = query.filter(
            (Emp.name.ilike(q)) | (Emp.emp_code.ilike(q))
        )

    return list(query.order_by(AttendanceSession.punch_in_at.desc()).all())


def admin_list(
    db: Session,
    current_user: Employee,
    from_date: date,
    to_date: date,
    employee_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status_filter: Optional[str] = None,
) -> List[AttendanceSession]:
    """
    Admin: list sessions in date range with optional employee_id, department_id, status.
    HR/ADMIN see all; MANAGER only department/team (or block if no team mapping).
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be less than or equal to to",
        )

    emp_scope = _admin_employee_scope_role_rank(db, current_user)
    if emp_scope is not None and emp_scope == []:
        return []

    from app.models.employee import Employee as Emp
    query = (
        db.query(AttendanceSession)
        .options(
            joinedload(AttendanceSession.employee).joinedload(Emp.department),
        )
        .join(Emp, AttendanceSession.employee_id == Emp.id)
        .filter(
            AttendanceSession.work_date >= from_date,
            AttendanceSession.work_date <= to_date,
        )
    )

    if emp_scope is not None:
        query = query.filter(AttendanceSession.employee_id.in_(emp_scope))
    if employee_id is not None:
        if emp_scope is not None and employee_id not in emp_scope:
            return []
        query = query.filter(AttendanceSession.employee_id == employee_id)
    if department_id is not None:
        query = query.filter(Emp.department_id == department_id)
    if status_filter is not None:
        query = query.filter(AttendanceSession.status == status_filter)

    return list(query.order_by(AttendanceSession.work_date.desc(), AttendanceSession.punch_in_at.desc()).all())


def admin_get_session(db: Session, session_id: int, current_user: Employee) -> Optional[AttendanceSession]:
    """Get session by id if current user is allowed (HR/ADMIN or MANAGER for their dept)."""
    session = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    if not session:
        return None
    emp_scope = _admin_employee_scope(db, current_user)
    if emp_scope is None:
        return session
    if session.employee_id in emp_scope:
        return session
    return None


def admin_update_session(
    db: Session,
    session_id: int,
    current_user: Employee,
    *,
    punch_in_at: Optional[datetime] = None,
    punch_out_at: Optional[datetime] = None,
    status: Optional[str] = None,
    remarks: Optional[str] = None,
) -> AttendanceSession:
    """
    Admin PATCH: update punch_in_at, punch_out_at, status, remarks.
    Create attendance_event(ADMIN_EDIT) and audit log. Only HR/ADMIN (or MANAGER for their dept).
    """
    session = admin_get_session(db, session_id, current_user)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if current_user.role == Role.MANAGER and not _admin_employee_scope_role_rank(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    meta = {}
    if punch_in_at is not None:
        punch_in_at_utc = ensure_utc(punch_in_at)
        meta["old_punch_in_at"] = session.punch_in_at.isoformat() if session.punch_in_at else None
        meta["new_punch_in_at"] = punch_in_at_utc.isoformat()
        session.punch_in_at = punch_in_at_utc
    if punch_out_at is not None:
        punch_out_at_utc = ensure_utc(punch_out_at)
        meta["old_punch_out_at"] = session.punch_out_at.isoformat() if session.punch_out_at else None
        meta["new_punch_out_at"] = punch_out_at_utc.isoformat()
        session.punch_out_at = punch_out_at_utc
    if status is not None:
        meta["old_status"] = session.status.value if hasattr(session.status, "value") else str(session.status)
        meta["new_status"] = status
        session.status = SessionStatus(status)
    if remarks is not None:
        session.remarks = remarks
        meta["remarks"] = remarks

    meta["edited_by"] = current_user.id
    meta["edited_at"] = now_utc().isoformat()

    event = AttendanceEvent(
        session_id=session.id,
        employee_id=session.employee_id,
        event_type=AttendanceEventType.ADMIN_EDIT,
        event_at=now_utc(),
        meta_json=sanitize_for_json(meta),
        created_by=current_user.id,
    )
    db.add(event)
    db.commit()
    db.refresh(session)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="ATTENDANCE_SESSION_ADMIN_EDIT",
        entity_type="attendance_sessions",
        entity_id=session.id,
        meta=sanitize_for_json({"session_id": session_id, **meta}),
    )
    return session


def admin_force_close(
    db: Session,
    session_id: int,
    current_user: Employee,
    now: Optional[datetime] = None,
) -> AttendanceSession:
    """
    Admin: set punch_out_at=now, status=AUTO_CLOSED; create event AUTO_OUT and audit log.
    """
    session = admin_get_session(db, session_id, current_user)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if current_user.role == Role.MANAGER and not _admin_employee_scope_role_rank(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    now = now or now_utc()
    if session.punch_out_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already closed",
        )

    session.punch_out_at = now
    session.status = SessionStatus.AUTO_CLOSED

    meta = {
        "forced_by": current_user.id,
        "forced_at": now.isoformat(),
    }
    event = AttendanceEvent(
        session_id=session.id,
        employee_id=session.employee_id,
        event_type=AttendanceEventType.AUTO_OUT,
        event_at=now,
        meta_json=sanitize_for_json(meta),
        created_by=current_user.id,
    )
    db.add(event)
    db.commit()
    db.refresh(session)

    log_audit(
        db=db,
        actor_id=current_user.id,
        action="ATTENDANCE_SESSION_FORCE_CLOSE",
        entity_type="attendance_sessions",
        entity_id=session.id,
        meta=sanitize_for_json({"session_id": session_id, **meta}),
    )
    return session
