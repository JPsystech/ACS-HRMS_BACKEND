"""
Role schemas

Used for managing dynamic role master data (including WFH enablement).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class RoleBase(BaseModel):
    name: str = Field(..., description="Role name (e.g. EMPLOYEE, MANAGER, HR)")
    role_rank: int = Field(
        ...,
        ge=1,
        description="Smaller rank = higher authority (e.g. ADMIN=1)",
    )
    wfh_enabled: bool = Field(
        default=False,
        description="Whether WFH is allowed for this role",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the role is active and selectable",
    )


class RoleCreate(RoleBase):
    """Schema for creating a role"""


class RoleUpdate(BaseModel):
    """Schema for updating a role"""

    name: Optional[str] = Field(
        default=None,
        description="Updated role name",
    )
    wfh_enabled: Optional[bool] = Field(
        default=None,
        description="Updated WFH enablement flag",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="Updated active flag",
    )
    role_rank: Optional[int] = Field(
        default=None,
        ge=1,
        description="Updated rank (smaller = higher authority)",
    )


class RoleOut(BaseModel):
    """Role output schema"""

    id: int
    name: str
    role_rank: int
    wfh_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

