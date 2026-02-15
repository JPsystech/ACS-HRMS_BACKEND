"""
Version and metadata endpoint
"""
from fastapi import APIRouter
from app.core.config import settings
from app.core.constants import SYSTEM_CREDIT

router = APIRouter()


@router.get("/version")
async def get_version():
    """
    Get application version and metadata
    
    Returns:
        Version information including service name, version, environment, and credit
    """
    return {
        "service": "acs-hrms-backend",
        "version": settings.VERSION or "1.0.0",
        "env": settings.APP_ENV,
        "credit": SYSTEM_CREDIT
    }
