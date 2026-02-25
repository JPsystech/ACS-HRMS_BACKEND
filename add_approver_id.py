import sqlite3

# Connect to the SQLite database
conn = sqlite3.connect('test.db')
cursor = conn.cursor()

# Check if approver_id column already exists
cursor.execute('PRAGMA table_info(leave_requests)')
columns = [col[1] for col in cursor.fetchall()]

if 'approver_id' not in columns:
    print("Adding approver_id column to leave_requests table...")
    try:
        # Add the approver_id column
        cursor.execute('ALTER TABLE leave_requests ADD COLUMN approver_id INTEGER')
        conn.commit()
        print("Successfully added approver_id column!")
        
        # Verify the column was added
        cursor.execute('PRAGMA table_info(leave_requests)')
        new_columns = [col[1] for col in cursor.fetchall()]
        print(f"approver_id column exists: {'approver_id' in new_columns}")
        
    except sqlite3.Error as e:
        print(f"Error adding column: {e}")
else:
    print("approver_id column already exists")

conn.close()