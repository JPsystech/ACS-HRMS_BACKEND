#!/usr/bin/env python3
import sqlite3
import os

def find_db():
    candidates = [
        os.path.join(os.getcwd(), "test.db"),
        os.path.join(os.getcwd(), "instance", "acs_hrms.db"),
        os.path.join(os.getcwd(), "acs_hrms.db"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def ensure_columns(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(company_events)")
    cols = {row[1] for row in cur.fetchall()}

    to_add = []
    if "description" not in cols:
        to_add.append(("description", "TEXT"))
    if "image_url" not in cols:
        to_add.append(("image_url", "VARCHAR(500)"))
    if "location" not in cols:
        to_add.append(("location", "VARCHAR(255)"))

    for name, typ in to_add:
        cur.execute(f"ALTER TABLE company_events ADD COLUMN {name} {typ} NULL")
        print(f"Added column {name} ({typ})")

    conn.commit()

def main():
    db_path = find_db()
    if not db_path:
        print("Database not found")
        return 1
    conn = sqlite3.connect(db_path)
    try:
        ensure_columns(conn)
        print("company_events columns verified/updated")
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    raise SystemExit(main())
