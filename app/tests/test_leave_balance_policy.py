"""
Tests for ACS leave policy and balance: new employee gets PL/CL/SL/RH balances.
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.leave import LeaveType
from app.core.security import hash_password
from app.services.policy_validator import get_or_create_policy_settings
from app.services import leave_wallet_service as wallet


def get_auth_token(client, emp_code: str, password: str) -> str:
    r = client.post("/api/v1/auth/login", json={"emp_code": emp_code, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def dept(db: Session):
    d = Department(name="IT", active=True)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@pytest.fixture
def policy_2026(db: Session):
    """Ensure ACS policy exists for 2026 (PL=7, SL=6, CL=5, RH=1)."""
    return get_or_create_policy_settings(db, 2026)


@pytest.fixture
def new_employee_full_year(db: Session, dept, policy_2026):
    """Employee joined in 2025 so in 2026 they get full year entitlement."""
    emp = Employee(
        emp_code="NEW001",
        name="New Employee",
        role=Role.EMPLOYEE,
        department_id=dept.id,
        password_hash=hash_password("pass123"),
        join_date=date(2025, 1, 1),
        active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


def test_new_employee_has_leave_balances_after_create(db: Session, new_employee_full_year, policy_2026):
    """Creating an employee and ensuring wallet gives PL/CL/SL/RH balances for the year."""
    year = 2026
    wallet.ensure_wallet_for_employee(db, new_employee_full_year.id, year)
    balances = wallet.get_wallet_balances(db, new_employee_full_year.id, year)
    types = {b.leave_type for b in balances}
    assert types >= {LeaveType.PL, LeaveType.CL, LeaveType.SL, LeaveType.RH}
    by_type = {b.leave_type: b for b in balances}
    assert float(by_type[LeaveType.PL].remaining) <= 7
    assert float(by_type[LeaveType.CL].remaining) <= 5
    assert float(by_type[LeaveType.SL].remaining) <= 6
    assert float(by_type[LeaveType.RH].remaining) <= 1


def test_balance_me_returns_entitled_used_available(client, db: Session, dept, policy_2026, new_employee_full_year):
    """GET /leaves/balance/me returns year and {PL, CL, SL, RH} with entitled, used, available."""
    token = get_auth_token(client, "NEW001", "pass123")
    r = client.get(
        "/api/v1/leaves/balance/me",
        params={"year": 2026},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["year"] == 2026
    assert data["employee_id"] == new_employee_full_year.id
    balances = data.get("balances") or {}
    for key in ("PL", "CL", "SL", "RH"):
        assert key in balances, f"balances should contain {key}"
        b = balances[key]
        assert "entitled" in b
        assert "used" in b
        assert "available" in b
        assert b["used"] >= 0
        assert b["available"] >= 0


def test_public_summary_returns_acs_entitlements(client, db: Session, policy_2026):
    """GET /policy/{year}/public-summary returns PL=7, SL=6, CL=5, RH=1, public_holidays=14."""
    r = client.get("/api/v1/policy/2026/public-summary")
    assert r.status_code == 200
    data = r.json()
    assert data["year"] == 2026
    assert data["PL"] == 7
    assert data["CL"] == 5
    assert data["SL"] == 6
    assert data["RH"] == 1
    assert data["public_holidays"] == 14
