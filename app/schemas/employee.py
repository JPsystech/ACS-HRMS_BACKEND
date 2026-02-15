"""
Employee schemas
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, field_serializer, ConfigDict
from app.models.employee import Role, WorkMode


class EmployeeCreate(BaseModel):
    """Schema for creating an employee"""
    emp_code: str = Field(..., description="Employee code (unique)")
    name: str = Field(..., description="Employee name")
    mobile_number: Optional[str] = Field(None, description="Employee mobile number")
    role: Role = Field(..., description="Employee role")
    department_id: int = Field(..., description="Department ID (required)")
    join_date: date = Field(..., description="Employee join date")
    password: Optional[str] = Field(None, min_length=6, max_length=72, description="Employee password (optional)")
    active: bool = Field(default=True, description="Employee active status")
    reporting_manager_id: Optional[int] = Field(None, description="Reporting manager ID")
    work_mode: Optional[WorkMode] = Field(default=WorkMode.OFFICE, description="Employee work mode")
    
    @field_validator('password', mode='before')
    @classmethod
    def validate_password(cls, v):
        """Normalize and validate password"""
        if v is None:
            return None
        
        # Trim whitespace
        v = v.strip()
        
        # Return None if empty after trimming
        if not v:
            return None
            
        # Check minimum length
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
            
        # Check UTF-8 byte length
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 72:
            raise ValueError("Password cannot be longer than 72 bytes when encoded as UTF-8")
            
        return v


class EmployeeUpdate(BaseModel):
    """Schema for updating an employee"""
    name: Optional[str] = Field(None, description="Employee name")
    mobile_number: Optional[str] = Field(None, description="Employee mobile number")
    role: Optional[Role] = Field(None, description="Employee role")
    department_id: Optional[int] = Field(None, description="Department ID")
    join_date: Optional[date] = Field(None, description="Employee join date")
    active: Optional[bool] = Field(None, description="Employee active status")
    reporting_manager_id: Optional[int] = Field(None, description="Reporting manager ID")
    work_mode: Optional[WorkMode] = Field(None, description="Employee work mode")


class DepartmentRef(BaseModel):
    """Minimal department for profile"""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class ReportingManagerRef(BaseModel):
    """Minimal reporting manager for profile"""
    id: int
    emp_code: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class EmployeeOut(BaseModel):
    """Schema for employee output. Datetimes in IST (+05:30)."""
    id: int
    emp_code: str
    name: str
    mobile_number: Optional[str] = None
    role: Role
    role_rank: Optional[int] = Field(None, description="Role rank (higher authority = lower number)")
    department_id: int
    reporting_manager_id: Optional[int]
    reporting_manager: Optional[ReportingManagerRef] = None
    join_date: date
    active: bool
    work_mode: WorkMode
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at", when_used="always")
    @classmethod
    def _ser_datetime(cls, dt):
        from app.utils.datetime_utils import iso_ist
        return iso_ist(dt) if dt is not None else None


class EmployeeMeOut(BaseModel):
    """Schema for GET /employees/me - current user profile with nested refs."""
    id: int
    emp_code: str
    name: str
    mobile_number: Optional[str] = None
    department: Optional[DepartmentRef] = None
    reporting_manager: Optional[ReportingManagerRef] = None
    role: Role
    role_rank: Optional[int] = Field(None, description="Role rank (higher authority = lower number)")
    join_date: date
    is_active: bool
    work_mode: WorkMode

    model_config = ConfigDict(from_attributes=True)


class PasswordReset(BaseModel):
    """Schema for password reset"""
    new_password: str = Field(..., min_length=6, description="New password")


class ManagerOptions(BaseModel):
    """Schema for manager options response"""
    id: int
    emp_code: str
    name: str
    role_id: int
    role_name: str
    role_rank: int
    department_id: int
    department_name: str
    is_fallback: Optional[bool] = Field(default=False, description="True if this is a fallback option (not same department for EMPLOYEE)")

    model_config = ConfigDict(from_attributes=True)
