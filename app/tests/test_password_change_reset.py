import pytest
from fastapi import status
from datetime import date
from sqlalchemy.orm import Session
from app.models.department import Department
from app.models.employee import Employee, Role
from app.core.security import hash_password


@pytest.fixture
def dept(db: Session):
    d = Department(name="IT", active=True)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@pytest.fixture
def emp(db: Session, dept):
    e = Employee(
        emp_code="E001",
        name="Emp One",
        role=Role.EMPLOYEE,
        department_id=dept.id,
        password_hash=hash_password("OldPass@123"),
        join_date=date.today(),
        active=True,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@pytest.fixture
def admin(db: Session, dept):
    a = Employee(
        emp_code="ADM001",
        name="Admin",
        role=Role.ADMIN,
        department_id=dept.id,
        password_hash=hash_password("Admin@123"),
        join_date=date.today(),
        active=True,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def login(client, emp_code, password):
    r = client.post("/api/v1/auth/login", json={"emp_code": emp_code, "password": password})
    return r


def test_change_password_success(client, emp):
    r = login(client, "E001", "OldPass@123")
    assert r.status_code == status.HTTP_200_OK
    token = r.json()["access_token"]

    # Change password
    r2 = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "OldPass@123", "new_password": "NewPass@123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == status.HTTP_200_OK
    assert "success" in r2.json()["message"].lower()

    # Old password should fail
    r3 = login(client, "E001", "OldPass@123")
    assert r3.status_code == status.HTTP_401_UNAUTHORIZED

    # New password should work
    r4 = login(client, "E001", "NewPass@123")
    assert r4.status_code == status.HTTP_200_OK
    assert r4.json().get("must_change_password") is False


def test_admin_reset_password_generate_random(client, db: Session, emp, admin):
    # Login as admin
    r_admin = login(client, "ADM001", "Admin@123")
    assert r_admin.status_code == status.HTTP_200_OK
    admin_token = r_admin.json()["access_token"]

    # Reset employee password with generate_random
    r_reset = client.post(
        f"/api/v1/admin/users/{emp.id}/reset-password",
        json={"generate_random": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_reset.status_code == status.HTTP_200_OK
    data = r_reset.json()
    assert "temp_password" in data
    temp_password = data["temp_password"]
    assert isinstance(temp_password, str) and len(temp_password) >= 8

    # Login with old should fail
    r_old = login(client, "E001", "OldPass@123")
    assert r_old.status_code == status.HTTP_401_UNAUTHORIZED

    # Login with temp should work and must_change_password flag should be true
    r_temp = login(client, "E001", temp_password)
    assert r_temp.status_code == status.HTTP_200_OK
    assert r_temp.json().get("must_change_password") is True

    # Now change password to finalize
    token_emp = r_temp.json()["access_token"]
    r_change = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": temp_password, "new_password": "FinalPass@123"},
        headers={"Authorization": f"Bearer {token_emp}"},
    )
    assert r_change.status_code == status.HTTP_200_OK

    # Login again with final password should work and flag false
    r_final = login(client, "E001", "FinalPass@123")
    assert r_final.status_code == status.HTTP_200_OK
    assert r_final.json().get("must_change_password") is False
