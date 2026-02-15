"""
Tests for policy validations (probation, notice, monthly cap, HR override)
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus, LeaveBalance
from app.models.policy import PolicySetting
from app.core.security import hash_password
from decimal import Decimal
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
def probation_employee(db: Session, test_department):
    """Create an employee in probation (joined 1 month ago)"""
    join_date = date.today() - timedelta(days=30)  # 1 month ago
    employee = Employee(
        emp_code="PROB001",
        name="Probation Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("probpass123"),
        join_date=join_date,
        active=True
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@pytest.fixture
def regular_employee(db: Session, test_department):
    """Create an employee past probation (joined 4 months ago)"""
    join_date = date.today() - timedelta(days=120)  # 4 months ago
    employee = Employee(
        emp_code="REG001",
        name="Regular Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("regpass123"),
        join_date=join_date,
        active=True
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@pytest.fixture
def manager_employee(db: Session, test_department):
    """Create a manager employee"""
    join_date = date.today() - timedelta(days=180)  # 6 months ago
    manager = Employee(
        emp_code="MGR001",
        name="Manager",
        role=Role.MANAGER,
        department_id=test_department.id,
        password_hash=hash_password("mgrpass123"),
        join_date=join_date,
        active=True
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)
    return manager


@pytest.fixture
def hr_employee(db: Session, test_department):
    """Create an HR employee"""
    join_date = date.today() - timedelta(days=180)  # 6 months ago
    hr = Employee(
        emp_code="HR001",
        name="HR Admin",
        role=Role.HR,
        department_id=test_department.id,
        password_hash=hash_password("hrpass123"),
        join_date=join_date,
        active=True
    )
    db.add(hr)
    db.commit()
    db.refresh(hr)
    return hr


@pytest.fixture
def reportee_employee(db: Session, test_department, manager_employee):
    """Create an employee reporting to manager"""
    join_date = date.today() - timedelta(days=180)  # 6 months ago
    emp = Employee(
        emp_code="REP001",
        name="Reportee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        reporting_manager_id=manager_employee.id,
        password_hash=hash_password("reppass123"),
        join_date=join_date,
        active=True
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def policy_settings_2026(db: Session):
    """Create policy settings for 2026"""
    policy = PolicySetting(
        year=2026,
        probation_months=3,
        cl_pl_notice_days=3,
        cl_pl_monthly_cap=Decimal('4.0'),
        weekly_off_day=7,
        sandwich_enabled=True,
        sandwich_include_weekly_off=True,
        sandwich_include_holidays=True,
        sandwich_include_rh=False,
        allow_hr_override=True
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def get_auth_token(client, emp_code, password):
    """Helper to get auth token"""
    response = client.post(
        "/api/v1/auth/login",
        json={"emp_code": emp_code, "password": password}
    )
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code} - {response.json()}")
    return response.json()["access_token"]


def test_probation_blocks_cl_pl(client, db, probation_employee, policy_settings_2026):
    """Test that probation blocks CL and PL but allows SL"""
    token = get_auth_token(client, "PROB001", "probpass123")
    
    today = date.today()
    future_date = today + timedelta(days=10)
    
    # Try to apply CL (should be rejected)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(future_date),
            "to_date": str(future_date),
            "reason": "Test CL"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "probation" in response.json()["detail"].lower()
    
    # Try to apply PL (should be rejected)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "PL",
            "from_date": str(future_date),
            "to_date": str(future_date),
            "reason": "Test PL"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "probation" in response.json()["detail"].lower()
    
    # Try to apply SL (should be allowed)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "SL",
            "from_date": str(future_date),
            "to_date": str(future_date),
            "reason": "Test SL"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED


def test_notice_rule_blocks_short_notice(client, db, regular_employee, policy_settings_2026):
    """Test that notice rule blocks short notice CL/PL"""
    token = get_auth_token(client, "REG001", "regpass123")
    
    today = date.today()
    
    # Try to apply CL with 2 days notice (should be rejected, need 3)
    short_notice_date = today + timedelta(days=2)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(short_notice_date),
            "to_date": str(short_notice_date),
            "reason": "Test short notice"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "notice" in response.json()["detail"].lower() or "days" in response.json()["detail"].lower()
    
    # Try to apply CL with 3 days notice (should be allowed)
    valid_notice_date = today + timedelta(days=3)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(valid_notice_date),
            "to_date": str(valid_notice_date),
            "reason": "Test valid notice"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED


def test_monthly_cap_blocks_over_4(client, db, hr_employee, manager_employee, reportee_employee, policy_settings_2026):
    """Test that monthly cap blocks when total approved CL+PL+RH exceeds 4 days per month"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Create leave balance
    balance = LeaveBalance(
        employee_id=reportee_employee.id,
        year=2026,
        pl_balance=Decimal('10.0'),
        cl_balance=Decimal('10.0'),
        sl_balance=Decimal('10.0'),
        rh_used=0
    )
    db.add(balance)
    db.commit()
    
    # Use a specific month (e.g., March 2026)
    test_month = date(2026, 3, 15)
    
    # Create and approve 4 days of CL+PL in the same month
    # Day 1: CL
    leave1 = LeaveRequest(
        employee_id=reportee_employee.id,
        leave_type=LeaveType.CL,
        from_date=test_month,
        to_date=test_month,
        status=LeaveStatus.APPROVED,
        computed_days=Decimal('1.0'),
        computed_days_by_month=json.dumps({"2026-03": 1.0}),
        paid_days=Decimal('1.0'),
        lwp_days=Decimal('0')
    )
    db.add(leave1)
    
    # Days 2-4: PL (3 days)
    leave2 = LeaveRequest(
        employee_id=reportee_employee.id,
        leave_type=LeaveType.PL,
        from_date=test_month + timedelta(days=1),
        to_date=test_month + timedelta(days=3),
        status=LeaveStatus.APPROVED,
        computed_days=Decimal('3.0'),
        computed_days_by_month=json.dumps({"2026-03": 3.0}),
        paid_days=Decimal('3.0'),
        lwp_days=Decimal('0')
    )
    db.add(leave2)
    db.commit()
    
    # Try to apply another PL (1 day) in the same month (should be rejected - total would be 5)
    future_date = test_month + timedelta(days=10)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "PL",
            "from_date": str(future_date),
            "to_date": str(future_date),
            "reason": "Test monthly cap"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "cap" in response.json()["detail"].lower() or "monthly" in response.json()["detail"].lower()


