"""
Shared time utilities for the application.
Provides timezone-aware datetime functions for consistent time handling across the app.
"""
from datetime import datetime, timezone
from typing import Optional

UTC = timezone.utc


def now_utc() -> datetime:
    """Current time in UTC (timezone-aware). Use for all time-related operations."""
    return datetime.now(UTC)


def to_ist(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert datetime to Asia/Kolkata timezone. Naive datetimes are treated as UTC before converting."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
    return dt.astimezone(IST)
