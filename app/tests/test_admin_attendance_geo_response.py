"""
Test that admin attendance endpoints return punch_in_geo, punch_out_geo, ip, device_id, source.
Punch-in with geo -> stored in DB -> GET admin/today returns location metadata.
Punch-out with geo -> stored -> admin/today returns punch_out_geo and metadata.
Backward compat: sessions with null geo return null; UI shows "No location".
"""
import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date

from app.models.department import Department
from app.models.employee import Employee, Role
from app.core.security import hash_password


@pytest.fixture
def test_department(db: Session):
    dept = Department(name="IT", active=True)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@pytest.fixture
def test_employee(db: Session, test_department):
    emp = Employee(
        emp_code="EMP001",
        name="Test Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("testpass123"),
        join_date=date.today(),
        active=True,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return emp


@pytest.fixture
def test_hr(db: Session, test_department):
    hr = Employee(
        emp_code="HR001",
        name="HR User",
        role=Role.HR,
        department_id=test_department.id,
        password_hash=hash_password("hrpass123"),
        join_date=date.today(),
        active=True,
    )
    db.add(hr)
    db.commit()
    db.refresh(hr)
    return hr


def get_auth_token(client, emp_code: str, password: str):
    r = client.post("/api/v1/auth/login", json={"emp_code": emp_code, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_punch_in_with_geo_then_admin_today_returns_geo(client, db, test_employee, test_hr):
    """Punch-in with geo/device/source -> GET admin/attendance/today includes punch_in_geo, punch_in_ip, punch_in_device_id, punch_in_source."""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    hr_token = get_auth_token(client, "HR001", "hrpass123")

    # Punch-in with full metadata
    punch_in_body = {
        "lat": 28.6139,
        "lng": 77.209,
        "accuracy": 12.5,
        "address": "Office Tower, Floor 2",
        "device_id": "device-flutter-001",
        "source": "MOBILE",
    }
    r = client.post(
        "/api/v1/attendance/punch-in",
        json=punch_in_body,
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    assert data.get("punch_in_geo") is not None
    assert data["punch_in_geo"]["lat"] == 28.6139
    assert data["punch_in_geo"]["lng"] == 77.209
    assert data["punch_in_geo"].get("accuracy") == 12.5
    assert data["punch_in_geo"].get("address") == "Office Tower, Floor 2"
    assert data.get("punch_in_device_id") == "device-flutter-001"
    assert data.get("punch_in_source") == "MOBILE"

    # Admin today must return the same session with location fields
    r_today = client.get(
        "/api/v1/admin/attendance/today",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert r_today.status_code == 200
    sessions = r_today.json()
    assert isinstance(sessions, list)
    assert len(sessions) >= 1
    session = next((s for s in sessions if s["employee_id"] == test_employee.id), None)
    assert session is not None
    assert session.get("punch_in_geo") is not None
    assert session["punch_in_geo"]["lat"] == 28.6139
    assert session["punch_in_geo"]["lng"] == 77.209
    assert session["punch_in_geo"].get("address") == "Office Tower, Floor 2"
    assert session.get("punch_in_device_id") == "device-flutter-001"
    assert session.get("punch_in_source") == "MOBILE"
    # IP may be set from request client in test
    assert "punch_in_ip" in session
    assert "punch_out_geo" in session
    assert session["punch_out_geo"] is None  # not punched out yet


def test_punch_out_with_geo_then_admin_returns_punch_out_geo(client, db, test_employee, test_hr):
    """Punch-in then punch-out with geo -> admin/today returns punch_out_geo and punch_out_* metadata."""
    emp_token = get_auth_token(client, "EMP001", "testpass123")
    hr_token = get_auth_token(client, "HR001", "hrpass123")

    # Punch-in
    r_in = client.post(
        "/api/v1/attendance/punch-in",
        json={"lat": 28.61, "lng": 77.20, "source": "MOBILE", "device_id": "dev-1"},
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert r_in.status_code == status.HTTP_201_CREATED

    # Punch-out with geo
    r_out = client.post(
        "/api/v1/attendance/punch-out",
        json={
            "lat": 28.615,
            "lng": 77.21,
            "accuracy": 10,
            "address": "Exit Gate",
            "device_id": "dev-1",
            "source": "MOBILE",
        },
        headers={"Authorization": f"Bearer {emp_token}"},
    )
    assert r_out.status_code == status.HTTP_200_OK
    out_data = r_out.json()
    assert out_data.get("punch_out_geo") is not None
    assert out_data["punch_out_geo"]["lat"] == 28.615
    assert out_data["punch_out_geo"]["lng"] == 77.21
    assert out_data.get("punch_out_device_id") == "dev-1"
    assert out_data.get("punch_out_source") == "MOBILE"

    # Admin today returns session with punch_out_geo and metadata
    r_today = client.get(
        "/api/v1/admin/attendance/today",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert r_today.status_code == 200
    sessions = r_today.json()
    session = next((s for s in sessions if s["employee_id"] == test_employee.id), None)
    assert session is not None
    assert session.get("punch_out_geo") is not None
    assert session["punch_out_geo"]["lat"] == 28.615
    assert session["punch_out_geo"]["lng"] == 77.21
    assert session.get("punch_out_device_id") == "dev-1"
    assert session.get("punch_out_source") == "MOBILE"
    assert "punch_out_ip" in session


def test_punch_in_accepts_geo_and_deviceId_keys(client, db, test_employee):
    """Client can send geo (dict) and deviceId; they are persisted and returned."""
    token = get_auth_token(client, "EMP001", "testpass123")
    r = client.post(
        "/api/v1/attendance/punch-in",
        json={
            "geo": {"lat": 12.5, "lng": 77.2, "accuracy": 15, "address": "Site A"},
            "deviceId": "flutter-device-xyz",
            "source": "MOBILE",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    assert data.get("punch_in_geo") is not None
    assert data["punch_in_geo"]["lat"] == 12.5
    assert data["punch_in_geo"]["lng"] == 77.2
    assert data["punch_in_geo"].get("address") == "Site A"
    assert data.get("punch_in_device_id") == "flutter-device-xyz"


def test_admin_today_null_geo_returns_null(client, db, test_department, test_hr):
    """Backward compat: session created without geo has null punch_in_geo/punch_out_geo; admin still returns all fields."""
    from datetime import datetime, timezone

    from app.models.attendance_session import AttendanceSession, SessionStatus
    from app.services.attendance_session_service import get_work_date

    work_date = get_work_date()
    emp_old = Employee(
        emp_code="EMPOLD",
        name="Old Employee",
        role=Role.EMPLOYEE,
        department_id=test_department.id,
        password_hash=hash_password("old123"),
        join_date=date.today(),
        active=True,
    )
    db.add(emp_old)
    db.commit()
    db.refresh(emp_old)

    session = AttendanceSession(
        employee_id=emp_old.id,
        work_date=work_date,
        punch_in_at=datetime.now(timezone.utc),
        punch_out_at=None,
        status=SessionStatus.OPEN,
        punch_in_source="WEB",
        punch_out_source=None,
        punch_in_ip=None,
        punch_out_ip=None,
        punch_in_device_id=None,
        punch_out_device_id=None,
        punch_in_geo=None,
        punch_out_geo=None,
        remarks=None,
    )
    db.add(session)
    db.commit()

    hr_token = get_auth_token(client, "HR001", "hrpass123")
    r = client.get("/api/v1/admin/attendance/today", headers={"Authorization": f"Bearer {hr_token}"})
    assert r.status_code == 200
    sessions = r.json()
    admin_session = next((s for s in sessions if s["employee_id"] == emp_old.id), None)
    assert admin_session is not None
    assert admin_session.get("punch_in_geo") is None
    assert admin_session.get("punch_out_geo") is None
    assert admin_session.get("punch_in_source") == "WEB"
    assert "punch_in_ip" in admin_session
    assert "punch_in_device_id" in admin_session


def test_attendance_tz_check_returns_utc_and_ist(client):
    """GET /api/v1/attendance/tz-check returns now_utc (Z), now_ist (+05:30), and conversion_confirmed."""
    r = client.get("/api/v1/attendance/tz-check")
    assert r.status_code == 200
    data = r.json()
    assert "now_utc" in data
    assert "now_ist" in data
    assert data.get("conversion_confirmed") is True
    now_utc = data["now_utc"]
    now_ist = data["now_ist"]
    assert now_utc.endswith("Z") or "+00:00" in now_utc, f"now_utc should be UTC, got {now_utc!r}"
    assert "+05:30" in now_ist and not now_ist.endswith("Z"), f"now_ist should be IST (+05:30), got {now_ist!r}"


def test_attendance_session_response_includes_ist(client, db, test_employee):
    """Punch-in response returns punch_in_at and other datetimes in IST (+05:30), never Z."""
    token = get_auth_token(client, "EMP001", "testpass123")
    r = client.post(
        "/api/v1/attendance/punch-in",
        json={"source": "WEB"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == status.HTTP_201_CREATED
    data = r.json()
    punch_in_at = data.get("punch_in_at")
    assert punch_in_at, "punch_in_at must be present"
    assert "+05:30" in punch_in_at and not punch_in_at.endswith("Z"), (
        f"punch_in_at must be IST (+05:30), got {punch_in_at!r}"
    )
    for field in ("created_at", "updated_at"):
        val = data.get(field)
        if val:
            assert "+05:30" in val and not val.endswith("Z"), f"{field} must be IST (+05:30), got {val!r}"
