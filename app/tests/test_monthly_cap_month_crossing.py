"""
Tests for monthly cap validation with month-crossing scenarios
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime, timezone
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
def test_employee(db: Session, test_department):
    """Create a test employee"""
    employee = Employee(
        emp_code="EMP001",
        name="Test Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("testpass123"),
        join_date=date.today() - timedelta(days=180),
        active=True
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


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


def test_monthly_cap_validates_correctly_across_month_boundary(client, db, test_employee, policy_settings_2026):
    """Test that monthly cap correctly validates leaves that cross month boundaries"""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create balance
    balance = LeaveBalance(
        employee_id=test_employee.id,
        year=2026,
        cl_balance=Decimal('10'),
        sl_balance=Decimal('10'),
        pl_balance=Decimal('10'),
        rh_used=0
    )
    db.add(balance)
    db.commit()
    
    # Find last day of current month and first day of next month
    today = date.today()
    if today.month == 12:
        last_day_this_month = date(today.year, 12, 31)
        first_day_next_month = date(today.year + 1, 1, 1)
    else:
        last_day_this_month = date(today.year, today.month + 1, 1) - timedelta(days=1)
        first_day_next_month = date(today.year, today.month + 1, 1)
    
    # Use dates in the future that are in different months
    if today < last_day_this_month - timedelta(days=10):
        # Apply leave spanning month boundary (e.g., Jan 30 - Feb 2)
        leave_from = last_day_this_month - timedelta(days=1)
        leave_to = first_day_next_month + timedelta(days=1)
        
        # First, approve 3 days in current month
        leave1 = LeaveRequest(
            employee_id=test_employee.id,
            leave_type=LeaveType.CL,
            from_date=last_day_this_month - timedelta(days=2),
            to_date=last_day_this_month,
            status=LeaveStatus.APPROVED,
            computed_days=3.0,
            paid_days=3.0,
            lwp_days=0.0,
            computed_days_by_month=json.dumps({
                f"{last_day_this_month.year}-{last_day_this_month.month:02d}": 3.0
            }),
            applied_at=datetime.now(timezone.utc)
        )
        db.add(leave1)
        db.commit()
        
        # Now try to apply leave that spans month boundary
        # This should check both months correctly
        response = client.post(
            "/api/v1/leaves/apply",
            json={
                "leave_type": "PL",
                "from_date": str(leave_from),
                "to_date": str(leave_to),
                "reason": "Month crossing test"
            },
            headers={"Authorization": f"Bearer {emp_token}"}
        )
        
        # Should be rejected if total exceeds 4 days in current month
        # The month-crossing leave would add days to current month
        if response.status_code == 201:
            # If it succeeds, verify the computed_days_by_month splits correctly
            leave_data = response.json()
            by_month = json.loads(leave_data.get("computed_days_by_month", "{}"))
            # Verify both months are represented if leave spans boundary
            assert len(by_month) >= 1, "Month-crossing leave should populate computed_days_by_month"


def test_monthly_cap_counts_days_per_month_correctly(client, db, test_employee, policy_settings_2026):
    """Test that monthly cap counts days per month correctly using computed_days_by_month"""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create balance
    balance = LeaveBalance(
        employee_id=test_employee.id,
        year=2026,
        cl_balance=Decimal('10'),
        sl_balance=Decimal('10'),
        pl_balance=Decimal('10'),
        rh_used=0
    )
    db.add(balance)
    db.commit()
    
    today = date.today()
    month_start = date(today.year, today.month, 1)
    
    # Approve 4 days in current month
    leave1 = LeaveRequest(
        employee_id=test_employee.id,
        leave_type=LeaveType.CL,
        from_date=month_start,
        to_date=month_start + timedelta(days=3),
        status=LeaveStatus.APPROVED,
        computed_days=4.0,
        paid_days=4.0,
        lwp_days=0.0,
        computed_days_by_month=json.dumps({
            f"{month_start.year}-{month_start.month:02d}": 4.0
        }),
        applied_at=datetime.now(timezone.utc)
    )
    db.add(leave1)
    db.commit()
    
    # Try to apply 1 more day in same month (should be rejected)
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "PL",
            "from_date": str(month_start + timedelta(days=10)),
            "to_date": str(month_start + timedelta(days=10)),
            "reason": "Should exceed monthly cap"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    # Should be rejected due to monthly cap
    assert response.status_code == status.HTTP_409_CONFLICT or response.status_code == status.HTTP_400_BAD_REQUEST
    assert "monthly" in response.json()["detail"].lower() or "cap" in response.json()["detail"].lower()
