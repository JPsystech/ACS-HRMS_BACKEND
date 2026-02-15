"""
Tests for holiday integration in leave day calculation and RH validation
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.holiday import Holiday, RestrictedHoliday
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus, LeaveBalance
from app.core.security import hash_password
from decimal import Decimal


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


def test_holiday_excluded_from_baseline_count(client, db, hr_employee, test_employee):
    """Test that holidays are excluded from leave day calculation"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create a holiday on a weekday
    today = date.today()
    # Find next Monday
    days_until_monday = (0 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    monday = today + timedelta(days=days_until_monday)
    tuesday = monday + timedelta(days=1)
    wednesday = tuesday + timedelta(days=1)
    
    # Create holiday on Tuesday
    client.post(
        "/api/v1/holidays",
        json={
            "year": monday.year,
            "date": str(tuesday),
            "name": "Test Holiday",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Apply leave from Monday to Wednesday (should exclude Tuesday holiday)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(monday),
            "to_date": str(wednesday),
            "reason": "Test leave"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    # Should count 2 days (Monday + Wednesday), excluding Tuesday holiday
    assert float(data["computed_days"]) == 2.0


def test_rh_apply_requires_rh_date(client, db, hr_employee, test_employee):
    """Test that RH can only be applied on valid RH dates"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create an RH date
    today = date.today()
    rh_date = today + timedelta(days=10)
    
    client.post(
        "/api/v1/restricted-holidays",
        json={
            "year": rh_date.year,
            "date": str(rh_date),
            "name": "Test RH",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Try to apply RH on non-RH date (should fail)
    non_rh_date = rh_date + timedelta(days=1)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "RH",
            "from_date": str(non_rh_date),
            "to_date": str(non_rh_date),
            "reason": "Test RH"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "restricted holiday" in response.json()["detail"].lower() or "rh" in response.json()["detail"].lower()
    
    # Apply RH on valid RH date (should succeed)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "RH",
            "from_date": str(rh_date),
            "to_date": str(rh_date),
            "reason": "Test RH"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["leave_type"] == "RH"
    assert data["status"] == "PENDING"


def test_rh_apply_single_day_only(client, db, hr_employee, test_employee):
    """Test that RH must be applied for a single day only"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create RH dates
    today = date.today()
    rh_date1 = today + timedelta(days=10)
    rh_date2 = rh_date1 + timedelta(days=1)
    
    client.post(
        "/api/v1/restricted-holidays",
        json={
            "year": rh_date1.year,
            "date": str(rh_date1),
            "name": "Test RH 1",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    client.post(
        "/api/v1/restricted-holidays",
        json={
            "year": rh_date2.year,
            "date": str(rh_date2),
            "name": "Test RH 2",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Try to apply RH for multiple days (should fail)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "RH",
            "from_date": str(rh_date1),
            "to_date": str(rh_date2),
            "reason": "Test RH"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "single day" in response.json()["detail"].lower()


def test_rh_quota_one_per_year_enforced_on_approval(
    client, db, hr_employee, manager_employee, reportee_employee
):
    """Test that RH quota (1 per year) is enforced on approval"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Create two RH dates
    today = date.today()
    rh_date1 = today + timedelta(days=10)
    rh_date2 = rh_date1 + timedelta(days=5)
    
    client.post(
        "/api/v1/restricted-holidays",
        json={
            "year": rh_date1.year,
            "date": str(rh_date1),
            "name": "Test RH 1",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    client.post(
        "/api/v1/restricted-holidays",
        json={
            "year": rh_date2.year,
            "date": str(rh_date2),
            "name": "Test RH 2",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Create leave balance with PL
    balance = LeaveBalance(
        employee_id=reportee_employee.id,
        year=rh_date1.year,
        pl_balance=Decimal('10.0'),
        cl_balance=Decimal('0'),
        sl_balance=Decimal('0'),
        rh_used=0
    )
    db.add(balance)
    db.commit()
    
    # Apply first RH
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "RH",
            "from_date": str(rh_date1),
            "to_date": str(rh_date1),
            "reason": "Test RH 1"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    leave_id1 = response.json()["id"]
    
    # Approve first RH
    response = client.post(
        f"/api/v1/leaves/{leave_id1}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Apply second RH
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "RH",
            "from_date": str(rh_date2),
            "to_date": str(rh_date2),
            "reason": "Test RH 2"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    leave_id2 = response.json()["id"]
    
    # Try to approve second RH (should fail due to quota)
    response = client.post(
        f"/api/v1/leaves/{leave_id2}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "quota" in response.json()["detail"].lower() or "already used" in response.json()["detail"].lower()


def test_rh_deducts_pl_balance(client, db, hr_employee, manager_employee, reportee_employee):
    """Test that RH deducts PL balance"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Create RH date
    today = date.today()
    rh_date = today + timedelta(days=10)
    
    client.post(
        "/api/v1/restricted-holidays",
        json={
            "year": rh_date.year,
            "date": str(rh_date),
            "name": "Test RH",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Create leave balance with PL
    initial_pl = Decimal('5.0')
    balance = LeaveBalance(
        employee_id=reportee_employee.id,
        year=rh_date.year,
        pl_balance=initial_pl,
        cl_balance=Decimal('0'),
        sl_balance=Decimal('0'),
        rh_used=0
    )
    db.add(balance)
    db.commit()
    
    # Apply RH
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "RH",
            "from_date": str(rh_date),
            "to_date": str(rh_date),
            "reason": "Test RH"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    leave_id = response.json()["id"]
    
    # Approve RH
    response = client.post(
        f"/api/v1/leaves/{leave_id}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Verify PL balance was deducted
    db.refresh(balance)
    assert float(balance.pl_balance) == float(initial_pl - Decimal('1.0'))
    
    # Verify rh_used was incremented
    assert balance.rh_used == 1
    
    # Verify leave request has paid_days = 1
    leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    assert float(leave_request.paid_days) == 1.0
    assert float(leave_request.lwp_days) == 0.0
