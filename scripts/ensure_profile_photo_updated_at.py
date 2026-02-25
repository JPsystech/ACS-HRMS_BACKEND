import os
import sqlite3

DB_FILE = os.environ.get("HRMS_SQLITE_PATH", "test.db")

con = sqlite3.connect(DB_FILE)
cur = con.cursor()
cur.execute("PRAGMA table_info(employees)")
cols = [r[1] for r in cur.fetchall()]
if "profile_photo_updated_at" not in cols:
    cur.execute("ALTER TABLE employees ADD COLUMN profile_photo_updated_at TEXT")
    con.commit()
con.close()
print("OK")
