"""
One-time repair script for 2026 leave balances.

Goal:
- Force entitlements to match ACS policy for 2026:
  PL=7, CL=5, SL=6, RH=1
- Keep `used` as-is.
- Recompute `remaining` = max(entitled - used, 0).

This ignores monthly accrual history and just aligns the wallet to the
final annual entitlements from policy_settings.

Usage (from hrms-backend folder, with .env loaded):

    python scripts/repair_leave_balances_2026.py

Safe to run multiple times (idempotent).
"""

from datetime import date
from pathlib import Path

import sys


# Ensure app package is importable when script is run directly
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session  # type: ignore

from app.db.session import SessionLocal
from app.models.employee import Employee
from app.models.leave import LeaveBalance, LeaveType
from app.services.policy_validator import get_or_create_policy_settings


YEAR = 2026


def repair_for_year(db: Session, year: int) -> None:
    """Repair leave_balances for all employees for the given year."""
    policy = get_or_create_policy_settings(db, year)
    entitlements = {
        LeaveType.PL: int(getattr(policy, "annual_pl", 7)),
        LeaveType.CL: int(getattr(policy, "annual_cl", 5)),
        LeaveType.SL: int(getattr(policy, "annual_sl", 6)),
        LeaveType.RH: int(getattr(policy, "annual_rh", 1)),
    }

    employees = db.query(Employee).filter(Employee.active == True).all()
    total_rows = 0

    for emp in employees:
        for lt, entitled in entitlements.items():
            # Find or create balance row
            bal = (
                db.query(LeaveBalance)
                .filter(
                    LeaveBalance.employee_id == emp.id,
                    LeaveBalance.year == year,
                    LeaveBalance.leave_type == lt,
                )
                .first()
            )
            if not bal:
                bal = LeaveBalance(
                    employee_id=emp.id,
                    year=year,
                    leave_type=lt,
                    opening=0,
                    accrued=0,
                    used=0,
                    remaining=0,
                    carry_forward=0,
                )
                db.add(bal)
                db.flush()

            used = float(bal.used or 0)
            # Store entitlement in `accrued` (opening kept as 0 for simplicity)
            bal.opening = 0
            bal.accrued = entitled
            # Preserve carry_forward if any (e.g. from previous year close)
            remaining = entitled + float(bal.carry_forward or 0) - used
            if remaining < 0:
                remaining = 0
            bal.remaining = remaining
            total_rows += 1

    db.commit()
    print(f"Repaired {total_rows} leave_balances rows for year {year} (employees={len(employees)})")


def main() -> None:
    print(f"Repairing leave balances for year {YEAR} ...")
    db = SessionLocal()
    try:
        repair_for_year(db, YEAR)
    finally:
        db.close()
    print("Done.")


if __name__ == "__main__":
    main()

