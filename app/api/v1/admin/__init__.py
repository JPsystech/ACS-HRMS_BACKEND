"""Admin API (HR/ADMIN; MANAGER only with team mapping)."""
from fastapi import APIRouter
from app.api.v1.admin import attendance as admin_attendance
from app.api.v1.admin import leaves as admin_leaves
from app.api.v1.admin import wfh as admin_wfh

admin_router = APIRouter(prefix="/admin", tags=["admin"])
admin_router.include_router(admin_attendance.router, prefix="/attendance", tags=["admin-attendance"])
admin_router.include_router(admin_leaves.router, prefix="/leaves", tags=["admin-leaves"])
admin_router.include_router(admin_wfh.router, prefix="/wfh", tags=["admin-wfh"])
