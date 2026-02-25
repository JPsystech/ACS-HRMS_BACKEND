"""
Tests for comp-off module
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime, timezone
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.attendance import AttendanceLog
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus, LeaveBalance
from app.models.compoff import CompoffRequest, CompoffLedger, CompoffRequestStatus, CompoffLedgerType
from app.models.holiday import Holiday
from app.core.security import hash_password
from decimal import Decimal


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
def manager_employee(db: Session, test_department):
    """Create a manager employee"""
    manager = Employee(
        emp_code="MGR001",
        name="Manager",
        role=Role.MANAGER,
        department_id=test_department.id,
        password_hash=hash_password("mgrpass123"),
        join_date=date.today() - timedelta(days=180),
        active=True
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)
    return manager


@pytest.fixture
def hr_employee(db: Session, test_department):
    """Create an HR employee"""
    hr = Employee(
        emp_code="HR001",
        name="HR Admin",
        role=Role.HR,
        department_id=test_department.id,
        password_hash=hash_password("hrpass123"),
        join_date=date.today() - timedelta(days=180),
        active=True
    )
    db.add(hr)
    db.commit()
    db.refresh(hr)
    return hr


@pytest.fixture
def reportee_employee(db: Session, test_department, manager_employee):
    """Create an employee reporting to manager"""
    emp = Employee(
        emp_code="REP001",
        name="Reportee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        reporting_manager_id=manager_employee.id,
        password_hash=hash_password("reppass123"),
        join_date=date.today() - timedelta(days=180),
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
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code} - {response.json()}")
    return response.json()["access_token"]


def test_compoff_earn_requires_attendance_and_sunday_or_holiday(client, db, hr_employee, test_employee):
    """Test that comp-off earn requires attendance on Sunday or holiday"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Find next Sunday
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0 and today.weekday() != 6:
        days_until_sunday = 7
    sunday = today + timedelta(days=days_until_sunday)
    
    # Create attendance on Sunday (both in and out)
    attendance = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=sunday,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance)
    db.commit()
    
    # Request comp-off for Sunday (should succeed)
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(sunday),
            "reason": "Worked on Sunday"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["worked_date"] == str(sunday)
    
    # Try to request comp-off for normal weekday (should fail)
    monday = sunday + timedelta(days=1)
    attendance2 = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=monday,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance2)
    db.commit()
    
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(monday),
            "reason": "Worked on Monday"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "sunday" in response.json()["detail"].lower() or "holiday" in response.json()["detail"].lower()


