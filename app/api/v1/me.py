from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date, datetime
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.services.storage_service import StorageService

router = APIRouter()


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    dob: Optional[date] = None


@router.put("/profile")
async def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    if payload.name is not None:
        e.name = payload.name
    if payload.dob is not None:
        e.dob = payload.dob
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"ok": True}


@router.post("/profile-photo")
async def upload_profile_photo(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    e = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    data = await file.read()
    storage = StorageService()
    path = f"profile-photos/{e.id}/avatar.jpg"
    
    # Use request.base_url to ensure correct URL generation for all environments
    base_url = str(request.base_url).rstrip("/")
    url = storage.upload_bytes("profile-photos", path, data, file.content_type or "image/jpeg", base_url=base_url)
    e.profile_photo_url = url
    e.profile_photo_updated_at = datetime.utcnow()
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"profile_photo_url": url}
