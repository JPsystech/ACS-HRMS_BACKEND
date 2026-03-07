import logging
from datetime import date, datetime
from typing import Dict, List, Tuple, Set
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.employee import Employee
from app.models.attendance_session import AttendanceSession
from app.models.notification_device import NotificationDevice
from app.models.notification_reminder import NotificationReminder, ReminderType, DeliveryStatus
from app.models.holiday import Holiday
from app.models.leave import LeaveRequest, LeaveStatus
from app.services.push_service import send_push_to_tokens
from app.utils.datetime_utils import now_utc

_log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _today_ist() -> date:
    return now_utc().astimezone(IST).date()


def _is_public_holiday(db: Session, d: date) -> bool:
    return db.query(Holiday).filter(Holiday.date == d, Holiday.active.is_(True)).first() is not None


def _employees_on_approved_leave(db: Session, d: date) -> Set[int]:
    rows = (
        db.query(LeaveRequest.employee_id)
        .filter(
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.from_date <= d,
            LeaveRequest.to_date >= d,
        )
        .all()
    )
    return {r[0] for r in rows}


def _active_employees(db: Session) -> List[Employee]:
    return db.query(Employee).filter(Employee.active.is_(True)).all()


def _users_with_active_tokens(db: Session, user_ids: Set[int]) -> Dict[int, List[str]]:
    rows = (
        db.query(NotificationDevice.user_id, NotificationDevice.fcm_token)
        .filter(
            NotificationDevice.user_id.in_(user_ids),
            NotificationDevice.is_active.is_(True),
        )
        .all()
    )
    out: Dict[int, List[str]] = {}
    for uid, tok in rows:
        out.setdefault(uid, []).append(tok)
    return out


def _already_sent(db: Session, uid: int, d: date, rtype: ReminderType) -> bool:
    exists = (
        db.query(NotificationReminder.id)
        .filter(
            NotificationReminder.user_id == uid,
            NotificationReminder.reminder_date == d,
            NotificationReminder.reminder_type == rtype,
        )
        .first()
        is not None
    )
    return exists


def _log_audit(db: Session, uid: int, d: date, rtype: ReminderType, title: str, body: str, ok: bool) -> None:
    rec = NotificationReminder(
        user_id=uid,
        reminder_date=d,
        reminder_type=rtype,
        title=title,
        body=body,
        delivery_status=DeliveryStatus.SENT if ok else DeliveryStatus.FAILED,
    )
    db.add(rec)
    db.commit()


def _eligible_for_punch_in(db: Session, d: date) -> List[int]:
    # Active employees with no session for today
    subq = (
        db.query(AttendanceSession.employee_id)
        .filter(AttendanceSession.work_date == d)
        .subquery()
    )
    rows = (
        db.query(Employee.id)
        .filter(
            Employee.active.is_(True),
            ~Employee.id.in_(subq),
        )
        .all()
    )
    return [r[0] for r in rows]


def _eligible_for_punch_out(db: Session, d: date) -> List[int]:
    # Employees with a session today that has punch_in_at set and punch_out_at is NULL
    rows = (
        db.query(AttendanceSession.employee_id)
        .filter(
            AttendanceSession.work_date == d,
            AttendanceSession.punch_in_at.isnot(None),
            AttendanceSession.punch_out_at.is_(None),
        )
        .all()
    )
    # Unique user ids
    return list({r[0] for r in rows})


def send_punch_in_reminders(db: Session) -> Dict[str, int]:
    d = _today_ist()
    if _is_public_holiday(db, d):
        _log.info("Reminder(punch-in): public holiday %s - skipping all", d)
        return {"matched": 0, "sent": 0, "skipped": 0}

    leave_users = _employees_on_approved_leave(db, d)
    candidates = [uid for uid in _eligible_for_punch_in(db, d) if uid not in leave_users]
    tokens_by_user = _users_with_active_tokens(db, set(candidates))

    title = "Attendance Reminder"
    body = "You have not punched in yet. Please mark your attendance."
    matched = 0
    sent = 0
    skipped = 0
    for uid in candidates:
        matched += 1
        if uid not in tokens_by_user:
            _log.info("Reminder(punch-in): skip uid=%s no active token", uid)
            skipped += 1
            continue
        if _already_sent(db, uid, d, ReminderType.PUNCH_IN_REMINDER):
            _log.info("Reminder(punch-in): skip uid=%s already sent", uid)
            skipped += 1
            continue
        toks = tokens_by_user[uid]
        res = send_push_to_tokens(toks, title, body, data={"type": "ATTN_PUNCH_IN", "date": str(d)})
        ok = bool(res.get("success")) and int(res.get("success_count", 0)) > 0
        _log_audit(db, uid, d, ReminderType.PUNCH_IN_REMINDER, title, body, ok)
        sent += 1 if ok else 0
    return {"matched": matched, "sent": sent, "skipped": skipped}


def send_punch_out_reminders(db: Session) -> Dict[str, int]:
    d = _today_ist()
    if _is_public_holiday(db, d):
        _log.info("Reminder(punch-out): public holiday %s - skipping all", d)
        return {"matched": 0, "sent": 0, "skipped": 0}

    leave_users = _employees_on_approved_leave(db, d)
    candidates = [uid for uid in _eligible_for_punch_out(db, d) if uid not in leave_users]
    tokens_by_user = _users_with_active_tokens(db, set(candidates))

    title = "Attendance Reminder"
    body = "You have not punched out yet. Please complete your attendance."
    matched = 0
    sent = 0
    skipped = 0
    for uid in candidates:
        matched += 1
        if uid not in tokens_by_user:
            _log.info("Reminder(punch-out): skip uid=%s no active token", uid)
            skipped += 1
            continue
        if _already_sent(db, uid, d, ReminderType.PUNCH_OUT_REMINDER):
            _log.info("Reminder(punch-out): skip uid=%s already sent", uid)
            skipped += 1
            continue
        toks = tokens_by_user[uid]
        res = send_push_to_tokens(toks, title, body, data={"type": "ATTN_PUNCH_OUT", "date": str(d)})
        ok = bool(res.get("success")) and int(res.get("success_count", 0)) > 0
        _log_audit(db, uid, d, ReminderType.PUNCH_OUT_REMINDER, title, body, ok)
        sent += 1 if ok else 0
    return {"matched": matched, "sent": sent, "skipped": skipped}