def test_compoff_earn_requires_holiday_with_attendance(client, db, hr_employee, test_employee):
    """Test that comp-off can be earned on holiday with attendance"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create a holiday on a weekday
    today = date.today()
    holiday_date = today + timedelta(days=5)
    
    # Create holiday
    client.post(
        "/api/v1/holidays",
        json={
            "year": holiday_date.year,
            "date": str(holiday_date),
            "name": "Test Holiday",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Create attendance on holiday
    attendance = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=holiday_date,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance)
    db.commit()
    
    # Request comp-off for holiday (should succeed)
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(holiday_date),
            "reason": "Worked on holiday"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "PENDING"


def test_compoff_approval_creates_credit_with_expiry(client, db, manager_employee, reportee_employee):
    """Test that comp-off approval creates credit with expiry"""
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Find next Sunday
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0 and today.weekday() != 6:
        days_until_sunday = 7
    sunday = today + timedelta(days=days_until_sunday)
    
    # Create attendance
    attendance = AttendanceLog(
        employee_id=reportee_employee.id,
        punch_date=sunday,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance)
    db.commit()
    
    # Request comp-off
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(sunday),
            "reason": "Worked on Sunday"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    request_id = response.json()["id"]
    
    # Approve by direct manager
    response = client.post(
        f"/api/v1/compoff/{request_id}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "APPROVED"
    
    # Verify ledger CREDIT entry created
    ledger_entry = db.query(CompoffLedger).filter(
        CompoffLedger.employee_id == reportee_employee.id,
        CompoffLedger.entry_type == CompoffLedgerType.CREDIT
    ).first()
    
    assert ledger_entry is not None
    assert float(ledger_entry.days) == 1.0
    assert ledger_entry.worked_date == sunday
    assert ledger_entry.expires_on == sunday + timedelta(days=60)
    assert ledger_entry.reference_id == request_id


def test_compoff_balance_excludes_expired(client, db, test_employee):
    """Test that comp-off balance excludes expired credits"""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create expired credit (60+ days ago)
    expired_date = date.today() - timedelta(days=70)
    expired_credit = CompoffLedger(
        employee_id=test_employee.id,
        entry_type=CompoffLedgerType.CREDIT,
        days=Decimal('1.0'),
        worked_date=expired_date,
        expires_on=expired_date + timedelta(days=60)  # Already expired
    )
    db.add(expired_credit)
    
    # Create valid credit
    valid_date = date.today() - timedelta(days=10)
    valid_credit = CompoffLedger(
        employee_id=test_employee.id,
        entry_type=CompoffLedgerType.CREDIT,
        days=Decimal('1.0'),
        worked_date=valid_date,
        expires_on=valid_date + timedelta(days=60)  # Still valid
    )
    db.add(valid_credit)
    db.commit()
    
    # Get balance
    response = client.get(
        "/api/v1/compoff/balance",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # Should have 1.0 available (only valid credit counted)
    assert data["available_days"] == 1.0
    assert data["credits"] == 1.0
    assert data["expired_credits"] == 1.0


def test_compoff_leave_approval_deducts_ledger(client, db, hr_employee, manager_employee, reportee_employee):
    """Test that COMPOFF leave approval deducts from ledger"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Create comp-off credit
    worked_date = date.today() - timedelta(days=10)
    credit = CompoffLedger(
        employee_id=reportee_employee.id,
        entry_type=CompoffLedgerType.CREDIT,
        days=Decimal('1.0'),
        worked_date=worked_date,
        expires_on=worked_date + timedelta(days=60)
    )
    db.add(credit)
    db.commit()
    
    # Apply COMPOFF leave for 2 days
    today = date.today()
    leave_from = today + timedelta(days=5)
    leave_to = leave_from + timedelta(days=1)  # 2 days
    
    response = client.post(
        "/api/v1/leaves/apply",
        json={
            "leave_type": "COMPOFF",
            "from_date": str(leave_from),
            "to_date": str(leave_to),
            "reason": "Use comp-off"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    leave_id = response.json()["id"]
    
    # Approve leave
    response = client.post(
        f"/api/v1/leaves/{leave_id}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "APPROVED"
    # Should have paid_days=1, lwp_days=1 (1 day from comp-off, 1 day LWP)
    assert float(data["paid_days"]) == 1.0
    assert float(data["lwp_days"]) == 1.0
    
    # Verify ledger DEBIT entry created
    debit_entry = db.query(CompoffLedger).filter(
        CompoffLedger.employee_id == reportee_employee.id,
        CompoffLedger.entry_type == CompoffLedgerType.DEBIT,
        CompoffLedger.leave_request_id == leave_id
    ).first()
    
    assert debit_entry is not None
    assert float(debit_entry.days) == 1.0
    
    # Verify balance is now 0
    response = client.get(
        "/api/v1/compoff/balance",
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    balance_data = response.json()
    assert balance_data["available_days"] == 0.0
    assert balance_data["credits"] == 1.0
    assert balance_data["debits"] == 1.0


def test_compoff_approval_authority(client, db, manager_employee, test_employee, reportee_employee):
    """Test comp-off approval authority"""
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Find next Sunday
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0 and today.weekday() != 6:
        days_until_sunday = 7
    sunday = today + timedelta(days=days_until_sunday)
    
    # Create attendance for reportee
    attendance = AttendanceLog(
        employee_id=reportee_employee.id,
        punch_date=sunday,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance)
    
    # Create attendance for non-reportee
    attendance2 = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=sunday,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance2)
    db.commit()
    
    # Reportee requests comp-off
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(sunday),
            "reason": "Worked on Sunday"
        },
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    reportee_request_id = response.json()["id"]
    
    # Non-reportee requests comp-off
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(sunday),
            "reason": "Worked on Sunday"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert response.status_code == status.HTTP_201_CREATED
    non_reportee_request_id = response.json()["id"]
    
    # Manager can approve reportee's request
    response = client.post(
        f"/api/v1/compoff/{reportee_request_id}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Manager cannot approve non-reportee's request
    response = client.post(
        f"/api/v1/compoff/{non_reportee_request_id}/approve",
        json={"remarks": "Approved"},
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_compoff_validation_specific_error_messages(client, db, test_employee):
    """Test comp-off validation provides specific error messages for different scenarios"""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Find next Sunday
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0 and today.weekday() != 6:
        days_until_sunday = 7
    sunday = today + timedelta(days=days_until_sunday)
    
    # Test 1: Sunday with punch_in only → rejected with punch-out message
    attendance_punch_in_only = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=sunday,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=None,  # Missing punch-out
        out_lat=None,
        out_lng=None,
        source="mobile"
    )
    db.add(attendance_punch_in_only)
    db.commit()
    
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(sunday),
            "reason": "Worked on Sunday - punch out missing"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "punch-out required" in response.json()["detail"].lower()
    
    # Test 2: Sunday with punch_in+punch_out → accepted
    attendance_complete = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=sunday,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance_complete)
    db.commit()
    
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(sunday),
            "reason": "Worked on Sunday - complete attendance"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    
    # Test 3: Working day with attendance → rejected (not Sunday/holiday)
    monday = sunday + timedelta(days=1)
    attendance_weekday = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=monday,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance_weekday)
    db.commit()
    
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(monday),
            "reason": "Worked on Monday"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "sunday" in response.json()["detail"].lower() or "holiday" in response.json()["detail"].lower()
    
    # Test 4: No attendance found → rejected with specific message
    tuesday = monday + timedelta(days=1)
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(tuesday),
            "reason": "No attendance"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "no attendance found" in response.json()["detail"].lower()


def test_compoff_validation_holiday_scenario(client, db, hr_employee, test_employee):
    """Test comp-off validation for holiday scenario with complete attendance"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    
    # Create a holiday on a weekday
    today = date.today()
    holiday_date = today + timedelta(days=5)
    
    # Create holiday
    client.post(
        "/api/v1/holidays",
        json={
            "year": holiday_date.year,
            "date": str(holiday_date),
            "name": "Test Holiday",
            "active": True
        },
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    
    # Create complete attendance on holiday
    attendance_holiday = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=holiday_date,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(attendance_holiday)
    db.commit()
    
    # Request comp-off for holiday (should succeed)
    response = client.post(
        "/api/v1/compoff/request",
        json={
            "worked_date": str(holiday_date),
            "reason": "Worked on holiday"
        },
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["worked_date"] == str(holiday_date)
