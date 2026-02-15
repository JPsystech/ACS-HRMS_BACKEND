"""
Tests for manager-department assignment endpoints
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
def dept1(db: Session):
    """Create department 1"""
    dept = Department(name="Dept1", active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@pytest.fixture
def dept2(db: Session):
    """Create department 2"""
    dept = Department(name="Dept2", active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def get_auth_token(client, emp_code, password):
    """Helper to get auth token"""
    response = client.post(
        "/api/v1/auth/login",
        json={"emp_code": emp_code, "password": password}
    )
    return response.json()["access_token"]


def test_manager_department_assign_only_for_manager_role(
    client, db, hr_user, test_department, dept1, dept2
):
    """Test that only MANAGER role can be assigned departments"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create a MANAGER
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "MGR001",
            "name": "Manager",
            "role": "MANAGER",
            "department_id": test_department.id,
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    manager_id = response.json()["id"]
    
    # Create an EMPLOYEE
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "EMP001",
            "name": "Employee",
            "role": "EMPLOYEE",
            "department_id": test_department.id,
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    employee_id = response.json()["id"]
    
    # Assign departments to MANAGER - should succeed
    response = client.post(
        f"/api/v1/managers/{manager_id}/departments",
        json={"department_ids": [dept1.id, dept2.id]},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.json()) == 2
    
    # Try to assign departments to EMPLOYEE - should fail
    response = client.post(
        f"/api/v1/managers/{employee_id}/departments",
        json={"department_ids": [dept1.id]},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "MANAGER" in response.json()["detail"]


def test_manager_department_list_and_remove(client, db, hr_user, test_department, dept1, dept2):
    """Test listing and removing manager-department assignments"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    # Create a MANAGER
    response = client.post(
        "/api/v1/employees",
        json={
            "emp_code": "MGR002",
            "name": "Manager 2",
            "role": "MANAGER",
            "department_id": test_department.id,
            "join_date": str(date.today()),
            "password": "password123"
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    manager_id = response.json()["id"]
    
    # Assign departments
    response = client.post(
        f"/api/v1/managers/{manager_id}/departments",
        json={"department_ids": [dept1.id, dept2.id]},
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    
    # List assignments
    response = client.get(
        f"/api/v1/managers/{manager_id}/departments",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assignments = response.json()
    assert len(assignments) == 2
    
    # Remove one assignment
    response = client.delete(
        f"/api/v1/managers/{manager_id}/departments/{dept1.id}",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Verify it's removed
    response = client.get(
        f"/api/v1/managers/{manager_id}/departments",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert len(response.json()) == 1
    assert response.json()[0]["department_id"] == dept2.id
