"""
Tests for attendance list endpoints with role-based scoping
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.manager_department import ManagerDepartment
from app.models.attendance import AttendanceLog
from app.core.security import hash_password


@pytest.fixture
def hr_dept(db: Session):
    """Create HR department"""
    dept = Department(name="HR", active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@pytest.fixture
def qa_dept(db: Session):
    """Create QA department"""
    dept = Department(name="QA", active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@pytest.fixture
def hr_user(db: Session, hr_dept):
    """Create HR user"""
    hr = Employee(
        emp_code="HR001",
        name="HR Admin",
        role=Role.HR,
        department_id=hr_dept.id,
        password_hash=hash_password("hrpass123"),
        join_date=date.today(),
        active=True
    )
    db.add(hr)
    db.commit()
    db.refresh(hr)
    return hr


@pytest.fixture
def manager_user(db: Session, hr_dept):
    """Create manager user"""
    manager = Employee(
        emp_code="MGR001",
        name="Manager",
        role=Role.MANAGER,
        department_id=hr_dept.id,
        password_hash=hash_password("mgrpass123"),
        join_date=date.today(),
        active=True
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)
    return manager


@pytest.fixture
def hr_employee(db: Session, hr_dept):
    """Create employee in HR department"""
    emp = Employee(
        emp_code="HR_EMP001",
        name="HR Employee",
        role=Role.EMPLOYEE,
        department_id=hr_dept.id,
        password_hash=hash_password("emppass123"),
        join_date=date.today(),
        active=True
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def qa_employee(db: Session, qa_dept):
    """Create employee in QA department"""
    emp = Employee(
        emp_code="QA_EMP001",
        name="QA Employee",
        role=Role.EMPLOYEE,
        department_id=qa_dept.id,
        password_hash=hash_password("emppass123"),
        join_date=date.today(),
        active=True
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def manager_department_mapping(db: Session, manager_user, hr_dept):
    """Map manager to HR department"""
    mapping = ManagerDepartment(
        manager_id=manager_user.id,
        department_id=hr_dept.id
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@pytest.fixture
def attendance_records(db: Session, hr_employee, qa_employee):
    """Create attendance records for both employees"""
    today = date.today()
    from datetime import datetime, timezone
    
    # Create attendance for HR employee
    hr_attendance = AttendanceLog(
        employee_id=hr_employee.id,
        punch_date=today,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        source="mobile"
    )
    
    # Create attendance for QA employee
    qa_attendance = AttendanceLog(
        employee_id=qa_employee.id,
        punch_date=today,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6140,
        in_lng=77.2091,
        source="mobile"
    )
    
    db.add_all([hr_attendance, qa_attendance])
    db.commit()
    db.refresh(hr_attendance)
    db.refresh(qa_attendance)
    return [hr_attendance, qa_attendance]


def get_auth_token(client, emp_code, password):
    """Helper to get auth token"""
    response = client.post(
        "/api/v1/auth/login",
        json={"emp_code": emp_code, "password": password}
    )
    return response.json()["access_token"]


def test_attendance_list_scope_hr_sees_all(
    client, db, hr_user, hr_employee, qa_employee, attendance_records
):
    """Test that HR can see all employees' attendance"""
    token = get_auth_token(client, "HR001", "hrpass123")
    today = date.today()
    
    response = client.get(
        f"/api/v1/attendance/list?from={today}&to={today}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    
    # Verify both employees are in the list
    employee_ids = [item["employee_id"] for item in data["items"]]
    assert hr_employee.id in employee_ids
    assert qa_employee.id in employee_ids


def test_attendance_list_scope_manager_sees_mapped_dept_only(
    client, db, manager_user, hr_employee, qa_employee, 
    manager_department_mapping, attendance_records
):
    """Test that MANAGER sees only employees in mapped departments"""
    token = get_auth_token(client, "MGR001", "mgrpass123")
    today = date.today()
    
    response = client.get(
        f"/api/v1/attendance/list?from={today}&to={today}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Manager should only see HR department employee (mapped to HR dept)
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["employee_id"] == hr_employee.id
    assert data["items"][0]["employee_id"] != qa_employee.id


def test_attendance_list_scope_employee_sees_own_only(
    client, db, hr_employee, qa_employee, attendance_records
):
    """Test that EMPLOYEE sees only their own attendance"""
    token = get_auth_token(client, "HR_EMP001", "emppass123")
    today = date.today()
    
    response = client.get(
        f"/api/v1/attendance/list?from={today}&to={today}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Employee should only see their own records
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["employee_id"] == hr_employee.id


def test_attendance_list_date_range_validation(client, db, hr_user):
    """Test that invalid date range returns 400"""
    token = get_auth_token(client, "HR001", "hrpass123")
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # from_date > to_date should fail
    response = client.get(
        f"/api/v1/attendance/list?from={today}&to={yesterday}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
