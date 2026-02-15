"""
Tests for sandwich rule in leave day calculation
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.holiday import Holiday
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus
from app.core.security import hash_password
import json


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


def get_auth_token(client, emp_code, password):
    """Helper to get auth token"""
    response = client.post(
        "/api/v1/auth/login",
        json={"emp_code": emp_code, "password": password}
    )
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code} - {response.json()}")
    return response.json()["access_token"]


def test_sandwich_counts_sunday_between_two_leave_days(client, db, hr_employee, test_employee):
    """Test that sandwich rule counts Sunday between two leave days"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Find a Saturday and Monday (with Sunday in between)
    today = date.today()
    # Find next Saturday
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and today.weekday() != 5:
        days_until_saturday = 7
    saturday = today + timedelta(days=days_until_saturday)
    sunday = saturday + timedelta(days=1)
    monday = saturday + timedelta(days=2)
    
    # Apply leave from Saturday to Monday (CL - sandwich applies)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(saturday),
            "to_date": str(monday),
            "reason": "Test sandwich"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # Should count 3 days: Saturday + Sunday (sandwich) + Monday
    assert float(data["computed_days"]) == 3.0
    
    # Verify computed_days_by_month is populated
    assert data["computed_days_by_month"] is not None
    by_month = json.loads(data["computed_days_by_month"])
    
    # Should have correct month key
    month_key = f"{saturday.year}-{saturday.month:02d}"
    assert month_key in by_month
    assert float(by_month[month_key]) == 3.0


def test_no_sandwich_when_single_side_only(client, db, test_employee):
    """Test that sandwich does not apply when there's only one side"""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Single day leave (Monday)
    today = date.today()
    days_until_monday = (0 - today.weekday()) % 7
    if days_until_monday == 0 and today.weekday() != 0:
        days_until_monday = 7
    monday = today + timedelta(days=days_until_monday)
    
    # Apply single day leave
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(monday),
            "to_date": str(monday),
            "reason": "Single day"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # Should count only 1 day (no sandwich for single day)
    assert float(data["computed_days"]) == 1.0


def test_sandwich_counts_holiday_between_leave_days(client, db, hr_employee, test_employee):
    """Test that sandwich rule counts holiday between two leave days"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Find dates: Monday, Tuesday (holiday), Wednesday
    today = date.today()
    days_until_monday = (0 - today.weekday()) % 7
    if days_until_monday == 0 and today.weekday() != 0:
        days_until_monday = 7
    monday = today + timedelta(days=days_until_monday)
    tuesday = monday + timedelta(days=1)
    wednesday = monday + timedelta(days=2)
    
    # Create a holiday on Tuesday
    client.post(
        "/api/v1/holidays",
        json={
            "year": tuesday.year,
            "date": str(tuesday),
            "name": "Test Holiday",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Apply leave from Monday to Wednesday (CL - sandwich applies)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(monday),
            "to_date": str(wednesday),
            "reason": "Test holiday sandwich"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # Should count 3 days: Monday + Tuesday (holiday, sandwich) + Wednesday
    assert float(data["computed_days"]) == 3.0
    
    # Verify by_month
    by_month = json.loads(data["computed_days_by_month"])
    month_key = f"{monday.year}-{monday.month:02d}"
    assert float(by_month[month_key]) == 3.0


def test_sandwich_not_applied_to_rh(client, db, hr_employee, test_employee):
    """Test that sandwich rule does NOT apply to RH"""
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
    
    # Apply RH (single day - sandwich doesn't apply anyway, but verify)
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
    
    # RH should count only 1 day (no sandwich)
    assert float(data["computed_days"]) == 1.0


def test_sandwich_not_applied_to_lwp(client, db, test_employee):
    """Test that sandwich rule does NOT apply to LWP"""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Find Saturday and Monday
    today = date.today()
    days_until_saturday = (5 - today.weekday()) % 7
    if days_until_saturday == 0 and today.weekday() != 5:
        days_until_saturday = 7
    saturday = today + timedelta(days=days_until_saturday)
    monday = saturday + timedelta(days=2)
    
    # Apply LWP from Saturday to Monday
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "LWP",
            "from_date": str(saturday),
            "to_date": str(monday),
            "reason": "Test LWP no sandwich"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # LWP should count only 2 days (Saturday + Monday), NOT including Sunday
    assert float(data["computed_days"]) == 2.0


def test_by_month_split_across_month_boundary(client, db, hr_employee, test_employee):
    """Test that computed_days_by_month splits correctly across month boundary"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Use last day of a month and first day of next month
    # Find last day of current month
    today = date.today()
    if today.month == 12:
        last_day = date(today.year, 12, 31)
        first_day_next = date(today.year + 1, 1, 1)
    else:
        # Get last day of current month
        if today.month == 2:
            # Check for leap year
            if today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0):
                last_day = date(today.year, 2, 29)
            else:
                last_day = date(today.year, 2, 28)
        elif today.month in [4, 6, 9, 11]:
            last_day = date(today.year, today.month, 30)
        else:
            last_day = date(today.year, today.month, 31)
        first_day_next = date(today.year, today.month + 1, 1)
    
    # Ensure dates are in the future
    if last_day <= today:
        # Move to next month
        if today.month == 12:
            last_day = date(today.year + 1, 1, 31)
            first_day_next = date(today.year + 1, 2, 1)
        else:
            if today.month + 1 == 2:
                if today.year % 4 == 0 and (today.year % 100 != 0 or today.year % 400 == 0):
                    last_day = date(today.year, 2, 29)
                else:
                    last_day = date(today.year, 2, 28)
            elif today.month + 1 in [4, 6, 9, 11]:
                last_day = date(today.year, today.month + 1, 30)
            else:
                last_day = date(today.year, today.month + 1, 31)
            first_day_next = date(today.year, today.month + 2, 1)
    
    # Apply leave spanning month boundary (CL - sandwich applies)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(last_day),
            "to_date": str(first_day_next),
            "reason": "Test month boundary"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # Verify computed_days_by_month splits across months
    by_month = json.loads(data["computed_days_by_month"])
    
    month_key1 = f"{last_day.year}-{last_day.month:02d}"
    month_key2 = f"{first_day_next.year}-{first_day_next.month:02d}"
    
    # Should have entries for both months
    assert month_key1 in by_month
    assert month_key2 in by_month
    
    # Sum should equal total computed_days
    total_from_by_month = sum(float(v) for v in by_month.values())
    assert abs(total_from_by_month - float(data["computed_days"])) < 0.01
