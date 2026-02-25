import pytest
from fastapi import status
from sqlalchemy.orm import Session
from datetime import date, timedelta
from app.models.department import Department
from app.models.employee import Employee, Role
from app.core.security import hash_password
from app.models.birthday_greeting import BirthdayGreeting


@pytest.fixture
def dept(db: Session):
    d = Department(name="CultureDept", active=True)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@pytest.fixture
def user_today(db: Session, dept):
    e = Employee(
        emp_code="EMPBD1",
        name="Birthday Today",
        role=Role.EMPLOYEE,
        department_id=dept.id,
        password_hash=hash_password("pass1234"),
        join_date=date.today(),
        active=True,
        dob=date.today(),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@pytest.fixture
def user_upcoming(db: Session, dept):
    upcoming = date.today() + timedelta(days=3)
    e = Employee(
        emp_code="EMPBD2",
        name="Birthday Upcoming",
        role=Role.EMPLOYEE,
        department_id=dept.id,
        password_hash=hash_password("pass1234"),
        join_date=date.today(),
        active=True,
        dob=upcoming,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def get_token(client, emp_code, password):
    r = client.post("/api/v1/auth/login", json={"emp_code": emp_code, "password": password})
    return r.json()["access_token"]


def test_birthdays_today(client, db, user_today):
    token = get_token(client, "EMPBD1", "pass1234")
    r = client.get("/api/v1/culture/birthdays/today", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["total"] >= 1
    item = next(i for i in data["items"] if i["employee_id"] == user_today.id)
    assert item["wish_status"] in ["Pending", "Sent"]
    assert item["birthday_date"] == date.today().isoformat()


def test_birthdays_upcoming(client, db, user_upcoming):
    token = get_token(client, "EMPBD2", "pass1234")
    r = client.get("/api/v1/culture/birthdays/upcoming?days=7", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert any(i["employee_id"] == user_upcoming.id for i in data["items"])


def test_generate_greeting_idempotent(client, db, user_today):
    token = get_token(client, "EMPBD1", "pass1234")
    r1 = client.post(
        f"/api/v1/culture/birthday/{user_today.id}/generate-greeting",
        json={"message": "Have a great day!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == status.HTTP_200_OK
    d1 = r1.json()
    assert "greeting_image_url" in d1
    r2 = client.post(
        f"/api/v1/culture/birthday/{user_today.id}/generate-greeting",
        json={"message": "Have a great day!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    d2 = r2.json()
    assert d2["greeting_image_url"] == d1["greeting_image_url"]


def test_send_wish_sets_fields(client, db, user_today):
    token = get_token(client, "EMPBD1", "pass1234")
    r = client.post(
        f"/api/v1/culture/birthday/{user_today.id}/send-wish",
        json={"wish_message": "Wish you a happy birthday!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == status.HTTP_200_OK
    rec = db.query(BirthdayGreeting).filter(BirthdayGreeting.employee_id == user_today.id).first()
    assert rec is not None
    assert rec.wish_sent_at is not None
    assert rec.wish_sent_by == user_today.id
    assert rec.wish_message is not None