def test_monthly_cap_counts_rh_as_pl(client, db, hr_employee, manager_employee, reportee_employee, policy_settings_2026):
    """Test that monthly cap counts RH as PL"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Create leave balance
    balance = LeaveBalance(
        employee_id=reportee_employee.id,
        year=2026,
        pl_balance=Decimal('10.0'),
        cl_balance=Decimal('10.0'),
        sl_balance=Decimal('10.0'),
        rh_used=0
    )
    db.add(balance)
    db.commit()
    
    # Create RH date
    rh_date = date(2026, 4, 15)
    from app.models.holiday import RestrictedHoliday
    rh = RestrictedHoliday(
        year=2026,
        date=rh_date,
        name="Test RH",
        active=True
    )
    db.add(rh)
    db.commit()
    
    # Apply and approve RH (1 day)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "RH",
            "from_date": str(rh_date),
            "to_date": str(rh_date),
            "reason": "Test RH"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    leave_id1 = response.json()["id"]
    
    # Approve RH
    response = client.post(
        f"/api/v1/leaves/{leave_id1}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Apply and approve PL 3 days in same month (total 4)
    pl_start = date(2026, 4, 20)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "PL",
            "from_date": str(pl_start),
            "to_date": str(pl_start + timedelta(days=2)),
            "reason": "Test PL"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    leave_id2 = response.json()["id"]
    
    # Approve PL
    response = client.post(
        f"/api/v1/leaves/{leave_id2}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Try to apply CL 1 day in same month (should be rejected - total would be 5: 1 RH + 3 PL + 1 CL)
    cl_date = date(2026, 4, 25)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(cl_date),
            "to_date": str(cl_date),
            "reason": "Test monthly cap with RH"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "cap" in response.json()["detail"].lower() or "monthly" in response.json()["detail"].lower()


def test_hr_override_allows_blocked_case_with_remark(client, db, hr_employee, probation_employee, policy_settings_2026):
    """Test that HR override allows blocked cases with remark"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    prob_token = get_auth_token(client, "PROB001", "probpass123")
    
    today = date.today()
    future_date = today + timedelta(days=10)
    
    # Probation employee tries to apply CL without override (should fail)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(future_date),
            "to_date": str(future_date),
            "reason": "Test CL"
        },
        headers={"Authorization": f"Bearer {prob_token}"}
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    
    # Probation employee tries to apply CL with override (should fail - not HR)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(future_date),
            "to_date": str(future_date),
            "reason": "Test CL",
            "override_policy": True,
            "override_remark": "HR override"
        },
        headers={"Authorization": f"Bearer {prob_token}"}
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "HR" in response.json()["detail"] or "override" in response.json()["detail"].lower()
    
    # HR applies leave for probation employee with override (should succeed)
    # Note: HR can apply for others, but the API currently only allows self-apply
    # For this test, we'll test HR applying for themselves with override
    # Create HR in probation
    hr_prob = Employee(
        emp_code="HRPROB001",
        name="HR Probation",
        role=Role.HR,
        department_id=probation_employee.department_id,
        password_hash=hash_password("hrprob123"),
        join_date=date.today() - timedelta(days=30),  # In probation
        active=True
    )
    db.add(hr_prob)
    db.commit()
    db.refresh(hr_prob)
    
    hr_prob_token = get_auth_token(client, "HRPROB001", "hrprob123")
    
    # HR applies CL with override (should succeed)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(future_date),
            "to_date": str(future_date),
            "reason": "Test CL with override",
            "override_policy": True,
            "override_remark": "HR override for probation employee"
        },
        headers={"Authorization": f"Bearer {hr_prob_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["override_policy"] is True
    assert data["override_remark"] == "HR override for probation employee"
    
    # Verify override_remark is required when override_policy is True
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": str(future_date + timedelta(days=1)),
            "to_date": str(future_date + timedelta(days=1)),
            "reason": "Test CL without remark",
            "override_policy": True,
            "override_remark": None
        },
        headers={"Authorization": f"Bearer {hr_prob_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "remark" in response.json()["detail"].lower()
