from app.db.session import SessionLocal
from app.services.employee_service import list_employees

def main():
    db = SessionLocal()
    try:
        items = list_employees(db)
        print("Employees:", len(items))
        for e in items:
            print(e.id, e.emp_code, e.name, e.role, e.role_rank)
    except Exception as e:
        print("Error:", repr(e))
    finally:
        db.close()

if __name__ == "__main__":
    main()
