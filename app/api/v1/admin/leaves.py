"""
Admin leave balances: list balances by year and optional employee_id/department.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import inspect

from app.core.deps import get_db, require_admin_attendance
from app.models.employee import Employee
from app.models.leave import LeaveBalance, WALLET_LEAVE_TYPES
from app.models.department import Department
from app.schemas.leave import AdminBalancesResponse, AdminBalanceItemOut, LeaveTransactionOut
from app.models.leave import LeaveTransaction
from app.services import leave_wallet_service as wallet

router = APIRouter()

MIGRATION_REQUIRED_MSG = (
    "Leave wallet migration not applied. Stop the backend server, run 'alembic upgrade head' from the hrms-backend folder, then restart the server."
)


def _leave_balances_has_new_schema(db: Session) -> bool:
    """Return True if leave_balances table has the new wallet schema (leave_type column)."""
    try:
        insp = inspect(db.get_bind())
        if "leave_balances" not in insp.get_table_names():
            return False
        cols = [c["name"] for c in insp.get_columns("leave_balances")]
        return "leave_type" in cols and "remaining" in cols
    except Exception:
        return False


@router.get("/balances", response_model=AdminBalancesResponse)
async def admin_list_balances(
    year: int = Query(..., description="Calendar year (e.g. 2026)"),
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_attendance),
):
    """
    List leave balances for the year. If employee_id given, only that employee.
    Otherwise all employees with balances (optionally filtered by department).
    """
    from app.models.employee import Employee as Emp

    if not _leave_balances_has_new_schema(db):
        raise HTTPException(status_code=503, detail=MIGRATION_REQUIRED_MSG)

    query = db.query(LeaveBalance).filter(LeaveBalance.year == year)
    if employee_id is not None:
        query = query.filter(LeaveBalance.employee_id == employee_id)
    if department_id is not None:
        sub = db.query(Emp.id).filter(Emp.department_id == department_id).subquery()
        query = query.filter(LeaveBalance.employee_id.in_(sub))
    balances = query.order_by(LeaveBalance.employee_id, LeaveBalance.leave_type).all()
    emp_ids = list({b.employee_id for b in balances})

    employees = {}
    depts = {}
    if emp_ids:
        for e in db.query(Emp).filter(Emp.id.in_(emp_ids)).all():
            employees[e.id] = e
        dept_ids = list({e.department_id for e in employees.values() if e.department_id})
        for d in db.query(Department).filter(Department.id.in_(dept_ids)).all():
            depts[d.id] = d.name

    acc_cache = {}
    items = []
    for b in balances:
        if b.leave_type not in WALLET_LEAVE_TYPES:
            continue
        emp = employees.get(b.employee_id)
        if not emp:
            emp = db.query(Emp).filter(Emp.id == b.employee_id).first()
            if emp:
                employees[b.employee_id] = emp
        if emp:
            if b.employee_id not in acc_cache:
                acc_cache[b.employee_id] = wallet.compute_accrual(db, emp, year)
            info = acc_cache[b.employee_id].get(b.leave_type, {})
            allocated = float(b.opening + b.accrued + b.carry_forward)
            items.append(
                AdminBalanceItemOut(
                    employee_id=b.employee_id,
                    employee_name=emp.name if emp else None,
                    department_name=depts.get(emp.department_id) if emp else None,
                    emp_code=emp.emp_code if emp else None,
                    leave_type=b.leave_type,
                    allocated=allocated,
                    opening=float(b.opening),
                    accrued=float(b.accrued),
                    used=float(b.used),
                    remaining=float(b.remaining),
                    eligible=info.get("eligible", True),
                )
            )
    return AdminBalancesResponse(year=year, items=items, total=len(items))


@router.get("/balances/transactions", response_model=List[LeaveTransactionOut])
async def admin_list_balance_transactions(
    employee_id: int = Query(..., description="Employee ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_attendance),
):
    """List leave transactions for an employee (for details drawer)."""
    transactions = wallet.get_transactions(db, employee_id, year=year, limit=limit)
    return [LeaveTransactionOut.model_validate(t) for t in transactions]
