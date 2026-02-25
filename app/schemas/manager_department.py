"""
Manager-Department mapping schemas
"""
from pydantic import BaseModel, Field
from typing import List


class AssignDepartmentsRequest(BaseModel):
    """Schema for assigning departments to a manager"""
    department_ids: List[int] = Field(..., description="List of department IDs to assign")


class ManagerDepartmentOut(BaseModel):
    """Schema for manager-department mapping output"""
    manager_id: int
    department_id: int

    class Config:
        from_attributes = True
