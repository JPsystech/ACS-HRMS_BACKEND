import sqlite3

def main():
    con = sqlite3.connect("test.db")
    cur = con.cursor()
    try:
        cur.execute("PRAGMA table_info(roles)")
        cols = cur.fetchall()
        print("roles columns:", cols)
    except Exception as e:
        print("roles table error:", e)
    try:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        print("tables:", [r[0] for r in cur.fetchall()])
    except Exception as e:
        print("list tables error:", e)
    try:
        cur.execute("SELECT COUNT(*) FROM roles")
        print("roles count:", cur.fetchone()[0])
    except Exception as e:
        print("roles count error:", e)
    con.close()

if __name__ == "__main__":
    main()
