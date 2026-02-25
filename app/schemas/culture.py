from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import date

class BirthdayEmployee(BaseModel):
    employee_id: int
    name: str
    emp_code: str
    department: Optional[str] = None
    profile_photo_url: Optional[str] = None
    dob: Optional[date] = None
    birthday_date: Optional[date] = None
    wish_status: Optional[str] = None

class BirthdayListResponse(BaseModel):
    items: List[BirthdayEmployee]
    total: int

class GreetingRequest(BaseModel):
    message: Optional[str] = Field(default=None)

class ThemeResponse(BaseModel):
    mode: str
    bannerText: Optional[str] = None
    accent: Optional[str] = None
    showConfetti: Optional[bool] = None

class WishRequest(BaseModel):
    message: Optional[str] = None
    wish_message: Optional[str] = None
