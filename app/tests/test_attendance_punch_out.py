"""
Tests for attendance punch-out endpoints
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


def test_punch_out_success(client, db, test_employee):
    """Test successful punch-out after punch-in; response has punch_out_at and punch_out_geo."""
    token = get_auth_token(client, "EMP001", "testpass123")
    client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6139, "lng": 77.2090, "source": "MOBILE"},
        headers={"Authorization": f"Bearer {token}"}
    )
    response = client.post(
        "/api/v1/attendance/punch-out",
        json={"lat": 28.6140, "lng": 77.2091, "source": "MOBILE"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["punch_out_at"] is not None
    assert data["employee_id"] == test_employee.id
    assert data["status"] == "CLOSED"
    assert data.get("punch_out_geo") is not None
    assert data["punch_out_geo"]["lat"] == 28.6140
    assert data["punch_out_geo"]["lng"] == 77.2091


def test_punch_out_without_punch_in_rejected(client, db, test_employee):
    """Test that punch-out without punch-in returns 400."""
    token = get_auth_token(client, "EMP001", "testpass123")
    response = client.post(
        "/api/v1/attendance/punch-out",
        json={"lat": 28.6139, "lng": 77.2090, "source": "WEB"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "no active session" in response.json()["detail"].lower()


def test_double_punch_out_rejected(client, db, test_employee):
    """Test that double punch-out returns 400."""
    token = get_auth_token(client, "EMP001", "testpass123")
    client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.6139, "lng": 77.2090, "source": "WEB"},
        headers={"Authorization": f"Bearer {token}"}
    )
    client.post(
        "/api/v1/attendance/punch-out",
        json={"lat": 28.6140, "lng": 77.2091, "source": "WEB"},
        headers={"Authorization": f"Bearer {token}"}
    )
    response = client.post(
        "/api/v1/attendance/punch-out",
        json={"lat": 28.6141, "lng": 77.2092, "source": "WEB"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    detail = response.json()["detail"].lower()
    assert "already punched out" in detail or "no active session" in detail
