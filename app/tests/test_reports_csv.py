"""
Tests for reports/CSV export endpoints
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime, timezone
from app.models.department import Department
from app.models.employee import Employee, Role
from app.models.attendance import AttendanceLog
from app.models.leave import LeaveRequest, LeaveType, LeaveStatus
from app.models.audit_log import AuditLog
from app.core.security import hash_password


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


def test_attendance_export_scope(client, db, hr_employee, manager_employee, test_employee, reportee_employee):
    """Test attendance export role-based scoping"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Create attendance records
    today = date.today()
    
    # Attendance for test_employee
    att1 = AttendanceLog(
        employee_id=test_employee.id,
        punch_date=today,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(att1)
    
    # Attendance for reportee_employee
    att2 = AttendanceLog(
        employee_id=reportee_employee.id,
        punch_date=today,
        in_time=datetime.now(timezone.utc),
        in_lat=28.6139,
        in_lng=77.2090,
        out_time=datetime.now(timezone.utc) + timedelta(hours=8),
        out_lat=28.6140,
        out_lng=77.2091,
        source="mobile"
    )
    db.add(att2)
    db.commit()
    
    # HR can export all
    response = client.get(
        f"/api/v1/reports/attendance.csv?from={today}&to={today}",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    csv_content = response.text
    assert "EMP001" in csv_content
    assert "REP001" in csv_content
    
    # Manager can export only reportee
    response = client.get(
        f"/api/v1/reports/attendance.csv?from={today}&to={today}",
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    csv_content = response.text
    assert "REP001" in csv_content
    assert "EMP001" not in csv_content  # Not a reportee
    
    # Employee can export only own
    response = client.get(
        f"/api/v1/reports/attendance.csv?from={today}&to={today}",
        headers={"Authorization": f"Bearer {emp_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    csv_content = response.text
    assert "EMP001" in csv_content
    assert "REP001" not in csv_content


def test_leaves_export_scope_and_overlap_filter(client, db, hr_employee, manager_employee, test_employee, reportee_employee):
    """Test leaves export role scoping and date overlap filtering"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    mgr_token = get_auth_token(client, "MGR001", "mgrpass123")
    rep_token = get_auth_token(client, "REP001", "reppass123")
    
    # Create leave requests
    today = date.today()
    leave_from = today - timedelta(days=5)
    leave_to = today + timedelta(days=5)  # Spans across today
    
    # Leave for reportee
    leave1 = LeaveRequest(
        employee_id=reportee_employee.id,
        leave_type=LeaveType.CL,
        from_date=leave_from,
        to_date=leave_to,
        status=LeaveStatus.APPROVED,
        computed_days=10.0,
        paid_days=10.0,
        lwp_days=0.0,
        applied_at=datetime.now(timezone.utc)
    )
    db.add(leave1)
    
    # Leave for test_employee (not reportee)
    leave2 = LeaveRequest(
        employee_id=test_employee.id,
        leave_type=LeaveType.PL,
        from_date=leave_from,
        to_date=leave_to,
        status=LeaveStatus.APPROVED,
        computed_days=10.0,
        paid_days=10.0,
        lwp_days=0.0,
        applied_at=datetime.now(timezone.utc)
    )
    db.add(leave2)
    db.commit()
    
    # HR can export all (with overlap filter)
    response = client.get(
        f"/api/v1/reports/leaves.csv?from={today}&to={today}",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    csv_content = response.text
    assert "REP001" in csv_content
    assert "EMP001" in csv_content  # Both included due to overlap
    
    # Manager can export only reportee
    response = client.get(
        f"/api/v1/reports/leaves.csv?from={today}&to={today}",
        headers={"Authorization": f"Bearer {mgr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    csv_content = response.text
    assert "REP001" in csv_content
    assert "EMP001" not in csv_content
    
    # Reportee can export only own
    response = client.get(
        f"/api/v1/reports/leaves.csv?from={today}&to={today}",
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    csv_content = response.text
    assert "REP001" in csv_content
    assert "EMP001" not in csv_content


def test_reports_require_auth(client, db):
    """Test that reports endpoints require authentication"""
    today = date.today()
    
    # Attendance export without token
    response = client.get(
        f"/api/v1/reports/attendance.csv?from={today}&to={today}"
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED or response.status_code == status.HTTP_403_FORBIDDEN
    
    # Leaves export without token
    response = client.get(
        f"/api/v1/reports/leaves.csv?from={today}&to={today}"
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED or response.status_code == status.HTTP_403_FORBIDDEN


def test_export_writes_audit_log(client, db, hr_employee):
    """Test that export triggers audit log entry"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    today = date.today()
    
    # Count audit logs before
    count_before = db.query(AuditLog).filter(
        AuditLog.action == "REPORT_EXPORT"
    ).count()
    
    # Export attendance
    response = client.get(
        f"/api/v1/reports/attendance.csv?from={today}&to={today}",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Count audit logs after
    count_after = db.query(AuditLog).filter(
        AuditLog.action == "REPORT_EXPORT"
    ).count()
    
    assert count_after == count_before + 1
    
    # Verify audit log content
    audit_log = db.query(AuditLog).filter(
        AuditLog.action == "REPORT_EXPORT"
    ).order_by(AuditLog.created_at.desc()).first()
    
    assert audit_log is not None
    assert audit_log.actor_id == hr_employee.id
    assert audit_log.entity_type == "report"
    assert audit_log.meta_json["report_type"] == "attendance"
    assert audit_log.meta_json["from_date"] == str(today)
    assert audit_log.meta_json["to_date"] == str(today)


def test_export_filters(client, db, hr_employee, test_employee, reportee_employee):
    """Test export filters (employee_id, department_id, status, leave_type)"""
    hr_token = get_auth_token(client, "HR001", "hrpass123")
    
    today = date.today()
    
    # Create leave with specific status
    leave = LeaveRequest(
        employee_id=test_employee.id,
        leave_type=LeaveType.CL,
        from_date=today,
        to_date=today,
        status=LeaveStatus.PENDING,
        computed_days=1.0,
        paid_days=0.0,
        lwp_days=0.0,
        applied_at=datetime.now(timezone.utc)
    )
    db.add(leave)
    db.commit()
    
    # Filter by status
    response = client.get(
        f"/api/v1/reports/leaves.csv?from={today}&to={today}&status=PENDING",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    csv_content = response.text
    assert "EMP001" in csv_content
    
    # Filter by leave_type
    response = client.get(
        f"/api/v1/reports/leaves.csv?from={today}&to={today}&leave_type=CL",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    csv_content = response.text
    assert "EMP001" in csv_content
    
    # Filter by employee_id
    response = client.get(
        f"/api/v1/reports/leaves.csv?from={today}&to={today}&employee_id={test_employee.id}",
        headers={"Authorization": f"Bearer {hr_token}"}
    )
    assert response.status_code == status.HTTP_200_OK
    csv_content = response.text
    assert "EMP001" in csv_content
