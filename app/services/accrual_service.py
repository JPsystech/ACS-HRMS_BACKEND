"""
Accrual service - monthly leave crediting (uses leave wallet).
Calls leave_wallet_service.ensure_wallet_for_employee with as_of = end of month.
"""
from datetime import date
from typing import Dict, List
from sqlalchemy.orm import Session
from app.models.employee import Employee
from app.models.leave import LeaveBalance
from app.services.audit_service import log_audit
from app.services import leave_wallet_service as wallet


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    if month == 2:
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            return date(year, 2, 29)
        return date(year, 2, 28)
    if month in (4, 6, 9, 11):
        return date(year, month, 30)
    return date(year, month, 31)


def is_eligible_for_month_accrual(
    employee: Employee,
    target_year: int,
    target_month: int
) -> bool:
    """True if employee is active and join_date <= last day of target month."""
    if not employee.active:
        return False
    month_end = _last_day_of_month(target_year, target_month)
    return employee.join_date <= month_end


def run_monthly_accrual(
    db: Session,
    year: int,
    month: int,
    actor_id: int
) -> Dict:
    """
    Run monthly accrual: ensure wallet for all eligible employees with as_of = end of month.
    Wallet computes accrued (CL/PL +1 per month, SL pro-rata annual, RH=1) and updates remaining.
    """
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {month}. Must be between 1 and 12.")
    target_month_key = f"{year:04d}-{month:02d}"
    as_of = _last_day_of_month(year, month)

    employees = db.query(Employee).filter(Employee.active == True).all()
    total_processed = 0
    credited_count = 0
    skipped_not_eligible = 0
    skipped_inactive = 0
    details = []

    for employee in employees:
        total_processed += 1
        if not employee.active:
            skipped_inactive += 1
            continue
        if not is_eligible_for_month_accrual(employee, year, month):
            skipped_not_eligible += 1
            continue
        try:
            wallet.ensure_wallet_for_employee(db, employee.id, year, as_of_date=as_of)
            credited_count += 1
            balances = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id == employee.id,
                LeaveBalance.year == year,
            ).all()
            detail = {"employee_id": employee.id, "emp_code": employee.emp_code, "name": employee.name}
            for b in balances:
                detail[f"{b.leave_type.value.lower()}_remaining"] = float(b.remaining)
            details.append(detail)
        except Exception:
            pass

    log_audit(
        db=db,
        actor_id=actor_id,
        action="ACCRUAL_RUN",
        entity_type="accrual",
        entity_id=None,
        meta={
            "month": target_month_key,
            "year": year,
            "month_number": month,
            "total_employees_processed": total_processed,
            "credited_count": credited_count,
            "skipped_not_eligible": skipped_not_eligible,
            "skipped_inactive": skipped_inactive,
        },
    )
    return {
        "month": target_month_key,
        "total_employees_processed": total_processed,
        "credited_count": credited_count,
        "skipped_already_credited": 0,
        "skipped_not_eligible": skipped_not_eligible,
        "skipped_inactive": skipped_inactive,
        "details": details,
    }


def get_accrual_status(
    db: Session,
    year: int
) -> List[Dict]:
    """Get wallet balance status per employee for the year."""
    employees = db.query(Employee).filter(Employee.active == True).all()
    status_list = []
    for employee in employees:
        balances = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.year == year,
        ).all()
        row = {
            "employee_id": employee.id,
            "emp_code": employee.emp_code,
            "name": employee.name,
            "join_date": str(employee.join_date),
        }
        for b in balances:
            row[f"{b.leave_type.value.lower()}_remaining"] = float(b.remaining)
            row[f"{b.leave_type.value.lower()}_used"] = float(b.used)
        status_list.append(row)
    return status_list
