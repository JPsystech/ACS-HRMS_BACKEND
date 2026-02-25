"""
Admin attendance endpoints: today list, date-range list, PATCH session, force-close.
HR and ADMIN can access all; MANAGER only if they have team mapping (see require_admin_attendance).
Returns production-level punch metadata: punch_in_geo, punch_out_geo, punch_in_ip, punch_out_ip,
punch_in_device_id, punch_out_device_id, punch_in_source, punch_out_source.
"""
import json
from datetime import date
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user, require_admin_attendance
from app.models.employee import Employee
from app.models.attendance_session import AttendanceSession
from app.schemas.attendance import (
    SessionDto,
    AdminSessionDto,
    AdminSessionUpdateRequest,
    AdminSessionListResponse,
)
from app.services import attendance_session_service as svc

router = APIRouter()


def _geo_to_dict(geo: Any) -> Optional[dict]:
    """
    Ensure geo is a plain dict for JSON response.
    Handles: None, dict, SQLAlchemy JSON type, or string (e.g. SQLite JSON stored as text).
    """
    if geo is None:
        return None
    if isinstance(geo, dict):
        return geo
    if isinstance(geo, str):
        try:
            return json.loads(geo)
        except (TypeError, ValueError):
            return None
    if hasattr(geo, "items"):
        return dict(geo)
    return None


def _session_to_admin_dto(s: AttendanceSession) -> AdminSessionDto:
    worked_minutes = None
    if s.punch_out_at and s.punch_in_at:
        delta = s.punch_out_at - s.punch_in_at
        worked_minutes = int(delta.total_seconds() / 60)
    status_val = s.status.value if hasattr(s.status, "value") else str(s.status)
    return AdminSessionDto(
        id=s.id,
        employee_id=s.employee_id,
        work_date=s.work_date,
        punch_in_at=s.punch_in_at,
        punch_out_at=s.punch_out_at,
        status=status_val,
        punch_in_source=s.punch_in_source,
        punch_out_source=s.punch_out_source,
        punch_in_ip=s.punch_in_ip,
        punch_out_ip=s.punch_out_ip,
        punch_in_device_id=s.punch_in_device_id,
        punch_out_device_id=s.punch_out_device_id,
        punch_in_geo=_geo_to_dict(s.punch_in_geo),
        punch_out_geo=_geo_to_dict(s.punch_out_geo),
        remarks=s.remarks,
        created_at=s.created_at,
        updated_at=s.updated_at,
        employee_name=s.employee.name if s.employee else None,
        department_name=s.employee.department.name if s.employee and s.employee.department else None,
        worked_minutes=worked_minutes,
    )


@router.get("/today", response_model=List[AdminSessionDto])
async def admin_today(
    department_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="OPEN, CLOSED, AUTO_CLOSED, SUSPICIOUS"),
    q: Optional[str] = Query(None, description="Search by name or emp_code"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_attendance),
):
    """GET /api/v1/admin/attendance/today - list today's sessions with optional filters."""
    sessions = svc.admin_list_today(
        db, current_user,
        department_id=department_id,
        status_filter=status,
        q=q,
    )
    return [_session_to_admin_dto(s) for s in sessions]


@router.get("", response_model=AdminSessionListResponse)
async def admin_list(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    employee_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_attendance),
):
    """GET /api/v1/admin/attendance?from=&to=&employee_id=&department_id=&status="""
    sessions = svc.admin_list(
        db, current_user,
        from_date=from_date,
        to_date=to_date,
        employee_id=employee_id,
        department_id=department_id,
        status_filter=status,
    )
    items = [_session_to_admin_dto(s) for s in sessions]
    return AdminSessionListResponse(items=items, total=len(items))


@router.patch("/{session_id}", response_model=SessionDto)
async def admin_patch_session(
    session_id: int,
    body: AdminSessionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_attendance),
):
    """PATCH /api/v1/admin/attendance/{session_id} - edit punch_in_at, punch_out_at, status, remarks. Creates ADMIN_EDIT event."""
    session = svc.admin_update_session(
        db, session_id, current_user,
        punch_in_at=body.punch_in_at,
        punch_out_at=body.punch_out_at,
        status=body.status,
        remarks=body.remarks,
    )
    return SessionDto.model_validate(session)


@router.post("/{session_id}/force-close", response_model=SessionDto)
async def admin_force_close(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_attendance),
):
    """POST /api/v1/admin/attendance/{session_id}/force-close - set punch_out_at=now, status=AUTO_CLOSED. Creates AUTO_OUT event."""
    session = svc.admin_force_close(db, session_id, current_user)
    return SessionDto.model_validate(session)
