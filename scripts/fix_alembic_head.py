import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "test.db")
DB_PATH = os.path.abspath(DB_PATH)

# Choose a known good revision present in the repo history
# This sits before our new 030_add_holiday_image_key branch.
TARGET_REVISION = "029_add_photo_key"

def main():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return 1

    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        # Ensure table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        row = cur.fetchone()
        if not row:
            print("alembic_version table not found; nothing to fix")
            return 0

        # Read current revision(s)
        try:
            cur.execute("SELECT version_num FROM alembic_version")
            versions = [r[0] for r in cur.fetchall()]
            print("Current alembic versions:", versions)
        except Exception as e:
            print("Failed reading alembic_version:", e)

        # Overwrite with a known revision
        cur.execute("DELETE FROM alembic_version")
        cur.execute("INSERT INTO alembic_version (version_num) VALUES (?)", (TARGET_REVISION,))
        con.commit()
        print(f"Stamped alembic_version to {TARGET_REVISION}")
        return 0
    finally:
        con.close()

if __name__ == "__main__":
    raise SystemExit(main())
