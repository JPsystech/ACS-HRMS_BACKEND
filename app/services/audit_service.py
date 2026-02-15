"""
Audit logging service
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.utils.json_serializer import sanitize_for_json
from typing import Optional, Dict, Any


def log_audit(
    db: Session,
    actor_id: int,
    action: str,
    entity_type: str,
    entity_id: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """
    Create an audit log entry
    
    Args:
        db: Database session
        actor_id: ID of the user performing the action
        action: Action type (e.g., "CREATE", "UPDATE", "DELETE", "ASSIGN")
        entity_type: Type of entity (e.g., "department", "employee", "manager_department")
        entity_id: ID of the affected entity (optional)
        meta: Additional metadata as dictionary (optional)
    
    Returns:
        Created AuditLog instance
    """
    # Serialize meta to JSON-safe values
    safe_meta = sanitize_for_json(meta) if meta is not None else None
    
    # Explicitly set created_at to avoid SQLite issues with server_default
    audit_log = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        meta_json=safe_meta,
        created_at=datetime.utcnow()
    )
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    return audit_log
