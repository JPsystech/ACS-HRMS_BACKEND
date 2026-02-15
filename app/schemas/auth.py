"""
Authentication schemas
"""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Login request schema"""
    emp_code: str = Field(..., description="Employee code")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"
