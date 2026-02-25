"""
Debug endpoint for login issues
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import get_db
from app.models.employee import Employee

router = APIRouter()

@router.get("/debug/employees")
async def debug_employees(db: Session = Depends(get_db)):
    """Debug endpoint to check employee data"""
    employees = db.query(Employee).limit(5).all()
    result = []
    for emp in employees:
        result.append({
            "id": emp.id,
            "emp_code": emp.emp_code,
            "name": emp.name,
            "active": emp.active,
            "has_password": emp.password_hash is not None,
            "must_change_password": getattr(emp, 'must_change_password', None),
            "password_changed_at": getattr(emp, 'password_changed_at', None),
            "last_login_at": getattr(emp, 'last_login_at', None)
        })
    return {"employees": result}

@router.post("/debug/login-test")
async def debug_login_test(emp_code: str, password: str, db: Session = Depends(get_db)):
    """Debug endpoint to test login step by step"""
    # Find employee
    employee = db.query(Employee).filter(Employee.emp_code == emp_code).first()
    
    if not employee:
        return {"error": "Employee not found", "emp_code": emp_code}
    
    result = {
        "employee_found": True,
        "emp_code": employee.emp_code,
        "name": employee.name,
        "active": employee.active,
        "has_password": employee.password_hash is not None,
        "must_change_password": getattr(employee, 'must_change_password', None),
        "password_changed_at": getattr(employee, 'password_changed_at', None),
        "last_login_at": getattr(employee, 'last_login_at', None)
    }
    
    # Check if active
    if not employee.active:
        result["error"] = "Account is inactive"
        return result
    
    # Check if password exists
    if employee.password_hash is None:
        result["error"] = "No password set"
        return result
    
    # Test password verification
    from app.core.security import verify_password
    password_valid = verify_password(password, employee.password_hash)
    result["password_valid"] = password_valid
    
    if not password_valid:
        result["error"] = "Invalid password"
        return result
    
    # If we get here, login should work
    result["login_success"] = True
    
    # Update last_login_at
    from datetime import datetime
    try:
        employee.last_login_at = datetime.utcnow()
        db.add(employee)
        db.commit()
        result["last_login_updated"] = True
    except Exception as e:
        db.rollback()
        result["last_login_updated"] = False
        result["last_login_error"] = str(e)
    
    return result
