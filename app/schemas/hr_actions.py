"""
HR Policy Actions schemas
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_serializer, ConfigDict
from app.models.hr_actions import HRPolicyActionType


class HRPolicyActionCreate(BaseModel):
    """Schema for creating HR policy action"""
    employee_id: int = Field(..., description="Employee ID")
    action_type: HRPolicyActionType = Field(..., description="Action type")
    reference_entity_type: Optional[str] = Field(None, description="Reference entity type (e.g., 'leave_requests')")
    reference_entity_id: Optional[int] = Field(None, description="Reference entity ID")
    meta_json: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    remarks: Optional[str] = Field(None, description="Optional remarks")


class CancelLeaveRequest(BaseModel):
    """Schema for cancelling approved leave"""
    recredit: bool = Field(False, description="Whether to re-credit paid days back to balance")
    remarks: Optional[str] = Field(None, description="Optional remarks")


class HRPolicyActionOut(BaseModel):
    """Schema for HR policy action output. Datetimes in IST (+05:30)."""
    id: int
    employee_id: int
    action_type: HRPolicyActionType
    reference_entity_type: Optional[str]
    reference_entity_id: Optional[int]
    meta_json: Optional[Dict[str, Any]]
    action_by: int
    action_at: datetime
    remarks: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("action_at", "created_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None


class HRPolicyActionListResponse(BaseModel):
    """Schema for HR policy actions list response"""
    items: list[HRPolicyActionOut]
    total: int
