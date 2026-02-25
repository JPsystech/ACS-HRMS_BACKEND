"""
Tests for 2026 final leave policy:
- Jan–Oct month credit: PL +0.5, CL +0.5, SL +0.5
- Nov–Dec month credit: PL +0.5, FL +0.5, SL +0.5 (no CL in Nov–Dec)
- PL/FL eligibility: allowed only after 6 months from join_date
- No advance leave: requested_days <= available; 0.5 increments only
"""
from datetime import date
from decimal import Decimal
import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.leave import LeaveType, LeaveRequest, LeaveStatus
from app.core.security import hash_password
from app.services import leave_wallet_service as wallet
from app.services.policy_validator import get_or_create_policy_settings
from app.services.leave_service import apply_leave


@pytest.fixture
def dept(db: Session):
    d = Department(name="IT", active=True)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@pytest.fixture
def employee_jan_join(db: Session, dept):
    """Employee joined at start of year for clean monthly accrual checks."""
    e = Employee(
        emp_code="JAN01",
        name="Jan Joiner",
        role=Role.EMPLOYEE,
        department_id=dept.id,
        password_hash=hash_password("pass123"),
        join_date=date(2026, 1, 1),
        active=True,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def test_november_accrual_fl_not_cl(db: Session, employee_jan_join):
    """As of November end, FL accrues 0.5 and CL does not accrue for Nov."""
    year = 2026
    # Ensure wallet as of Nov 30
    wallet.ensure_wallet_for_employee(db, employee_jan_join.id, year, as_of_date=date(2026, 11, 30))
    balances = wallet.get_wallet_balances(db, employee_jan_join.id, year)
    by_type = {b.leave_type: b for b in balances}
    # CL should have capped at 5 (Jan–Oct 10*0.5)
    assert float(by_type[LeaveType.CL].accrued) == pytest.approx(5.0)
    # FL should have 0.5 (Nov only)
    assert float(by_type[LeaveType.FL].accrued) == pytest.approx(0.5)
    # PL/SL accrue every month (11 * 0.5 = 5.5) capped by entitlements (PL=6, SL=6)
    assert float(by_type[LeaveType.PL].accrued) == pytest.approx(5.5, rel=1e-3)
    assert float(by_type[LeaveType.SL].accrued) == pytest.approx(5.5, rel=1e-3)


def test_total_monthly_credit_is_1_5(db: Session, employee_jan_join):
    """Each month credit sum should be 1.5 days across types."""
    year = 2026
    # End of Jan: PL 0.5 + CL 0.5 + SL 0.5 = 1.5
    acc_jan = wallet.compute_accrual(db, employee_jan_join, year, as_of_date=date(2026, 1, 31))
    total_jan = acc_jan[LeaveType.PL]["accrued"] + acc_jan[LeaveType.CL]["accrued"] + acc_jan[LeaveType.SL]["accrued"]
    assert total_jan == pytest.approx(1.5)
    # End of Nov: Increment from Oct end should be PL 0.5 + SL 0.5 + FL 0.5
    acc_oct = wallet.compute_accrual(db, employee_jan_join, year, as_of_date=date(2026, 10, 31))
    acc_nov = wallet.compute_accrual(db, employee_jan_join, year, as_of_date=date(2026, 11, 30))
    delta_pl = acc_nov[LeaveType.PL]["accrued"] - acc_oct[LeaveType.PL]["accrued"]
    delta_sl = acc_nov[LeaveType.SL]["accrued"] - acc_oct[LeaveType.SL]["accrued"]
    delta_cl = acc_nov[LeaveType.CL]["accrued"] - acc_oct[LeaveType.CL]["accrued"]
    delta_fl = acc_nov[LeaveType.FL]["accrued"] - acc_oct[LeaveType.FL]["accrued"]
    assert delta_pl == pytest.approx(0.5)
    assert delta_sl == pytest.approx(0.5)
    assert delta_cl == pytest.approx(0.0)
    assert delta_fl == pytest.approx(0.5)
    assert (delta_pl + delta_sl + delta_cl + delta_fl) == pytest.approx(1.5)


def test_pl_fl_eligibility_block_and_allow(db: Session, dept):
    """Join March 10, 2026: block PL/FL before 6 months; allow PL after 6 months if available."""
    e = Employee(
        emp_code="MAR10",
        name="March Joiner",
        role=Role.EMPLOYEE,
        department_id=dept.id,
        password_hash=hash_password("pass123"),
        join_date=date(2026, 3, 10),
        active=True,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    year = 2026
    # Ensure wallet up to June
    wallet.ensure_wallet_for_employee(db, e.id, year, as_of_date=date(2026, 6, 30))
    # Block PL before eligibility (June 15)
    with pytest.raises(Exception):
        apply_leave(
            db=db,
            employee_id=e.id,
            leave_type=LeaveType.PL,
            from_date=date(2026, 6, 15),
            to_date=date(2026, 6, 15),
            reason="Test"
        )
    # After eligibility (>= Sep 10), PL allowed if balance exists
    wallet.ensure_wallet_for_employee(db, e.id, year, as_of_date=date(2026, 9, 30))
    leave = apply_leave(
        db=db,
        employee_id=e.id,
        leave_type=LeaveType.PL,
        from_date=date(2026, 9, 15),
        to_date=date(2026, 9, 15),
        reason="Eligible now"
    )
    assert isinstance(leave, LeaveRequest)
    assert leave.status == LeaveStatus.PENDING
