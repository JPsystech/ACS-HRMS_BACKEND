"""
Tests for monthly accrual engine
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.leave import LeaveBalance
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
def hr_employee(db: Session, test_department):
    """Create an HR employee"""
    join_date = date.today() - timedelta(days=180)  # 6 months ago
    hr = Employee(
        emp_code="HR001",
        name="HR Admin",
        role=Role.HR,
        department_id=test_department.id,
        password_hash=hash_password("hrpass123"),
        join_date=join_date,
        active=True
    )
    db.add(hr)
    db.commit()
    db.refresh(hr)
    return hr


@pytest.fixture
def employee_joined_feb_10(db: Session, test_department):
    """Create employee who joined Feb 10 (eligible for Feb accrual)"""
    join_date = date(2026, 2, 10)
    emp = Employee(
        emp_code="FEB10",
        name="Feb 10 Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("feb10pass"),
        join_date=join_date,
        active=True
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def employee_joined_feb_20(db: Session, test_department):
    """Create employee who joined Feb 20 (eligible from Mar accrual)"""
    join_date = date(2026, 2, 20)
    emp = Employee(
        emp_code="FEB20",
        name="Feb 20 Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("feb20pass"),
        join_date=join_date,
        active=True
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def inactive_employee(db: Session, test_department):
    """Create inactive employee"""
    join_date = date(2026, 1, 5)
    emp = Employee(
        emp_code="INACTIVE",
        name="Inactive Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("inactivepass"),
        join_date=join_date,
        active=False
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
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code} - {response.json()}")
    return response.json()["access_token"]


def test_accrual_credits_eligible_employees_and_caps(client, db, hr_employee, test_department):
    """Test that accrual credits eligible employees and respects caps"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create employee with balance near cap
    join_date = date(2026, 1, 5)
    emp = Employee(
        emp_code="CAP001",
        name="Cap Test Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("cappass123"),
        join_date=join_date,
        active=True
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    
    # Create balance near cap
    balance = LeaveBalance(
        employee_id=emp.id,
        year=2026,
        cl_balance=Decimal('5.8'),
        sl_balance=Decimal('5.9'),
        pl_balance=Decimal('6.8'),
        rh_used=0
    )
    db.add(balance)
    db.commit()
    
    # Run accrual for February 2026
    response = client.post(
        "/api/v1/accrual/run?month=2026-02",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["credited_count"] >= 1
    assert data["month"] == "2026-02"
    
    # Verify balances are capped
    db.refresh(balance)
    assert float(balance.cl_balance) == 6.0  # Capped at 6.0
    assert float(balance.sl_balance) == 6.0  # Capped at 6.0
    assert float(balance.pl_balance) == 7.0  # Capped at 7.0
    assert balance.last_accrual_month == "2026-02"


def test_accrual_skips_duplicate_month(client, db, hr_employee, employee_joined_feb_10):
    """Test that running accrual twice for same month does not double-credit"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create initial balance
    balance = LeaveBalance(
        employee_id=employee_joined_feb_10.id,
        year=2026,
        cl_balance=Decimal('1.0'),
        sl_balance=Decimal('1.0'),
        pl_balance=Decimal('1.0'),
        rh_used=0
    )
    db.add(balance)
    db.commit()
    
    # Run accrual first time
    response = client.post(
        "/api/v1/accrual/run?month=2026-02",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data1 = response.json()
    initial_credited = data1["credited_count"]
    
    # Get balance after first run
    db.refresh(balance)
    cl_after_first = float(balance.cl_balance)
    
    # Run accrual second time (should skip)
    response = client.post(
        "/api/v1/accrual/run?month=2026-02",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data2 = response.json()
    
    # Should have skipped already credited employees
    assert data2["skipped_already_credited"] >= 1
    
    # Verify balance did not increase
    db.refresh(balance)
    assert float(balance.cl_balance) == cl_after_first


def test_join_date_rule_before_15_gets_credit_same_month(client, db, hr_employee, employee_joined_feb_10):
    """Test that employee joining on/before 15th gets credit for that month"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Employee joined Feb 10 (before 15th) - should be eligible for Feb accrual
    # Run accrual for February
    response = client.post(
        "/api/v1/accrual/run?month=2026-02",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["credited_count"] >= 1
    
    # Verify balance was credited
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_joined_feb_10.id,
        LeaveBalance.year == 2026
    ).first()
    
    assert balance is not None
    assert float(balance.cl_balance) == 0.5
    assert float(balance.sl_balance) == 0.5
    assert float(balance.pl_balance) == 0.5
    assert balance.last_accrual_month == "2026-02"


def test_join_date_rule_after_15_starts_next_month(client, db, hr_employee, employee_joined_feb_20):
    """Test that employee joining after 15th starts accrual from next month"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Employee joined Feb 20 (after 15th) - should NOT be eligible for Feb accrual
    # Run accrual for February
    response = client.post(
        "/api/v1/accrual/run?month=2026-02",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Employee should be skipped (not eligible)
    # Check if balance exists (should not be created yet)
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_joined_feb_20.id,
        LeaveBalance.year == 2026
    ).first()
    
    # Balance might not exist, or if it exists, last_accrual_month should not be set
    if balance:
        assert balance.last_accrual_month != "2026-02"
    
    # Run accrual for March (should be eligible now)
    response = client.post(
        "/api/v1/accrual/run?month=2026-03",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data2 = response.json()
    assert data2["credited_count"] >= 1
    
    # Verify balance was credited in March
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_joined_feb_20.id,
        LeaveBalance.year == 2026
    ).first()
    
    assert balance is not None
    assert float(balance.cl_balance) == 0.5
    assert float(balance.sl_balance) == 0.5
    assert float(balance.pl_balance) == 0.5
    assert balance.last_accrual_month == "2026-03"


def test_inactive_employee_not_credited(client, db, hr_employee, inactive_employee):
    """Test that inactive employees are not credited"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Run accrual
    response = client.post(
        "/api/v1/accrual/run?month=2026-02",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Verify inactive employee was not credited
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == inactive_employee.id,
        LeaveBalance.year == 2026
    ).first()
    
    # Balance should not exist or should not have been credited
    if balance:
        assert balance.last_accrual_month != "2026-02"


def test_accrual_status_endpoint(client, db, hr_employee, employee_joined_feb_10):
    """Test accrual status endpoint"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create balance
    balance = LeaveBalance(
        employee_id=employee_joined_feb_10.id,
        year=2026,
        cl_balance=Decimal('2.0'),
        sl_balance=Decimal('1.5'),
        pl_balance=Decimal('3.0'),
        rh_used=0,
        last_accrual_month="2026-02"
    )
    db.add(balance)
    db.commit()
    
    # Get status
    response = client.get(
        "/api/v1/accrual/status?year=2026",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["year"] == 2026
    assert len(data["employees"]) >= 1
    
    # Find our employee
    emp_status = next((e for e in data["employees"] if e["emp_code"] == "FEB10"), None)
    assert emp_status is not None
    assert emp_status["cl_balance"] == 2.0
    assert emp_status["sl_balance"] == 1.5
    assert emp_status["pl_balance"] == 3.0
    assert emp_status["last_accrual_month"] == "2026-02"
