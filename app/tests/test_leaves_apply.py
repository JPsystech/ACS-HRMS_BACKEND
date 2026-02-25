"""
Tests for leave apply endpoints
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime, timezone
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus
from app.core.security import hash_password


@pytest.fixture
def test_department(db: Session):
    """Create a test department"""
    dept = Department(name="IT", active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@pytest.fixture
def test_employee(db: Session, test_department):
    """Create a test employee"""
    employee = Employee(
        emp_code="EMP001",
        name="Test Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("testpass123"),
        join_date=date.today(),
        active=True
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@pytest.fixture
def manager_employee(db: Session, test_department):
    """Create a manager employee"""
    manager = Employee(
        emp_code="MGR001",
        name="Manager",
        role=Role.MANAGER,
        department_id=test_department.id,
        password_hash=hash_password("mgrpass123"),
        join_date=date.today(),
        active=True
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)
    return manager


@pytest.fixture
def hr_employee(db: Session, test_department):
    """Create an HR employee"""
    hr = Employee(
        emp_code="HR001",
        name="HR Admin",
        role=Role.HR,
        department_id=test_department.id,
        password_hash=hash_password("hrpass123"),
        join_date=date.today(),
        active=True
    )
    db.add(hr)
    db.commit()
    db.refresh(hr)
    return hr


@pytest.fixture
def reportee_employee(db: Session, test_department, manager_employee):
    """Create an employee reporting to manager"""
    emp = Employee(
        emp_code="REP001",
        name="Reportee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        reporting_manager_id=manager_employee.id,
        password_hash=hash_password("reppass123"),
        join_date=date.today(),
        active=True
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def get_auth_token(client, emp_code, password):
    """Helper to get auth token"""
    response = client.post(
        "/api/v1/auth/login",
        json={"emp_code": emp_code, "password": password}
    )
    return response.json()["access_token"]


def test_leave_apply_success_excludes_sunday(client, db, test_employee):
    """Test that leave apply excludes Sundays in day calculation"""
    token = get_auth_token(client, "EMP001", "testpass123")
    
    # Find a Saturday and Monday (skipping Sunday)
    today = date.today()
    # Find next Saturday
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and today.weekday() != 5:
        days_until_saturday = 7
    saturday = today + timedelta(days=days_until_saturday)
    monday = saturday + timedelta(days=2)  # Skip Sunday
    
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(saturday),
            "to_date": str(monday),
            "reason": "Test leave"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["leave_type"] == "CL"
    # Should count 2 days (Saturday + Monday), excluding Sunday
    assert float(data["computed_days"]) == 2.0


def test_leave_apply_invalid_date_order(client, db, test_employee):
    """Test that from_date > to_date returns 400"""
    token = get_auth_token(client, "EMP001", "testpass123")
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(today),
            "to_date": str(yesterday)
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "from_date" in response.json()["detail"].lower() or "less than" in response.json()["detail"].lower()


def test_leave_apply_overlap_rejected(client, db, test_employee):
    """Test that overlapping leave requests are rejected"""
    token = get_auth_token(client, "EMP001", "testpass123")
    today = date.today()
    day1 = today + timedelta(days=1)
    day2 = today + timedelta(days=2)
    day3 = today + timedelta(days=3)
    
    # Create first leave request (PENDING)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(day1),
            "to_date": str(day2)
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Try to create overlapping leave (should be rejected)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "PL",
            "from_date": str(day2),
            "to_date": str(day3)
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "overlap" in response.json()["detail"].lower()


def test_leave_apply_cross_year_rejected(client, db, test_employee):
    """Test that cross-year leave requests are rejected"""
    token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create dates that span across years
    dec_31 = date(2026, 12, 31)
    jan_1 = date(2027, 1, 1)
    
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(dec_31),
            "to_date": str(jan_1)
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "year" in response.json()["detail"].lower() or "span" in response.json()["detail"].lower()


def test_leave_list_scope_hr_sees_all(client, db, hr_employee, test_employee, reportee_employee):
    """Test that HR can see all leave requests"""
    token = get_auth_token(client, "HR001", "hrpass123")
    today = date.today()
    day1 = today + timedelta(days=1)
    day2 = today + timedelta(days=2)
    
    # Create leave for test_employee
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(day1),
            "to_date": str(day2)
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # HR should see all leaves
    response = client.get(
        f"/api/v1/leaves/list?from={day1}&to={day2}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] >= 1


def test_leave_list_scope_manager_sees_direct_reportees_only(
    client, db, manager_employee, test_employee, reportee_employee
):
    """Test that MANAGER sees only direct reportees' leaves"""
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    today = date.today()
    day1 = today + timedelta(days=1)
    day2 = today + timedelta(days=2)
    
    # Create leave for reportee (manager should see this)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(day1),
            "to_date": str(day2)
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Create leave for non-reportee (manager should NOT see this)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "PL",
            "from_date": str(day1),
            "to_date": str(day2)
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Manager should see only reportee's leaves
    response = client.get(
        f"/api/v1/leaves/list?from={day1}&to={day2}",
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Should see at least reportee's leave
    assert data["total"] >= 1
    # Verify all leaves belong to reportee
    for item in data["items"]:
        assert item["employee_id"] == reportee_employee.id


def test_leave_list_scope_employee_sees_own_only(client, db, test_employee, reportee_employee):
    """Test that EMPLOYEE sees only their own leaves"""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    today = date.today()
    day1 = today + timedelta(days=1)
    day2 = today + timedelta(days=2)
    
    # Create leave for test_employee
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(day1),
            "to_date": str(day2)
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Create leave for reportee
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "PL",
            "from_date": str(day1),
            "to_date": str(day2)
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Employee should see only their own leaves
    response = client.get(
        f"/api/v1/leaves/list?from={day1}&to={day2}",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["employee_id"] == test_employee.id
