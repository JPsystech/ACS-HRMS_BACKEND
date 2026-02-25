"""
Audit log model
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    action = Column(String, nullable=False)  # e.g., "CREATE", "UPDATE", "DELETE", "ASSIGN"
    entity_type = Column(String, nullable=False)  # e.g., "department", "employee", "manager_department"
    entity_id = Column(Integer, nullable=True)  # ID of the affected entity
    meta_json = Column(JSON, nullable=True)  # Additional metadata as JSON
    # Note: server_default handled by migration (CURRENT_TIMESTAMP for SQLite, now() for PostgreSQL)
    created_at = Column(DateTime(timezone=True), nullable=False)
