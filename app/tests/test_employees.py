"""
Tests for employee endpoints
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date
from app.models.department import Department
from app.models.employee import Employee, Role
from app.core.security import hash_password


@pytest.fixture
def hr_user(db: Session, test_department):
    """Create an HR user"""
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
def manager_user(db: Session, test_department):
    """Create a manager user"""
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


def get_auth_token(client, emp_code, password):
    """Helper to get auth token"""
    response = client.post(
        "/api/v1/auth/login",
        json={"emp_code": emp_code, "password": password}
    )
    return response.json()["access_token"]


def test_employee_create_requires_department(client, db, hr_user, test_department):
    """Test that creating employee without department_id fails"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Try to create employee without department_id
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "NEW001",
            "name": "New Employee",
            "role": "EMPLOYEE",
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    # Should fail validation (department_id is required)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Create employee with department_id - should succeed
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "NEW001",
            "name": "New Employee",
            "role": "EMPLOYEE",
            "department_id": test_department.id,
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["department_id"] == test_department.id


def test_reporting_hierarchy_no_cycles(client, db, hr_user, test_department):
    """Test that reporting hierarchy cannot have cycles"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create employee A
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "EMP_A",
            "name": "Employee A",
            "role": "EMPLOYEE",
            "department_id": test_department.id,
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    emp_a_id = response.json()["id"]
    
    # Create employee B
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "EMP_B",
            "name": "Employee B",
            "role": "EMPLOYEE",
            "department_id": test_department.id,
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    emp_b_id = response.json()["id"]
    
    # Set A -> B (A reports to B)
    response = client.patch(
        f"/api/v1/employees/{emp_a_id}",
        json={"reporting_manager_id": emp_b_id},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Try to set B -> A (would create cycle) - should fail
    response = client.patch(
        f"/api/v1/employees/{emp_b_id}",
        json={"reporting_manager_id": emp_a_id},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "cycle" in response.json()["detail"].lower()
    
    # Try to set self as manager - should fail
    response = client.patch(
        f"/api/v1/employees/{emp_a_id}",
        json={"reporting_manager_id": emp_a_id},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_employee_emp_code_unique(client, db, hr_user, test_department):
    """Test that employee emp_code must be unique"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create first employee
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "UNIQUE001",
            "name": "First Employee",
            "role": "EMPLOYEE",
            "department_id": test_department.id,
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Try to create duplicate emp_code - should fail
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "UNIQUE001",
            "name": "Second Employee",
            "role": "EMPLOYEE",
            "department_id": test_department.id,
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
