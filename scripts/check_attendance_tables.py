#!/usr/bin/env python3
"""
Check whether attendance_sessions (and optionally attendance_events) table exists.
Uses the same DATABASE_URL as the app (from app.core.config.settings).
Run from project root: python scripts/check_attendance_tables.py
Or: cd hrms-backend && python scripts/check_attendance_tables.py
"""
import sys
import os

# Ensure app is importable (run from hrms-backend or repo root)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main() -> int:
    try:
        from app.core.config import settings
        from sqlalchemy import create_engine, text
    except ImportError as e:
        print("Error: Could not import app or sqlalchemy.", e, file=sys.stderr)
        return 1

    url = settings.DATABASE_URL
    print(f"DATABASE_URL: {url if url.startswith('sqlite') else url.split('@')[-1]}")
    engine = create_engine(url)

    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            r = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_sessions'"
            ))
            sessions_exists = r.scalar() is not None
            r = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_events'"
            ))
            events_exists = r.scalar() is not None
        else:
            # PostgreSQL / generic
            r = conn.execute(text(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'attendance_sessions'"
            ))
            sessions_exists = r.scalar() is not None
            r = conn.execute(text(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'attendance_events'"
            ))
            events_exists = r.scalar() is not None

    print(f"attendance_sessions: {'exists' if sessions_exists else 'MISSING'}")
    print(f"attendance_events:   {'exists' if events_exists else 'MISSING'}")
    if not sessions_exists:
        print("Run: alembic upgrade head (from hrms-backend directory)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
