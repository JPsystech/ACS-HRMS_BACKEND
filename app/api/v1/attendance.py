"""
Attendance endpoints (session-based punch in/out + legacy list).
Employee/MANAGER/HR/ADMIN can call their own attendance; /today and /my return only own records.
Accepts geo (dict), punch_in_geo/punch_out_geo, or lat/lng; device_id (or deviceId); persists to AttendanceSession.
"""
import logging
from datetime import date
from typing import Optional, Any, Dict
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.schemas.attendance import (
    PunchInRequest,
    PunchOutRequest,
    AttendanceOut,
    AttendanceListResponse,
    AttendanceListItemOut,
    SessionPunchInRequest,
    SessionPunchOutRequest,
    SessionDto,
    SessionListResponse,
)
from app.services.attendance_service import punch_in as legacy_punch_in, punch_out as legacy_punch_out, list_attendance
from app.services.attendance_session_service import (
    punch_in as session_punch_in,
    punch_out as session_punch_out,
    get_today_session,
    list_my_sessions,
)
from app.utils.datetime_utils import now_utc, iso_8601_utc, iso_ist, to_ist

router = APIRouter()
_log = logging.getLogger(__name__)


def _client_ip(request: Request) -> Optional[str]:
    """Client IP: X-Forwarded-For (first hop) when behind proxy, else request.client.host."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _geo_to_dict(geo: Any) -> Optional[Dict[str, Any]]:
    """Convert geo to dict for storage. Accepts GeoSchema (model_dump), dict with lat/lng, or None."""
    if geo is None:
        return None
    if hasattr(geo, "model_dump"):
        d = geo.model_dump(exclude_none=True)
        if d.get("lat") is not None and d.get("lng") is not None:
            return d
        return None
    if isinstance(geo, dict) and geo.get("lat") is not None and geo.get("lng") is not None:
        return dict(geo)
    return None


def _build_geo(
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    accuracy: Optional[float] = None,
    address: Optional[str] = None,
    captured_at: Optional[Any] = None,
    is_mocked: Optional[bool] = None,
    source: Optional[str] = None,
    provider: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build punch_*_geo JSON (lat, lng, accuracy, provider, address, captured_at, is_mocked, source). Returns None if lat/lng not both provided."""
    if lat is None or lng is None:
        return None
    captured_at_iso = captured_at.isoformat() if hasattr(captured_at, "isoformat") else captured_at
    return {
        "lat": lat,
        "lng": lng,
        "accuracy": accuracy,
        "provider": provider,
        "address": address,
        "captured_at": captured_at_iso,
        "is_mocked": is_mocked,
        "source": source,
    }


# --- Session-based (new) ---


@router.get("/tz-check")
async def tz_check():
    """
    Self-check: server UTC now, server IST now, and confirmation that API uses IST (+05:30).
    All API datetime fields are returned in Asia/Kolkata (IST); never Z.
    """
    now_utc_dt = now_utc()
    now_ist_dt = to_ist(now_utc_dt)
    return {
        "now_utc": iso_8601_utc(now_utc_dt),
        "now_ist": iso_ist(now_utc_dt),
        "message": "All API datetimes are returned in IST (Asia/Kolkata, +05:30). DB storage remains UTC.",
        "conversion_confirmed": now_ist_dt is not None and now_utc_dt is not None,
    }


