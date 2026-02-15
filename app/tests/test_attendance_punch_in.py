"""
Tests for attendance punch-in endpoints
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date
from app.models.department import Department
from app.models.employee import Employee, Role
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


def get_auth_token(client, emp_code, password):
    """Helper to get auth token"""
    response = client.post(
        "/api/v1/auth/login",
        json={"emp_code": emp_code, "password": password}
    )
    return response.json()["access_token"]


def test_punch_in_success(client, db, test_employee):
    """Test successful punch-in returns session (SessionDto) with work_date, punch_in_at, punch_in_geo."""
    token = get_auth_token(client, "EMP001", "testpass123")
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={
            "lat": 28.6139,
            "lng": 77.2090,
            "source": "MOBILE"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "id" in data
    assert data["employee_id"] == test_employee.id
    assert "work_date" in data
    assert "punch_in_at" in data
    assert data["punch_in_source"] == "MOBILE"
    assert data["punch_out_at"] is None
    assert data["status"] == "OPEN"
    # Live GPS stored in punch_in_geo
    assert data.get("punch_in_geo") is not None
    assert data["punch_in_geo"]["lat"] == 28.6139
    assert data["punch_in_geo"]["lng"] == 77.2090
    assert data["punch_in_geo"].get("source") == "MOBILE"


def test_punch_in_duplicate_same_day_rejected(client, db, test_employee):
    """Test that duplicate punch-in on same day returns 400."""
    token = get_auth_token(client, "EMP001", "testpass123")
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6139, "lng": 77.2090, "source": "WEB"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6140, "lng": 77.2091, "source": "WEB"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already punched in" in response.json()["detail"].lower()


def test_punch_in_requires_auth(client, db, test_employee):
    """Test that punch-in requires authentication."""
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6139, "lng": 77.2090, "source": "WEB"}
    )
    assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]


def test_punch_in_with_invalid_token(client, db, test_employee):
    """Test that punch-in with invalid token is rejected."""
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6139, "lng": 77.2090, "source": "WEB"},
        headers={"Authorization": "Bearer invalid_token_here"}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_punch_in_with_live_gps_stores_geo_and_device(client, db, test_employee):
    """Punch-in with lat, lng, accuracy, address, device_id, source; response has punch_in_geo and punch_in_device_id."""
    token = get_auth_token(client, "EMP001", "testpass123")
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={
            "lat": 12.34,
            "lng": 56.78,
            "accuracy": 10.5,
            "address": "Office Tower, Floor 2",
            "device_id": "device-abc-123",
            "source": "MOBILE",
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["punch_in_device_id"] == "device-abc-123"
    geo = data.get("punch_in_geo")
    assert geo is not None
    assert geo["lat"] == 12.34
    assert geo["lng"] == 56.78
    assert geo["accuracy"] == 10.5
    assert geo["address"] == "Office Tower, Floor 2"
    assert geo["source"] == "MOBILE"


def test_punch_in_validation_lat_lng_accuracy(client, db, test_employee):
    """Invalid lat/lng/accuracy return 422 (validation error)."""
    token = get_auth_token(client, "EMP001", "testpass123")
    # lat > 90 -> validation error
    r = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 91, "lng": 0, "source": "WEB"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 422
    # accuracy <= 0 -> validation error
    r = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6, "lng": 77.2, "accuracy": 0, "source": "WEB"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 422


def test_punch_in_all_roles_can_punch_in(client, db, test_department):
    """Test that EMPLOYEE, MANAGER, and HR can all punch-in"""
    # Create users of different roles
    employee = Employee(
        emp_code="EMP002",
        name="Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("pass123"),
        join_date=date.today(),
        active=True
    )
    manager = Employee(
        emp_code="MGR001",
        name="Manager",
        role=Role.MANAGER,
        department_id=test_department.id,
        password_hash=hash_password("pass123"),
        join_date=date.today(),
        active=True
    )
    hr = Employee(
        emp_code="HR001",
        name="HR",
        role=Role.HR,
        department_id=test_department.id,
        password_hash=hash_password("pass123"),
        join_date=date.today(),
        active=True
    )
    db.add_all([employee, manager, hr])
    db.commit()
    
    # Test EMPLOYEE can punch-in
    token = get_auth_token(client, "EMP002", "pass123")
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6139, "lng": 77.2090},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Test MANAGER can punch-in
    token = get_auth_token(client, "MGR001", "pass123")
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6139, "lng": 77.2090},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Test HR can punch-in
    token = get_auth_token(client, "HR001", "pass123")
    response = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6139, "lng": 77.2090},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
