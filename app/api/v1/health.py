"""
Health check endpoint
"""
from fastapi import APIRouter
from app.core.constants import SYSTEM_CREDIT

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    
    Returns service status and attribution.
    """
    return {
        "status": "ok",
        "service": "acs-hrms-backend",
        "credit": SYSTEM_CREDIT
    }
