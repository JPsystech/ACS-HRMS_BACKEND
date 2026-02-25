import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('test.db')
cursor = conn.cursor()

# Check leave requests with approver_id
cursor.execute('SELECT id, employee_id, approver_id FROM leave_requests LIMIT 5')
print('Leave requests:')
for row in cursor.fetchall():
    print(f'  ID: {row[0]}, Employee: {row[1]}, Approver: {row[2]}')

conn.close()