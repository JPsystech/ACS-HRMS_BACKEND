"""
Main API router
"""
from fastapi import APIRouter

from app.api.v1 import (
    health,
    auth,
    departments,
    employees,
    managers,
    attendance,
    leaves,
    holidays,
    restricted_holidays,
    public_calendars,
    policy,
    accrual,
    compoff,
    reports,
    version,
    events,
    wfh,
    hr_actions,
    roles,
)
from app.api.v1.admin import admin_router

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(version.router, tags=["version"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(departments.router, prefix="/departments", tags=["departments"])
api_router.include_router(employees.router, prefix="/employees", tags=["employees"])
api_router.include_router(managers.router, prefix="/managers", tags=["managers"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(admin_router)
api_router.include_router(leaves.router, prefix="/leaves", tags=["leaves"])
api_router.include_router(holidays.router, prefix="/holidays", tags=["holidays"])
api_router.include_router(restricted_holidays.router, prefix="/restricted_holidays", tags=["restricted-holidays"])
api_router.include_router(public_calendars.router, prefix="/calendars", tags=["calendars"])
api_router.include_router(policy.router, prefix="/policy", tags=["policy"])
api_router.include_router(accrual.router, prefix="/accrual", tags=["accrual"])
api_router.include_router(compoff.router, prefix="/compoff", tags=["comp-off"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(events.router, prefix="/events", tags=["company-events"])
api_router.include_router(wfh.router, prefix="/wfh", tags=["wfh"])
api_router.include_router(hr_actions.router, prefix="/hr/actions", tags=["hr-actions"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
