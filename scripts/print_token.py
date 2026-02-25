import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.db.session import SessionLocal
from app.models.employee import Employee
from app.core.security import create_access_token

def main():
    db = SessionLocal()
    try:
        emp = db.query(Employee).filter(Employee.emp_code == "ADM-001").first()
        if not emp:
            print("Employee ADM-001 not found")
            return
        token = create_access_token(data={"sub": str(emp.id), "emp_code": emp.emp_code, "role": emp.role, "role_rank": 1})
        print(token)
    finally:
        db.close()

if __name__ == "__main__":
    main()
