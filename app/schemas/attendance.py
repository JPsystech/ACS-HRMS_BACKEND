"""
Attendance schemas (legacy AttendanceLog + session-based AttendanceSession).
"""
import json
from datetime import date, datetime
from typing import Optional, List, Any, Dict, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator, field_serializer
from decimal import Decimal

from app.utils.datetime_utils import iso_ist, ensure_utc


class PunchInRequest(BaseModel):
    """Schema for punch-in request"""
    lat: float = Field(..., ge=-90, le=90, description="GPS latitude")
    lng: float = Field(..., ge=-180, le=180, description="GPS longitude")
    source: str = Field(default="mobile", description="Source of punch-in (e.g., 'mobile', 'web')")


class PunchOutRequest(BaseModel):
    """Schema for punch-out request"""
    lat: float = Field(..., ge=-90, le=90, description="GPS latitude")
    lng: float = Field(..., ge=-180, le=180, description="GPS longitude")
    source: str = Field(default="mobile", description="Source of punch-out (e.g., 'mobile', 'web')")


def _serialize_dt_ist(dt: Optional[datetime]) -> Optional[str]:
    """Serialize datetime as IST (+05:30) for API responses."""
    return iso_ist(dt)


class AttendanceOut(BaseModel):
    """Schema for attendance output. All datetimes in IST (+05:30)."""
    id: int
    employee_id: int
    punch_date: date
    in_time: datetime
    in_lat: Decimal
    in_lng: Decimal
    out_time: Optional[datetime]
    out_lat: Optional[Decimal]
    out_lng: Optional[Decimal]
    source: str

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("in_time", "out_time", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_dt_ist(dt)


class AttendanceListItemOut(BaseModel):
    """Schema for attendance list item output. All datetimes in IST (+05:30)."""
    id: int
    employee_id: int
    punch_date: date
    in_time: datetime
    in_lat: Decimal
    in_lng: Decimal
    out_time: Optional[datetime]
    out_lat: Optional[Decimal]
    out_lng: Optional[Decimal]
    source: str

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("in_time", "out_time", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_dt_ist(dt)


class AttendanceListResponse(BaseModel):
    """Schema for attendance list response"""
    items: List[AttendanceListItemOut]
    total: int


# --- Session-based (AttendanceSession / AttendanceEvent) ---


class GeoSchema(BaseModel):
    """Geo payload for punch-in/out: lat, lng required; optional accuracy, provider, captured_at, address."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lng: float = Field(..., ge=-180, le=180, description="Longitude")
    accuracy: Optional[float] = Field(None, gt=0)
    provider: Optional[str] = None
    captured_at: Optional[datetime] = None
    address: Optional[str] = None

    model_config = ConfigDict(extra="allow")  # allow extra keys from client (e.g. is_mocked, source)


# Optional GPS fields for live capture; when provided, service builds punch_*_geo JSON.
def _validate_lat(v: Optional[float]) -> Optional[float]:
    if v is None:
        return v
    if not (-90 <= v <= 90):
        raise ValueError("lat must be between -90 and 90")
    return v


def _validate_lng(v: Optional[float]) -> Optional[float]:
    if v is None:
        return v
    if not (-180 <= v <= 180):
        raise ValueError("lng must be between -180 and 180")
    return v


def _validate_accuracy(v: Optional[float]) -> Optional[float]:
    if v is None:
        return v
    if v <= 0:
        raise ValueError("accuracy must be positive")
    return v


class SessionPunchInRequest(BaseModel):
    """Request for session punch-in. Accepts geo (GeoSchema/dict), device_id/deviceId; or punch_in_geo/lat+lng."""
    source: str = Field(default="WEB", description="MOBILE/WEB/ADMIN")
    punch_in_ip: Optional[str] = None
    punch_in_device_id: Optional[str] = None
    punch_in_geo: Optional[Dict[str, Any]] = None
    geo: Optional[Union[GeoSchema, Dict[str, Any]]] = Field(None, description="Geo: lat, lng, accuracy, provider, captured_at. Stored as punch_in_geo.")
    device_id: Optional[str] = Field(None, alias="deviceId", description="Device ID")
    lat: Optional[float] = Field(None, description="GPS latitude [-90, 90]")
    lng: Optional[float] = Field(None, description="GPS longitude [-180, 180]")
    accuracy: Optional[float] = Field(None, description="Accuracy in meters; must be positive")
    provider: Optional[str] = Field(None, description="Location provider e.g. gps, network")
    captured_at: Optional[datetime] = None
    is_mocked: Optional[bool] = Field(None, description="True if location is mock; see REJECT_MOCK_LOCATION_PUNCH config")
    address: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("lat")
    @classmethod
    def check_lat(cls, v: Optional[float]) -> Optional[float]:
        return _validate_lat(v)

    @field_validator("lng")
    @classmethod
    def check_lng(cls, v: Optional[float]) -> Optional[float]:
        return _validate_lng(v)

    @field_validator("accuracy")
    @classmethod
    def check_accuracy(cls, v: Optional[float]) -> Optional[float]:
        return _validate_accuracy(v)


class SessionPunchOutRequest(BaseModel):
    """Request for session punch-out. Accepts geo (GeoSchema/dict), device_id/deviceId; or punch_out_geo/lat+lng."""
    source: str = Field(default="WEB", description="MOBILE/WEB/ADMIN")
    punch_out_ip: Optional[str] = None
    punch_out_device_id: Optional[str] = None
    punch_out_geo: Optional[Dict[str, Any]] = None
    geo: Optional[Union[GeoSchema, Dict[str, Any]]] = Field(None, description="Geo: lat, lng, etc. Stored as punch_out_geo.")
    device_id: Optional[str] = Field(None, alias="deviceId", description="Device ID")
    lat: Optional[float] = Field(None, description="GPS latitude [-90, 90]")
    lng: Optional[float] = Field(None, description="GPS longitude [-180, 180]")
    accuracy: Optional[float] = Field(None, description="Accuracy in meters; must be positive")
    provider: Optional[str] = None
    captured_at: Optional[datetime] = None
    is_mocked: Optional[bool] = None
    address: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("lat")
    @classmethod
    def check_lat(cls, v: Optional[float]) -> Optional[float]:
        return _validate_lat(v)

    @field_validator("lng")
    @classmethod
    def check_lng(cls, v: Optional[float]) -> Optional[float]:
        return _validate_lng(v)

    @field_validator("accuracy")
    @classmethod
    def check_accuracy(cls, v: Optional[float]) -> Optional[float]:
        return _validate_accuracy(v)


def _ensure_geo_dict(v: Any) -> Optional[Dict[str, Any]]:
    """Ensure geo is a dict for JSON response (ORM may return str for SQLite JSON column)."""
    if v is None:
        return None
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (TypeError, ValueError):
            return None
    return None


def _geo_captured_at_to_ist(geo: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return a copy of geo with captured_at converted to IST ISO string (+05:30)."""
    if not geo or "captured_at" not in geo:
        return geo
    from datetime import datetime
    out = dict(geo)
    cap = out.get("captured_at")
    if cap is None:
        return out
    if isinstance(cap, datetime):
        out["captured_at"] = iso_ist(ensure_utc(cap) if cap.tzinfo is None else cap)
    elif isinstance(cap, str):
        try:
            dt = datetime.fromisoformat(cap.replace("Z", "+00:00"))
            out["captured_at"] = iso_ist(dt)
        except (ValueError, TypeError):
            pass
    return out


class SessionDto(BaseModel):
    """Attendance session output; all datetimes in IST (+05:30). Includes punch_in_geo and punch_out_geo."""
    id: int
    employee_id: int
    work_date: date
    punch_in_at: datetime
    punch_out_at: Optional[datetime] = None
    status: str
    punch_in_source: str
    punch_out_source: Optional[str] = None
    punch_in_ip: Optional[str] = None
    punch_out_ip: Optional[str] = None
    punch_in_device_id: Optional[str] = None
    punch_out_device_id: Optional[str] = None
    punch_in_geo: Optional[Dict[str, Any]] = None
    punch_out_geo: Optional[Dict[str, Any]] = None
    remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("punch_in_geo", "punch_out_geo", mode="before")
    @classmethod
    def geo_to_dict(cls, v: Any) -> Optional[Dict[str, Any]]:
        return _ensure_geo_dict(v)

    @field_serializer("punch_in_at", "punch_out_at", "created_at", "updated_at", when_used="always")
    def _serialize_datetime_ist(self, dt: Optional[datetime]) -> Optional[str]:
        """Emit ISO-8601 in IST (+05:30) for API responses. Never Z."""
        return _serialize_dt_ist(dt)

    @field_serializer("punch_in_geo", "punch_out_geo", when_used="always")
    def _serialize_geo_captured_at_ist(self, geo: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Ensure geo.captured_at is returned in IST (+05:30)."""
        return _geo_captured_at_to_ist(geo)


class EventDto(BaseModel):
    """Attendance event output (immutable log entry). Datetimes in IST (+05:30)."""
    id: int
    session_id: int
    employee_id: int
    event_type: str
    event_at: datetime
    meta_json: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("event_at", "created_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt: Optional[datetime]) -> Optional[str]:
        return _serialize_dt_ist(dt)


class SessionListResponse(BaseModel):
    """List of sessions with total"""
    items: List[SessionDto]
    total: int


class AdminSessionUpdateRequest(BaseModel):
    """Admin PATCH body: edit punch_in_at, punch_out_at, status, remarks"""
    punch_in_at: Optional[datetime] = None
    punch_out_at: Optional[datetime] = None
    status: Optional[str] = None  # OPEN/CLOSED/AUTO_CLOSED
    remarks: Optional[str] = None


class AdminSessionDto(SessionDto):
    """Session with employee and department names for admin list."""
    employee_name: Optional[str] = None
    department_name: Optional[str] = None
    worked_minutes: Optional[int] = None  # computed: (punch_out_at - punch_in_at) or None


class AdminSessionListResponse(BaseModel):
    """Admin list response with sessions that include employee/department names."""
    items: List[AdminSessionDto]
    total: int
