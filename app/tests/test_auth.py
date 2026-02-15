"""
Tests for authentication endpoints
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


@pytest.fixture
def test_hr_employee(db: Session, test_department):
    """Create a test HR employee"""
    employee = Employee(
        emp_code="HR001",
        name="Test HR",
        role=Role.HR,
        department_id=test_department.id,
        password_hash=hash_password("hrpass123"),
        join_date=date.today(),
        active=True
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@pytest.fixture
def inactive_employee(db: Session, test_department):
    """Create an inactive test employee"""
    employee = Employee(
        emp_code="INACTIVE001",
        name="Inactive Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("testpass123"),
        join_date=date.today(),
        active=False
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


def test_auth_login_success(client, test_employee):
    """Test successful login returns 200 and access_token"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "emp_code": "EMP001",
            "password": "testpass123"
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0


def test_auth_login_wrong_password(client, test_employee):
    """Test login with wrong password returns 401"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "emp_code": "EMP001",
            "password": "wrongpassword"
        }
    )
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    data = response.json()
    assert "detail" in data


def test_auth_login_invalid_emp_code(client):
    """Test login with invalid emp_code returns 401"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "emp_code": "INVALID001",
            "password": "testpass123"
        }
    )
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_auth_inactive_user_blocked(client, inactive_employee):
    """Test inactive user cannot login - returns 403"""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "emp_code": "INACTIVE001",
            "password": "testpass123"
        }
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert "inactive" in data["detail"].lower()


def test_role_guard_blocks_unauthorized_access(client, test_employee):
    """Test that role guard blocks unauthorized access"""
    # First login to get token
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "emp_code": "EMP001",
            "password": "testpass123"
        }
    )
    token = login_response.json()["access_token"]
    
    # Verify token contains employee role
    from app.core.security import decode_token
    from app.models.employee import Role
    
    payload = decode_token(token)
    assert payload["role"] == "EMPLOYEE"
    
    # Test the guard by creating a test endpoint
    from fastapi import Depends
    from app.core.deps import require_roles
    from app.main import app
    
    # Add a test endpoint to the app for testing
    @app.get("/test/hr-only", include_in_schema=False)
    async def test_hr_endpoint(user: Employee = Depends(require_roles(Role.HR))):
        return {"message": "HR only"}
    
    # Try to access HR-only endpoint with EMPLOYEE token - should be blocked
    response = client.get(
        "/test/hr-only",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should be blocked with 403
    assert response.status_code == status.HTTP_403_FORBIDDEN
    
    # Clean up - remove the test endpoint
    # Note: FastAPI routes is a property, so we need to remove from the router
    # The endpoint will be cleaned up when the test finishes anyway


def test_role_guard_allows_authorized_access(client, test_hr_employee):
    """Test that role guard allows authorized access"""
    # Login as HR
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "emp_code": "HR001",
            "password": "hrpass123"
        }
    )
    token = login_response.json()["access_token"]
    
    # Verify token contains HR role
    from fastapi import Depends
    from app.core.security import decode_token
    from app.models.employee import Role
    from app.core.deps import require_roles
    from app.main import app
    
    payload = decode_token(token)
    assert payload["role"] == "HR"
    assert payload.get("emp_code") == "HR001"
    # sub is now a string in JWT (per JWT spec)
    assert int(payload.get("sub")) == test_hr_employee.id
    
    # Add a test endpoint to the app for testing
    @app.get("/test/hr-only-2", include_in_schema=False)
    async def test_hr_endpoint_2(user: Employee = Depends(require_roles(Role.HR))):
        return {"message": "HR only"}
    
    # Access HR-only endpoint with HR token - should be allowed
    response = client.get(
        "/test/hr-only-2",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should be allowed with 200
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "HR only"
    
    # Clean up - remove the test endpoint
    # Note: FastAPI routes is a property, so we need to remove from the router
    # The endpoint will be cleaned up when the test finishes anyway
