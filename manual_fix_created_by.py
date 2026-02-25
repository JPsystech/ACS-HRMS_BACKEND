#!/usr/bin/env python3
"""
Manually fix the missing created_by column in birthday_greetings table
"""
import sqlite3
import os

def main():
    # Connect to the database
    db_path = 'test.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if created_by column already exists
        cursor.execute('PRAGMA table_info(birthday_greetings)')
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'created_by' in columns:
            print("created_by column already exists")
            return
        
        # Add the missing created_by column
        print("Adding created_by column to birthday_greetings table...")
        cursor.execute("ALTER TABLE birthday_greetings ADD COLUMN created_by INTEGER")
        
        # Add foreign key constraint
        print("Adding foreign key constraint...")
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("""
            CREATE TABLE birthday_greetings_temp (
                id INTEGER PRIMARY KEY,
                employee_id INTEGER NOT NULL,
                date DATE NOT NULL,
                greeting_image_url TEXT,
                greeting_message TEXT,
                created_by INTEGER,
                wish_sent_at DATETIME,
                wish_sent_by INTEGER,
                wish_message TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (employee_id) REFERENCES employees(id),
                FOREIGN KEY (wish_sent_by) REFERENCES employees(id),
                FOREIGN KEY (created_by) REFERENCES employees(id),
                UNIQUE (employee_id, date)
            )
        """)
        
        # Copy data to new table
        print("Migrating data to new table...")
        cursor.execute("""
            INSERT INTO birthday_greetings_temp 
            (id, employee_id, date, greeting_image_url, greeting_message, 
             wish_sent_at, wish_sent_by, wish_message, created_at, updated_at)
            SELECT id, employee_id, date, greeting_image_url, greeting_message,
                   wish_sent_at, wish_sent_by, wish_message, created_at, updated_at
            FROM birthday_greetings
        """)
        
        # Drop old table and rename new one
        cursor.execute("DROP TABLE birthday_greetings")
        cursor.execute("ALTER TABLE birthday_greetings_temp RENAME TO birthday_greetings")
        
        # Recreate indexes
        cursor.execute("CREATE INDEX ix_birthday_greetings_employee_id ON birthday_greetings (employee_id)")
        cursor.execute("CREATE INDEX ix_birthday_greetings_date ON birthday_greetings (date)")
        
        conn.commit()
        print("Schema fix completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()