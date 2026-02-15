"""
Timezone-aware datetime helpers for production.
- Store and compute in UTC in DB.
- All API responses expose datetimes in IST (Asia/Kolkata, +05:30); never Z.
"""
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

UTC = timezone.utc
IST = ZoneInfo("Asia/Kolkata")


def now_utc() -> datetime:
    """Current time in UTC (timezone-aware). Use for punch_in_at, punch_out_at, created_at, etc."""
    return datetime.now(UTC)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """If dt is naive, treat as UTC and return timezone-aware UTC. If already aware, convert to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


def to_ist(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert to Asia/Kolkata. Naive datetimes are treated as UTC before converting."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(IST)


def iso_ist(dt: Optional[datetime]) -> Optional[str]:
    """Serialize as ISO-8601 in IST with +05:30 offset. Use for all API response datetime fields. Never returns Z."""
    if dt is None:
        return None
    ist_dt = to_ist(dt)
    return ist_dt.isoformat()


def iso_z(dt: Optional[datetime]) -> Optional[str]:
    """Serialize as ISO-8601 with Z (UTC). Prefer iso_ist for API responses."""
    return iso_8601_utc(dt)


def iso_8601_utc(dt: Optional[datetime]) -> Optional[str]:
    """ISO-8601 with Z for UTC. Internal use; API responses use iso_ist."""
    if dt is None:
        return None
    utc = ensure_utc(dt)
    s = utc.isoformat()
    if s.endswith("+00:00"):
        s = s[:-6] + "Z"
    return s
