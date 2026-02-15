"""
JSON serializer utility for converting Python objects to JSON-safe values
"""
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from uuid import UUID
from typing import Any, Dict, List, Union

try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = None  # type: ignore


def sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize Python objects for JSON storage (datetime/date -> isoformat, Enum -> value, etc.).
    Use before saving to any JSON columns (audit_logs.meta_json, attendance_events.meta_json).
    """
    return to_json_safe(obj)


# Alias for callers that expect safe_json
def safe_json(obj: Any) -> Any:
    """Same as sanitize_for_json. Recursively convert to JSON-safe values."""
    return sanitize_for_json(obj)


def to_json_safe(value: Any) -> Any:
    """
    Recursively convert Python objects to JSON-safe values
    
    Args:
        value: Any Python object to convert
        
    Returns:
        JSON-safe equivalent of the input value
    """
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (date, datetime, time)):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, UUID):
        return str(value)
    elif isinstance(value, dict):
        return {k: to_json_safe(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple, set)):
        return [to_json_safe(item) for item in value]
    elif BaseModel is not None and isinstance(value, BaseModel):
        return to_json_safe(value.model_dump() if hasattr(value, "model_dump") else value.dict())
    else:
        # Fallback for any other type
        try:
            return str(value)
        except Exception:
            return None


def serialize_meta(meta: Union[Dict[str, Any], List[Any], None]) -> Union[Dict[str, Any], List[Any], None]:
    """
    Serialize metadata for audit logging (uses sanitize_for_json).
    """
    if meta is None:
        return None
    if isinstance(meta, (dict, list)):
        return sanitize_for_json(meta)
    return sanitize_for_json({"value": meta})