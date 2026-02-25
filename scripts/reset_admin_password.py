from app.db.session import SessionLocal
from app.models.employee import Employee
from app.core.security import hash_password

def main():
    db = SessionLocal()
    try:
        admin = db.query(Employee).filter(Employee.emp_code == "ADM-001").first()
        if not admin:
            print("ADM-001 not found")
            return
        new_pw = "Admin@12345"
        admin.password_hash = hash_password(new_pw)
        db.commit()
        print("✅ ADM-001 password reset to Admin@12345")
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
