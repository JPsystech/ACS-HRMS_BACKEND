from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RegisterDeviceRequest(BaseModel):
    fcm_token: str = Field(..., min_length=10)
    platform: str = Field(..., description="android|ios|web|desktop")
    app_version: Optional[str] = None
    is_active: bool = True


class RegisterDeviceResponse(BaseModel):
    status: str
    device_id: int


class TestPushRequest(BaseModel):
    user_id: Optional[int] = None
    token: Optional[str] = None
    title: str = "Test Notification"
    body: str = "Hello from ACS HRMS"
    data: Optional[Dict[str, Any]] = None


class TestPushResponse(BaseModel):
    status: str
    result: Dict[str, Any]

