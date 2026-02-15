"""
Backfill leave wallet for all active employees for a given year.
Run after migration 017. Creates leave_balances rows (CL, SL, PL, RH) and computes accrual.

Usage:
  python scripts/backfill_leave_wallet.py --year 2026
  python scripts/backfill_leave_wallet.py --year 2026 --dry-run
"""
import argparse
import sys
from pathlib import Path

# Add project root so app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session
from app.db import session as db_session
from app.models.employee import Employee
from app.services import leave_wallet_service as wallet


def main():
    parser = argparse.ArgumentParser(description="Backfill leave wallet for a year")
    parser.add_argument("--year", type=int, required=True, help="Calendar year (e.g. 2026)")
    parser.add_argument("--dry-run", action="store_true", help="Do not commit")
    args = parser.parse_args()

    db: Session = db_session.SessionLocal()
    try:
        employees = db.query(Employee).filter(Employee.active == True).all()
        print(f"Year {args.year}: ensuring wallet for {len(employees)} active employees...")
        for i, emp in enumerate(employees):
            try:
                wallet.ensure_wallet_for_employee(db, emp.id, args.year)
                if (i + 1) % 50 == 0:
                    print(f"  {i + 1}/{len(employees)}")
            except Exception as e:
                print(f"  Skip employee {emp.id} ({emp.emp_code}): {e}")
        if args.dry_run:
            db.rollback()
            print("Dry run: rolled back.")
        else:
            db.commit()
            print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
