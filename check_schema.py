#!/usr/bin/env python3
"""
Check the current schema of birthday_greetings table
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
        # Check current columns
        cursor.execute('PRAGMA table_info(birthday_greetings)')
        columns = cursor.fetchall()
        
        print('Current columns in birthday_greetings table:')
        for col in columns:
            print(f'  {col[1]} ({col[2]}) - nullable: {col[3]}, pk: {col[5]}')
        
        # Check expected columns from model
        expected_columns = [
            'id', 'employee_id', 'date', 'greeting_image_url', 'greeting_message',
            'created_by', 'wish_sent_at', 'wish_sent_by', 'wish_message',
            'created_at', 'updated_at'
        ]
        
        print('\nMissing columns:')
        current_col_names = [col[1] for col in columns]
        for expected in expected_columns:
            if expected not in current_col_names:
                print(f'  {expected}')
                
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()