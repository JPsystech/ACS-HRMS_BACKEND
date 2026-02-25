"""
Check if leave_balances table has the new wallet schema (leave_type, remaining).
Run from hrms-backend with the same .env as the app. If the server is running,
this uses a separate connection and is safe to run.

Usage: python scripts/check_leave_wallet_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy import inspect
from app.core.config import settings


def main():
    print(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)
    insp = inspect(engine)
    tables = insp.get_table_names()

    if "leave_balances" not in tables:
        print("Table 'leave_balances' does not exist. Run: alembic upgrade head")
        return

    cols = [c["name"] for c in insp.get_columns("leave_balances")]
    has_leave_type = "leave_type" in cols
    has_remaining = "remaining" in cols
    has_old = "cl_balance" in cols

    if has_leave_type and has_remaining:
        print("OK: leave_balances has the new wallet schema (leave_type, remaining).")
        with engine.connect() as conn:
            r = conn.execute(text("SELECT COUNT(*) FROM leave_balances"))
            n = r.scalar()
        print(f"     Rows: {n}. If 0, run: python scripts/backfill_leave_wallet.py --year 2026")
        return

    if has_old:
        print("PROBLEM: leave_balances still has the OLD schema (cl_balance, etc.).")
        print("")
        print("Do this:")
        print("  1. STOP the backend server (stop uvicorn completely).")
        print("  2. In a terminal:  cd hrms-backend")
        print("  3. Run:  alembic upgrade head")
        print("  4. Start the backend server again.")
        print("")
        print("If step 3 fails with 'disk I/O error', the database file is still in use. Close any app using it and retry.")
        return

    print("Unexpected schema. Columns:", cols)
    print("Run: alembic upgrade head  (with server stopped)")


if __name__ == "__main__":
    main()
