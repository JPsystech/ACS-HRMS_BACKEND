"""
Admin WFH balances endpoints.

WFH usage is per employee/year and computed from WFHRequest rows:
- Entitled: wfh_max_days from policy_settings for the year (default 12)
- Used: count of APPROVED WFH requests in that year
- Remaining: entitled - used
Accrual isn't time-based for WFH, so we treat it equal to entitlement.
"""

from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin_attendance
from app.models.employee import Employee
from app.models.wfh import WFHRequest, WFHStatus
from app.models.employee import Employee as Emp
from app.models.department import Department
from app.schemas.wfh import (
    AdminWfhBalanceItem,
    AdminWfhBalancesResponse,
    AdminWfhTransactionOut,
)
from app.services.policy_validator import get_or_create_policy_settings

router = APIRouter()


@router.get("/balances", response_model=AdminWfhBalancesResponse)
async def admin_wfh_balances(
    year: int = Query(..., description="Calendar year (e.g. 2026)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_attendance),
):
    """
    List WFH usage by employee for a given year.

    Entitled is taken from policy_settings.wfh_max_days (default 12).
    Used is count of APPROVED WFH requests in that year.
    Remaining is entitled - used.
    """
    # Get WFH policy for the year
    settings = get_or_create_policy_settings(db, year)
    entitled_days: int = getattr(settings, "wfh_max_days", 12)

    start = date(year, 1, 1)
    end = date(year, 12, 31)

    # Fetch all WFH requests for the year
    requests = (
        db.query(WFHRequest)
        .filter(WFHRequest.request_date >= start, WFHRequest.request_date <= end)
        .all()
    )

    if not requests:
        return AdminWfhBalancesResponse(year=year, items=[], total=0)

    # Preload employees and departments
    emp_ids = list({r.employee_id for r in requests})
    employees: dict[int, Emp] = {}
    depts: dict[int, str] = {}

    if emp_ids:
        for e in db.query(Emp).filter(Emp.id.in_(emp_ids)).all():
            employees[e.id] = e
        dept_ids = list({e.department_id for e in employees.values() if e.department_id})
        if dept_ids:
            for d in db.query(Department).filter(Department.id.in_(dept_ids)).all():
                depts[d.id] = d.name

    # Aggregate usage by employee
    used_counts: dict[int, int] = {}
    for r in requests:
        if r.status == WFHStatus.APPROVED:
            used_counts[r.employee_id] = used_counts.get(r.employee_id, 0) + 1

    items: List[AdminWfhBalanceItem] = []
    for emp_id in emp_ids:
        emp = employees.get(emp_id)
        used = used_counts.get(emp_id, 0)
        remaining = max(entitled_days - used, 0)
        items.append(
            AdminWfhBalanceItem(
                employee_id=emp_id,
                employee_name=emp.name if emp else None,
                department_name=depts.get(emp.department_id) if emp else None,
                emp_code=emp.emp_code if emp else None,
                entitled=entitled_days,
                accrued=entitled_days,
                used=used,
                remaining=remaining,
            )
        )

    # Sort by remaining desc then name for a stable output
    items.sort(key=lambda i: (-i.remaining, (i.employee_name or "").lower()))

    return AdminWfhBalancesResponse(year=year, items=items, total=len(items))


@router.get("/balances/transactions", response_model=List[AdminWfhTransactionOut])
async def admin_wfh_transactions(
    employee_id: int = Query(..., description="Employee ID"),
    year: Optional[int] = Query(None, description="Filter by year (e.g. 2026)"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_attendance),
):
    """
    List WFH 'transactions' for an employee.

    This is a simple view over WFHRequest rows:
    - date: request_date
    - day_value: request's day_value
    - action: current status (PENDING/APPROVED/REJECTED/CANCELLED)
    - remarks: request reason
    - action_by_employee_id: approved_by
    - action_at: approved_at (or applied_at when still pending)
    """
    query = db.query(WFHRequest).filter(WFHRequest.employee_id == employee_id)

    if year is not None:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        query = query.filter(
            WFHRequest.request_date >= start,
            WFHRequest.request_date <= end,
        )

    requests = (
        query.order_by(WFHRequest.request_date.asc())
        .limit(limit)
        .all()
    )

    result: List[AdminWfhTransactionOut] = []
    for r in requests:
        action_at = r.approved_at or r.applied_at
        result.append(
            AdminWfhTransactionOut(
                id=r.id,
                employee_id=r.employee_id,
                date=r.request_date,
                day_value=r.day_value,
                action=r.status.value if hasattr(r.status, "value") else str(r.status),
                remarks=r.reason,
                action_by_employee_id=r.approved_by,
                action_at=action_at,
            )
        )

    return result

