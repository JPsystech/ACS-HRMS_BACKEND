from datetime import datetime, date, timedelta
from typing import List, Tuple
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.attendance_daily import AttendanceDaily
from app.models.holiday import Holiday
from app.utils.datetime_utils import now_utc, to_ist, ensure_utc

IST = ZoneInfo("Asia/Kolkata")


GOOD_CUTOFF_HOUR = 10
GOOD_CUTOFF_MINUTE = 0


def _ist_date(dt_utc: datetime) -> date:
    return to_ist(dt_utc).date()  # type: ignore[arg-type]


def upsert_daily_on_punch_in(db: Session, user_id: int, punch_in_at_utc: datetime) -> None:
    """
    Upsert attendance_daily for the user's work_date with earliest first_in_time and is_good flag.
    """
    wd = _ist_date(punch_in_at_utc)

    ad: AttendanceDaily | None = (
        db.query(AttendanceDaily)
        .filter(AttendanceDaily.user_id == user_id, AttendanceDaily.work_date == wd)
        .first()
    )

    if ad is None:
        ad = AttendanceDaily(user_id=user_id, work_date=wd, first_in_time=punch_in_at_utc)
        db.add(ad)
    else:
        if ad.first_in_time is None or ensure_utc(punch_in_at_utc) < ensure_utc(ad.first_in_time):
            ad.first_in_time = punch_in_at_utc

    # Recompute is_good using IST time of first_in_time
    if ad.first_in_time is not None:
        ist = to_ist(ad.first_in_time)
        ad.is_good = (ist.hour < GOOD_CUTOFF_HOUR) or (ist.hour == GOOD_CUTOFF_HOUR and ist.minute <= GOOD_CUTOFF_MINUTE)
    else:
        ad.is_good = False

    # computed_at auto via DB; explicit update triggers updated timestamp
    db.flush()


def _working_days_back(db: Session, upto: date, window: int) -> List[date]:
    """
    Return the last `window` working days up to and including the last working day on/before `upto`.
    Sundays and active holidays are excluded.
    """
    holidays = set(
        d for (d,) in db.query(Holiday.date).filter(Holiday.active == True, Holiday.date <= upto).all()  # noqa: E712
    )
    days: List[date] = []
    cur = upto
    while len(days) < window:
        is_sunday = cur.weekday() == 6
        if not is_sunday and cur not in holidays:
            days.append(cur)
        cur = cur - timedelta(days=1)
    return list(reversed(days))


def get_streak_and_consistency(
    db: Session, user_id: int, window: int = 30, today_utc: datetime | None = None
) -> Tuple[int, int, int, int]:
    """
    Returns (current_streak_days, consistency_percent, work_days, good_days)
    for the last N working days ending at last working day on/before today IST.
    """
    today_ist = to_ist(today_utc or now_utc())
    upto_date = today_ist.date()
    days = _working_days_back(db, upto_date, window)
    if not days:
        return (0, 0, 0, 0)

    min_d, max_d = days[0], days[-1]
    rows: List[AttendanceDaily] = (
        db.query(AttendanceDaily)
        .filter(
            AttendanceDaily.user_id == user_id,
            AttendanceDaily.work_date >= min_d,
            AttendanceDaily.work_date <= max_d,
        )
        .all()
    )
    by_date = {r.work_date: r for r in rows}

    good_count = 0
    for d in days:
        r = by_date.get(d)
        if r and r.is_good:
            good_count += 1
    work_days = len(days)
    consistency = round((good_count / work_days) * 100) if work_days else 0

    # Streak from latest working day backwards until first false/missing
    streak = 0
    for d in reversed(days):
        r = by_date.get(d)
        if r and r.is_good:
            streak += 1
        else:
            break

    return (streak, consistency, work_days, good_count)

