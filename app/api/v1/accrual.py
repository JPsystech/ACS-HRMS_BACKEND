"""
Accrual management endpoints (HR-only)
"""
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, require_roles, get_current_user
from app.core.constants import SYSTEM_CREDIT
from app.models.employee import Role, Employee
from app.services.accrual_service import run_monthly_accrual, get_accrual_status

router = APIRouter()


@router.post("/run")
async def run_accrual_endpoint(
    month: str = Query(None, description="Month in YYYY-MM format (e.g., 2026-02). Omit to run full year."),
    year: int = Query(None, description="Year only (e.g., 2026). Use with month omitted to run all 12 months (idempotent)."),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """
    Run accrual (HR-only). Idempotent: running twice does not double-credit.
    
    Option A: POST /api/v1/accrual/run?month=2026-02 — run February 2026 only.
    Option B: POST /api/v1/accrual/run?year=2026 — run all months 1..12 for 2026 (full year allocation, pro-rata for joiners).
    
    Policy: PL=5, CL=6, SL=7 per year. Monthly accrual +1 CL, +1 PL; SL annual grant pro-rated. PL usable after 6 months.
    """
    if month:
        try:
            parts = month.split("-")
            if len(parts) != 2:
                raise ValueError("Invalid format")
            year_val = int(parts[0])
            month_num = int(parts[1])
            if month_num < 1 or month_num > 12 or len(parts[0]) != 4:
                raise ValueError("Invalid")
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid month: {month}. Use YYYY-MM (e.g., 2026-02)"
            )
        result = run_monthly_accrual(db=db, year=year_val, month=month_num, actor_id=current_user.id)
    elif year is not None:
        results = []
        for m in range(1, 13):
            r = run_monthly_accrual(db=db, year=year, month=m, actor_id=current_user.id)
            results.append(r)
        result = {
            "year": year,
            "months_run": 12,
            "total_employees_processed": results[-1].get("total_employees_processed", 0) if results else 0,
            "credited_count": results[-1].get("credited_count", 0) if results else 0,
            "details": results,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either month=YYYY-MM or year=YYYY"
        )
    result["credit"] = SYSTEM_CREDIT
    return result


@router.get("/status")
async def get_accrual_status_endpoint(
    year: int = Query(..., description="Year (e.g., 2026)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.ADMIN))
):
    """
    Get accrual status for all employees for a given year (HR-only)
    
    Shows for each employee:
    - Current balances (CL, SL, PL)
    - RH used count
    - Last accrual month credited
    
    Useful for verification and debugging.
    """
    status_list = get_accrual_status(db=db, year=year)
    
    return {
        "year": year,
        "employees": status_list,
        "total": len(status_list),
        "credit": SYSTEM_CREDIT
    }
