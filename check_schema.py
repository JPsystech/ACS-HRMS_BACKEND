import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('test.db')
cursor = conn.cursor()

# Check leave_requests table schema
cursor.execute('PRAGMA table_info(leave_requests)')
print('leave_requests columns:')
for col in cursor.fetchall():
    print(f'  {col[1]} ({col[2]})')

# Check if approver_id column exists
cursor.execute('PRAGMA table_info(leave_requests)')
columns = [col[1] for col in cursor.fetchall()]
print(f'\napprover_id column exists: {"approver_id" in columns}')

conn.close()