@router.post("/punch-in", response_model=SessionDto, status_code=201)
async def punch_in_endpoint(
    request: Request,
    body: Optional[SessionPunchInRequest] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Session punch-in for current user. Work date = Asia/Kolkata today.
    Optional live GPS: lat, lng, accuracy, captured_at, is_mocked, address, device_id, source.
    If already punched in for today => 400 "Already punched in".
    """
    payload = body or SessionPunchInRequest()
    # Resolve geo: 1) build from lat/lng, 2) punch_in_geo, 3) geo (client-friendly key)
    punch_in_geo = None
    if payload.lat is not None and payload.lng is not None:
        punch_in_geo = _build_geo(
            lat=payload.lat,
            lng=payload.lng,
            accuracy=payload.accuracy,
            address=payload.address,
            captured_at=payload.captured_at,
            is_mocked=payload.is_mocked,
            source=payload.source,
            provider=getattr(payload, "provider", None),
        )
    if punch_in_geo is None and payload.punch_in_geo:
        punch_in_geo = _geo_to_dict(payload.punch_in_geo)
    if punch_in_geo is None and getattr(payload, "geo", None):
        punch_in_geo = _geo_to_dict(payload.geo)
    punch_in_device_id = getattr(payload, "device_id", None) or payload.punch_in_device_id
    punch_in_ip = payload.punch_in_ip or _client_ip(request)

    _log.debug(
        "punch_in: payload_keys=%s punch_in_geo=%s punch_in_device_id=%s",
        list(payload.model_dump().keys()) if hasattr(payload, "model_dump") else [],
        "dict" if punch_in_geo else None,
        punch_in_device_id,
    )

    session = session_punch_in(
        db=db,
        employee_id=current_user.id,
        source=payload.source,
        punch_in_ip=punch_in_ip,
        punch_in_device_id=punch_in_device_id,
        punch_in_geo=punch_in_geo,
        is_mocked=payload.is_mocked,
    )
    return SessionDto.model_validate(session)


@router.post("/punch-out", response_model=SessionDto)
async def punch_out_endpoint(
    request: Request,
    body: Optional[SessionPunchOutRequest] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Session punch-out for current user. If no open session for today => 400 "No active session".
    Optional live GPS: lat, lng, accuracy, captured_at, is_mocked, address, device_id, source.
    """
    payload = body or SessionPunchOutRequest()
    punch_out_geo = None
    if payload.lat is not None and payload.lng is not None:
        punch_out_geo = _build_geo(
            lat=payload.lat,
            lng=payload.lng,
            accuracy=payload.accuracy,
            address=payload.address,
            captured_at=payload.captured_at,
            is_mocked=payload.is_mocked,
            source=payload.source,
            provider=getattr(payload, "provider", None),
        )
    if punch_out_geo is None and payload.punch_out_geo:
        punch_out_geo = _geo_to_dict(payload.punch_out_geo)
    if punch_out_geo is None and getattr(payload, "geo", None):
        punch_out_geo = _geo_to_dict(payload.geo)
    punch_out_device_id = getattr(payload, "device_id", None) or payload.punch_out_device_id
    punch_out_ip = payload.punch_out_ip or _client_ip(request)

    _log.debug(
        "punch_out: punch_out_geo=%s punch_out_device_id=%s",
        "dict" if punch_out_geo else None,
        punch_out_device_id,
    )

    session = session_punch_out(
        db=db,
        employee_id=current_user.id,
        source=payload.source,
        punch_out_ip=punch_out_ip,
        punch_out_device_id=punch_out_device_id,
        punch_out_geo=punch_out_geo,
        is_mocked=payload.is_mocked,
    )
    return SessionDto.model_validate(session)


@router.get("/today", response_model=Optional[SessionDto])
async def today_endpoint(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """Get today's attendance session for the current user (Asia/Kolkata work date)."""
    session = get_today_session(db, current_user.id)
    return SessionDto.model_validate(session) if session else None


@router.get("/my", response_model=SessionListResponse)
async def my_endpoint(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """List own attendance sessions in date range. Only current user's records."""
    sessions = list_my_sessions(db, current_user.id, from_date, to_date)
    return SessionListResponse(
        items=[SessionDto.model_validate(s) for s in sessions],
        total=len(sessions),
    )


@router.get("/today-scope", response_model=SessionListResponse)
async def today_scope_endpoint(
    employee_id: Optional[int] = Query(None, description="Filter by specific employee ID"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    Get today's attendance sessions using role-based scoping identical to leaves.
    
    Role-based scoping:
    - ADMIN/MD/VP (role_rank <= 3): can view all employees
    - MANAGER (role_rank == 4): can view only direct reportees
    - EMPLOYEE: can view only own attendance
    
    Returns today's attendance sessions list + total count.
    """
    from app.services.leave_service import get_role_rank, get_subordinate_ids
    from app.services.attendance_session_service import get_today_session, _get_sessions_for_employees
    from app.utils.datetime_utils import get_work_date
    
    today = get_work_date()
    current_user_rank = get_role_rank(db, current_user)
    
    # Apply role-based scoping
    if current_user_rank <= 3:
        # ADMIN/MD/VP: can view all employees
        if employee_id:
            # Filter by specific employee if requested
            session = get_today_session(db, employee_id)
            sessions = [session] if session else []
        else:
            # Get all sessions for today
            from app.services.attendance_session_service import admin_list_today
            sessions = admin_list_today(db, current_user)
    elif current_user_rank == 4:
        # MANAGER: can view only direct reportees
        subordinate_ids = get_subordinate_ids(db, current_user.id)
        
        if employee_id:
            # Validate that requested employee is within manager's scope
            if employee_id not in subordinate_ids and employee_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only view attendance of your direct reportees."
                )
            session = get_today_session(db, employee_id)
            sessions = [session] if session else []
        else:
            # Get sessions for all direct reportees today
            if not subordinate_ids:
                sessions = []
            else:
                # Get today's sessions for multiple employees
                sessions = _get_sessions_for_employees(db, subordinate_ids, today, today)
    else:
        # EMPLOYEE: can view only own attendance
        if employee_id and employee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own attendance."
            )
        session = get_today_session(db, current_user.id)
        sessions = [session] if session else []
    
    return SessionListResponse(
        items=[SessionDto.model_validate(s) for s in sessions if s is not None],
        total=len([s for s in sessions if s is not None]),
    )


# --- Legacy (AttendanceLog) ---

@router.get("/list", response_model=AttendanceListResponse)
async def list_attendance_endpoint(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    List legacy attendance logs with role-based scoping.
    For session-based list use GET /my.
    """
    attendance_logs = list_attendance(
        db=db,
        current_user=current_user,
        from_date=from_date,
        to_date=to_date,
    )
    return AttendanceListResponse(
        items=[AttendanceListItemOut.model_validate(log) for log in attendance_logs],
        total=len(attendance_logs),
    )


@router.get("/list-sessions", response_model=SessionListResponse)
async def list_sessions_endpoint(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    employee_id: Optional[int] = Query(None, description="Filter by specific employee ID"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """
    List attendance sessions with role-based scoping identical to leaves.
    
    Role-based scoping:
    - ADMIN/MD/VP (role_rank <= 3): can view all employees
    - MANAGER (role_rank == 4): can view only direct reportees
    - EMPLOYEE: can view only own attendance
    
    Returns attendance sessions list + total count.
    """
    from app.services.leave_service import get_role_rank, get_subordinate_ids
    from app.services.attendance_session_service import list_my_sessions
    
    # Validate date range
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be less than or equal to to_date"
        )
    
    current_user_rank = get_role_rank(db, current_user)
    
    # Apply role-based scoping
    if current_user_rank <= 3:
        # ADMIN/MD/VP: can view all employees
        if employee_id:
            # Filter by specific employee if requested
            sessions = list_my_sessions(db, employee_id, from_date, to_date)
        else:
            # Get all sessions for all employees in date range
            # This requires a new service function or we can use admin_list with proper scoping
            from app.services.attendance_session_service import admin_list
            sessions = admin_list(db, current_user, from_date, to_date, employee_id=employee_id)
    elif current_user_rank == 4:
        # MANAGER: can view only direct reportees
        subordinate_ids = get_subordinate_ids(db, current_user.id)
        
        if employee_id:
            # Validate that requested employee is within manager's scope
            if employee_id not in subordinate_ids and employee_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only view attendance of your direct reportees."
                )
            sessions = list_my_sessions(db, employee_id, from_date, to_date)
        else:
            # Get sessions for all direct reportees
            if not subordinate_ids:
                sessions = []
            else:
                # Get sessions for multiple employees
                sessions = _get_sessions_for_employees(db, subordinate_ids, from_date, to_date)
    else:
        # EMPLOYEE: can view only own attendance
        if employee_id and employee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You can only view your own attendance."
            )
        sessions = list_my_sessions(db, current_user.id, from_date, to_date)
    
    return SessionListResponse(
        items=[SessionDto.model_validate(s) for s in sessions],
        total=len(sessions),
    )
