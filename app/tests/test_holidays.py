"""
Tests for holiday calendar endpoints
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.holiday import Holiday, RestrictedHoliday
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


def test_create_holiday_success(client, db, hr_employee):
    """Test creating a holiday (HR-only)"""
    token = get_auth_token(client, "HR001", "hrpass123")
    
    response = client.post(
        "/api/v1/holidays",
        json={
            "year": 2026,
            "date": "2026-01-26",
            "name": "Republic Day",
            "active": True
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["year"] == 2026
    assert data["date"] == "2026-01-26"
    assert data["name"] == "Republic Day"
    assert data["active"] is True


def test_create_holiday_duplicate_rejected(client, db, hr_employee):
    """Test that duplicate holidays are rejected"""
    token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create first holiday
    response = client.post(
        "/api/v1/holidays",
        json={
            "year": 2026,
            "date": "2026-01-26",
            "name": "Republic Day",
            "active": True
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Try to create duplicate
    response = client.post(
        "/api/v1/holidays",
        json={
            "year": 2026,
            "date": "2026-01-26",
            "name": "Another Name",
            "active": True
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in response.json()["detail"].lower()


def test_list_holidays_by_year(client, db, hr_employee):
    """Test listing holidays filtered by year"""
    token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create holidays for different years
    client.post(
        "/api/v1/holidays",
        json={
            "year": 2026,
            "date": "2026-01-26",
            "name": "Republic Day 2026",
            "active": True
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    client.post(
        "/api/v1/holidays",
        json={
            "year": 2027,
            "date": "2027-01-26",
            "name": "Republic Day 2027",
            "active": True
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # List holidays for 2026 only
    response = client.get(
        "/api/v1/holidays?year=2026",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["year"] == 2026


def test_create_rh_success(client, db, hr_employee):
    """Test creating a restricted holiday (HR-only)"""
    token = get_auth_token(client, "HR001", "hrpass123")
    
    response = client.post(
        "/api/v1/restricted-holidays",
        json={
            "year": 2026,
            "date": "2026-10-02",
            "name": "Gandhi Jayanti (RH)",
            "active": True
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["year"] == 2026
    assert data["date"] == "2026-10-02"
    assert data["name"] == "Gandhi Jayanti (RH)"
    assert data["active"] is True


def test_public_calendar_endpoints(client, db, hr_employee, test_department):
    """Test public calendar endpoints (any authenticated user)"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create a holiday
    client.post(
        "/api/v1/holidays",
        json={
            "year": 2026,
            "date": "2026-01-26",
            "name": "Republic Day",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Create an employee (non-HR)
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
    
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Employee should be able to read holidays
    response = client.get(
        "/api/v1/calendars/holidays?year=2026&active_only=true",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Republic Day"
