from datetime import date as date_type, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class AttendanceCorrectionCreate(BaseModel):
    request_type: str = Field(..., description="FORGOT_PUNCH_IN | FORGOT_PUNCH_OUT | CORRECTION")
    date: date_type = Field(..., description="Work date")
    requested_punch_in: Optional[datetime] = Field(None)
    requested_punch_out: Optional[datetime] = Field(None)
    reason: str = Field(..., description="Reason for correction")
    remarks: Optional[str] = Field(None)

class AttendanceCorrectionOut(BaseModel):
    id: int
    employee_id: int
    request_type: str
    date: date_type
    requested_punch_in: Optional[datetime] = None
    requested_punch_out: Optional[datetime] = None
    reason: str
    remarks: Optional[str] = None
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    admin_remarks: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AttendanceCorrectionReview(BaseModel):
    admin_remarks: Optional[str] = Field(None)
