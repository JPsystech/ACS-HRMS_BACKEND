"""
Authentication schemas
"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    """Login request schema"""
    emp_code: str = Field(..., description="Employee code")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    must_change_password: bool = False
    access_token_expires_at: Optional[datetime] = None
    refresh_token_expires_at: Optional[datetime] = None


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Employee password change request"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")


class AdminResetPasswordRequest(BaseModel):
    """Admin reset password request"""
    new_password: Optional[str] = Field(None, description="New password (optional if generate_random=true)")
    generate_random: bool = Field(default=False, description="Generate a random temporary password")
