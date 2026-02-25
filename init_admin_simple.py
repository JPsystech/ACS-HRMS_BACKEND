"""
Simple script to create admin user using bcrypt directly
"""
import bcrypt
from datetime import date, datetime
from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.employee import Employee, Role
from app.models.department import Department

if __name__ == "__main__":
    db = SessionLocal()
    try:
        # First create all tables if they don't exist
        from app.db.base import Base
        Base.metadata.create_all(bind=db.bind)
        
        # Check if HR user exists
        existing_hr = db.query(Employee).filter(Employee.role == Role.HR).first()
        if existing_hr:
            print(f"HR user already exists: {existing_hr.emp_code}")
            print("Login credentials: Employee Code: HR001")
        else:
            # Create department if needed
            default_dept = db.query(Department).filter(Department.name == "HR").first()
            if not default_dept:
                # Use raw SQL for SQLite compatibility
                engine = db.bind
                is_sqlite = engine.dialect.name == 'sqlite'
                now = datetime.now().isoformat()
                
                if is_sqlite:
                    db.execute(text(
                        "INSERT INTO departments (name, active, created_at, updated_at) "
                        "VALUES (:name, :active, :created_at, :updated_at)"
                    ), {"name": "HR", "active": 1, "created_at": now, "updated_at": now})
                else:
                    default_dept = Department(name="HR", active=True)
                    db.add(default_dept)
                
                db.commit()
                default_dept = db.query(Department).filter(Department.name == "HR").first()
            
            # Hash password using bcrypt directly
            password = "admin123"
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Create HR user
            default_hr = Employee(
                emp_code="HR001",
                name="Default HR Admin",
                role=Role.HR,
                department_id=default_dept.id,
                password_hash=password_hash,
                join_date=date.today(),
                active=True
            )
            db.add(default_hr)
            db.commit()
            print("\n✅ Admin user created successfully!")
            print("Login credentials: Employee Code: HR001")
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
    finally:
        db.close()
