
import os
import sys
from pathlib import Path

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent))

from app.db.session import SessionLocal
from app.models.employee import Employee

def check_db():
    db = SessionLocal()
    try:
        e = db.query(Employee).filter(Employee.id == 7).first()
        if e:
            print(f"Employee 7:")
            print(f" - Name: {e.name}")
            print(f" - Photo Key: {e.photo_key}")
            print(f" - Photo URL: {e.profile_photo_url}")
            print(f" - Photo Updated At: {e.profile_photo_updated_at}")
        else:
            print("Employee 7 not found.")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
