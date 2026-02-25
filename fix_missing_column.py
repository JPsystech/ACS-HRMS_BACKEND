#!/usr/bin/env python3
"""
Quick script to fix missing greeting_message column in birthday_greetings table
"""
import sqlite3
import os

def main():
    # Connect to the database - try multiple possible locations
    possible_paths = [
        os.path.join(os.getcwd(), 'instance', 'acs_hrms.db'),
        os.path.join(os.getcwd(), 'test.db'),
        os.path.join(os.getcwd(), 'acs_hrms.db')
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("Database not found in any expected location")
        print("Searched in:", possible_paths)
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(birthday_greetings)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'greeting_message' in columns:
            print("greeting_message column already exists")
            return
        
        # Add the missing column
        print("Adding greeting_message column to birthday_greetings table...")
        cursor.execute("ALTER TABLE birthday_greetings ADD COLUMN greeting_message TEXT")
        conn.commit()
        print("Column added successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()