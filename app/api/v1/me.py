from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import date, datetime
import os
import re
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.services.r2_storage import get_r2_storage_service

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


@router.post("/photo")
@router.post("/profile-photo")
async def upload_profile_photo(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: Employee = Depends(get_current_user)):
    """Upload profile photo to Cloudflare R2"""
    import logging
    logger = logging.getLogger(__name__)
    
    e = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: jpg, jpeg, png, webp"
        )
    
    # Validate file size (5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    file_data = await file.read()
    if len(file_data) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size: 5MB"
        )
    
    # Generate safe filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_filename = re.sub(r'[^a-zA-Z0-9.-]', '', file.filename or "photo")
    if not safe_filename:
        safe_filename = "photo"
    
    # Generate object key
    object_key = f"employees/{e.id}/profile/{timestamp}_{safe_filename}"
    
    # Upload to R2
    try:
        logger.info(f"Uploading photo: bucket=acs-hrms-storage, key={object_key}, type={file.content_type}, size={len(file_data)}")
        
        success = get_r2_storage_service().upload_file(
            file_data=file_data,
            object_key=object_key,
            content_type=file.content_type
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload photo"
            )
        
        # Update database
        e.photo_key = object_key
        e.profile_photo_updated_at = datetime.utcnow()
        db.add(e)
        db.commit()
        db.refresh(e)
        
        logger.info(f"Photo uploaded successfully: {object_key}")
        
        # Generate pre-signed URL for immediate display
        r2_service = get_r2_storage_service()
        photo_url = r2_service.get_presigned_url(object_key)
        
        return {
            "photo_key": object_key,
            "profile_photo_url": photo_url,
            "photo_fetch_url": "/api/v1/me/photo",
            "updated_at": e.profile_photo_updated_at.isoformat() if e.profile_photo_updated_at else None
        }
        
    except ValueError as ve:
        # R2 not configured
        logger.error(f"R2 configuration error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo upload service is not configured. Please contact administrator."
        )
    except Exception as ex:
        logger.error(f"Photo upload error: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed"
        )


@router.get("/photo")
@router.get("/profile-photo")
async def get_profile_photo(
    v: Optional[str] = None,  # Cache-busting version parameter
    db: Session = Depends(get_db), 
    current_user: Employee = Depends(get_current_user)
):
    """Retrieve profile photo from Cloudflare R2"""
    import logging
    logger = logging.getLogger(__name__)
    
    e = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not e or not e.photo_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile photo not found"
        )
    
    try:
        logger.debug(f"Fetching photo: {e.photo_key}")
        
        file_data = get_r2_storage_service().get_file(e.photo_key)
        if file_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Photo not found in storage"
            )
        
        # Determine content type from file extension
        content_type = "image/jpeg"  # Default
        if e.photo_key.lower().endswith('.png'):
            content_type = "image/png"
        elif e.photo_key.lower().endswith('.webp'):
            content_type = "image/webp"
        
        # Return with caching headers
        headers = {
            "Cache-Control": "public, max-age=3600",  # 1 hour cache
            "Content-Type": content_type,
        }
        
        return StreamingResponse(
            iter([file_data]),
            headers=headers,
            media_type=content_type
        )
        
    except ValueError as ve:
        # R2 not configured
        logger.error(f"R2 configuration error: {ve}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo service is not configured. Please contact administrator."
        )
    except HTTPException:
        raise
    except Exception as ex:
        logger.error(f"Photo fetch error: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve photo"
        )
