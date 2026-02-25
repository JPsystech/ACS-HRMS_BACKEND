"""
Regression test: Apply -> Approve -> Cancel -> Fetch must show status CANCELLED_BY_COMPANY and cancel_remark.
Ensures cancelled leaves are not reset to PENDING and appear correctly in list APIs.

Manual verification (optional):
  1. Apply leave (Flutter or POST /api/v1/leaves/apply) -> status PENDING.
  2. Approve (Admin: POST /api/v1/leaves/{id}/approve) -> status APPROVED.
  3. Cancel (Admin: POST /api/v1/hr/actions/cancel-leave/{id} body: {"recredit": false, "remarks": "Cancelled"}) -> 200.
  4. GET /api/v1/leaves/my (as employee) -> leave must have status CANCELLED and cancel_remark.
  5. Confirm DB: leave_requests.status = CANCELLED (not PENDING).
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from decimal import Decimal
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus, LeaveBalance
from app.core.security import hash_password


@pytest.fixture
def test_department(db: Session):
    dept = Department(name="IT", active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@pytest.fixture
def hr_employee(db: Session, test_department):
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
def reportee_employee(db: Session, test_department, hr_employee):
    emp = Employee(
        emp_code="REP001",
        name="Reportee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        reporting_manager_id=hr_employee.id,
        password_hash=hash_password("reppass123"),
        join_date=date.today(),
        active=True
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def leave_balance(db: Session, reportee_employee):
    year = date.today().year
    bal = LeaveBalance(
        employee_id=reportee_employee.id,
        year=year,
        cl_balance=Decimal("10"),
        sl_balance=Decimal("10"),
        pl_balance=Decimal("10"),
        rh_used=0,
    )
    db.add(bal)
    db.commit()
    db.refresh(bal)
    return bal


def get_token(client, emp_code: str, password: str) -> str:
    r = client.post("/api/v1/auth/login", json={"emp_code": emp_code, "password": password})
    assert r.status_code == status.HTTP_200_OK
    return r.json()["access_token"]


def test_apply_approve_cancel_then_fetch_shows_cancelled(
    client, db: Session, hr_employee, reportee_employee, leave_balance
):
    """
    Apply leave -> Approve -> Cancel with remark -> GET /leaves/my must return
    the leave with status CANCELLED and cancel_remark present (never PENDING).
    DB must NOT have status PENDING after cancel.
    """
    rep_token = get_token(client, "REP001", "reppass123")
    hr_token = get_token(client, "HR001", "hrpass123")

    today = date.today()
    day1 = today + timedelta(days=14)
    day2 = today + timedelta(days=14)

    # 1) Employee applies leave -> PENDING
    apply_r = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "CL",
            "from_date": day1.isoformat(),
            "to_date": day2.isoformat(),
            "reason": "Personal",
        },
        headers={"Authorization": f"Bearer {rep_token}"},
    )
    assert apply_r.status_code == status.HTTP_201_CREATED
    data = apply_r.json()
    leave_id = data["id"]
    assert data["status"] == "PENDING"

    # 2) HR approves -> APPROVED
    approve_r = client.post(
        f"/api/v1/leaves/{leave_id}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert approve_r.status_code == status.HTTP_200_OK
    assert approve_r.json()["status"] == "APPROVED"

    # 3) HR cancels with remark
    cancel_r = client.post(
        f"/api/v1/hr/actions/cancel-leave/{leave_id}",
        json={"recredit": False, "remarks": "Cancelled for test"},
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert cancel_r.status_code == status.HTTP_200_OK

    # 4) Fetch leave list as employee (GET /leaves/my) -> must show CANCELLED_BY_COMPANY and cancel_remark
    my_r = client.get(
        "/api/v1/leaves/my",
        headers={"Authorization": f"Bearer {rep_token}"},
    )
    assert my_r.status_code == status.HTTP_200_OK
    items = my_r.json()["items"]
    leave_item = next((x for x in items if x["id"] == leave_id), None)
    assert leave_item is not None, "Cancelled leave must appear in /leaves/my"
    assert leave_item["status"] == "CANCELLED", (
        f"Expected status CANCELLED after cancel (never PENDING), got {leave_item['status']}"
    )
    assert leave_item.get("cancelled_remark") == "Cancelled for test"
    assert leave_item.get("cancel_remark") == "Cancelled for test", "cancel_remark alias for Flutter"
    assert leave_item.get("reason") == "Personal", "Employee reason must not be overwritten"

    # 5) DB record must still be CANCELLED_BY_COMPANY (not PENDING)
    leave_db = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    assert leave_db is not None
    assert leave_db.status == LeaveStatus.CANCELLED, (
        f"DB status must be CANCELLED (never PENDING), got {leave_db.status}"
    )
    assert leave_db.cancelled_remark == "Cancelled for test"
    assert leave_db.reason == "Personal"
