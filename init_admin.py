"""
Quick script to initialize default HR admin user
Run this if you don't have an admin user yet
"""
from app.db.session import SessionLocal
from app.db.init_db import init_db
from datetime import datetime
from sqlalchemy import text

if __name__ == "__main__":
    db = SessionLocal()
    try:
        # Check if using SQLite and handle datetime defaults
        from sqlalchemy import inspect
        engine = db.bind
        is_sqlite = engine.dialect.name == 'sqlite'
        
        if is_sqlite:
            # For SQLite, we need to handle datetime defaults manually
            # Check if HR user exists
            from app.models.employee import Employee, Role
            existing_hr = db.query(Employee).filter(Employee.role == Role.HR).first()
            if existing_hr:
                print("HR user already exists, skipping initialization")
                print(f"Existing user: {existing_hr.emp_code}")
            else:
                # Create department if needed
                from app.models.department import Department
                default_dept = db.query(Department).filter(Department.name == "HR").first()
                if not default_dept:
                    # Use raw SQL for SQLite compatibility
                    now = datetime.now().isoformat()
                    db.execute(text(
                        "INSERT INTO departments (name, active, created_at, updated_at) "
                        "VALUES (:name, :active, :created_at, :updated_at)"
                    ), {"name": "HR", "active": 1, "created_at": now, "updated_at": now})
                    db.commit()
                    default_dept = db.query(Department).filter(Department.name == "HR").first()
                
                # Create HR user
                from app.core.security import hash_password
                from datetime import date
                default_hr = Employee(
                    emp_code="HR001",
                    name="Default HR Admin",
                    role=Role.HR,
                    department_id=default_dept.id,
                    password_hash=hash_password("admin123"),
                    join_date=date.today(),
                    active=True
                )
                db.add(default_hr)
                db.commit()
                print("\n✅ Database initialized!")
                print("Login credentials: Employee Code: HR001")
        else:
            # Use the standard init_db for PostgreSQL
            init_db(db)
            print("\n✅ Database initialized!")
            print("Login credentials: Employee Code: HR001")
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
    finally:
        db.close()
