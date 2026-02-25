"""
Tests for department endpoints
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


@pytest.fixture
def employee_user(db: Session, test_department):
    """Create an employee user"""
    emp = Employee(
        emp_code="EMP001",
        name="Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("emppass123"),
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


def test_department_crud_hr_only(client, db, hr_user, manager_user, employee_user, test_department):
    """Test that only HR can create/list/update departments"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    manager_token = get_auth_token(client, "MGR001", "mgrpass123")
    emp_token = get_auth_token(client, "EMP001", "emppass123")
    
    # HR can create department
    response = client.post(
        "/api/v1/departments",
        json={"name": "Engineering", "active": True},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    dept_data = response.json()
    assert dept_data["name"] == "Engineering"
    dept_id = dept_data["id"]
    
    # HR can list departments
    response = client.get(
        "/api/v1/departments",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) >= 1
    
    # HR can update department
    response = client.patch(
        f"/api/v1/departments/{dept_id}",
        json={"name": "Engineering Updated"},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "Engineering Updated"
    
    # Manager cannot create department
    response = client.post(
        "/api/v1/departments",
        json={"name": "Sales", "active": True},
        headers={"Authorization": f"Bearer {manager_token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    
    # Employee cannot create department
    response = client.post(
        "/api/v1/departments",
        json={"name": "Marketing", "active": True},
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_department_name_unique(client, db, hr_user, test_department):
    """Test that department names must be unique"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create first department
    response = client.post(
        "/api/v1/departments",
        json={"name": "UniqueDept", "active": True},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # Try to create duplicate (case-insensitive should fail)
    response = client.post(
        "/api/v1/departments",
        json={"name": "uniquedept", "active": True},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
