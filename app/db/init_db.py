"""
Database initialization script
Helper function to seed minimal demo data
"""
from sqlalchemy.orm import Session
from app.models.department import Department
from app.models.employee import Employee, Role
from app.core.security import hash_password
from datetime import date


def init_db(db: Session) -> None:
    """
    Initialize database with default HR user if none exists
    
    This is a helper function and should NOT be auto-run on startup.
    Call manually when needed for initial setup.
    """
    # Check if any HR user exists
    existing_hr = db.query(Employee).filter(Employee.role == Role.HR).first()
    if existing_hr:
        print("HR user already exists, skipping initialization")
        return
    
    # Create default department if none exists
    default_dept = db.query(Department).filter(Department.name == "HR").first()
    if not default_dept:
        default_dept = Department(
            name="HR",
            active=True
        )
        db.add(default_dept)
        db.flush()
    
    # Create default HR user
    default_hr = Employee(
        emp_code="HR001",
        name="Default HR Admin",
        role=Role.HR,
        department_id=default_dept.id,
        password_hash=hash_password("admin123"),  # Change this in production!
        join_date=date.today(),
        active=True
    )
    db.add(default_hr)
    db.commit()
    print("Default HR user created: emp_code=HR001")
