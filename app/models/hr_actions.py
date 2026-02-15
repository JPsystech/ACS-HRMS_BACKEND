"""
HR policy actions model - records penalties and administrative actions
"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base


class HRPolicyActionType(str, enum.Enum):
    DEDUCT_PL_3 = "DEDUCT_PL_3"  # Unauthorized leave penalty - deduct 3 PL
    MARK_ABSCONDED = "MARK_ABSCONDED"  # Absent >3 days without info
    MEDICAL_CERT_MISSING_PENALTY = "MEDICAL_CERT_MISSING_PENALTY"  # Medical leave >1 day without certificate
    CANCEL_APPROVED_LEAVE = "CANCEL_APPROVED_LEAVE"  # Company cancels approved leave
    OTHER = "OTHER"  # Other HR administrative actions


class HRPolicyAction(Base):
    __tablename__ = "hr_policy_actions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    action_type = Column(SQLEnum(HRPolicyActionType), nullable=False, index=True)
    reference_entity_type = Column(String(50), nullable=True)  # e.g., "leave_requests", "wfh_requests"
    reference_entity_id = Column(Integer, nullable=True)  # ID of referenced entity
    meta_json = Column(JSON, nullable=True)  # Store details like dates, remarks, counts, recredit flags
    action_by = Column(Integer, ForeignKey("employees.id"), nullable=False)  # HR who performed action
    action_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id], backref="hr_policy_actions")
    actor = relationship("Employee", foreign_keys=[action_by])
