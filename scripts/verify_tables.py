import sys
import sqlite3
import os

TABLES = [
    "birthday_greetings",
    "birthday_wishes",
    "attendance_sessions",
    "attendance_events",
    "attendance_daily",
]

def main() -> int:
    db = "test.db"
    if not os.path.exists(db):
        print(f"Database not found: {db}")
        return 1
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    def exists(t: str) -> bool:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (t,))
        return cur.fetchone() is not None
    missing = []
    for t in TABLES:
        ok = exists(t)
        print(f"{t}: {'exists' if ok else 'MISSING'}")
        if not ok:
            missing.append(t)
    conn.close()
    return 0 if not missing else 1

if __name__ == "__main__":
    sys.exit(main())
