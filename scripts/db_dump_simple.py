import sqlite3
from datetime import datetime

def parse_row_types(row):
    return [type(v).__name__ for v in row]

con = sqlite3.connect("test.db")
cur = con.cursor()
print("One employee row:")
try:
    cur.execute("SELECT id, emp_code, name, role, created_at, updated_at FROM employees LIMIT 1")
    row = cur.fetchone()
    print(row)
    print(parse_row_types(row) if row else None)
except Exception as e:
    print("employees error:", e)

print("One role row:")
try:
    cur.execute("SELECT id, name, role_rank, created_at, updated_at FROM roles LIMIT 1")
    row = cur.fetchone()
    print(row)
    print(parse_row_types(row) if row else None)
except Exception as e:
    print("roles error:", e)

con.close()
