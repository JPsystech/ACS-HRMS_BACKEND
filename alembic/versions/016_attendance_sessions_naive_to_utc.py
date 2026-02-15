"""Assume existing attendance_sessions timestamps are Asia/Kolkata; convert to UTC.

Revision ID: 016_attendance_naive_utc
Revises: 015_leave_remarks
Create Date: 2026-02-09

Existing naive values (e.g. '2026-02-09 13:35:25' without Z/+00:00) are treated as IST
and converted to UTC for consistent API output (ISO-8601 with Z).
"""
from typing import Sequence, Union
from datetime import datetime
from zoneinfo import ZoneInfo
from alembic import op
from sqlalchemy import text

revision: str = "016_attendance_naive_utc"
down_revision: Union[str, None] = "015_leave_remarks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")


def _parse_and_convert_to_utc(val: str | None) -> str | None:
    """If val is naive (no Z or offset), assume Asia/Kolkata and return UTC string. Else normalize to UTC."""
    if val is None or not val:
        return None
    val = val.strip()
    try:
        if "T" in val:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(val[:19], "%Y-%m-%d %H:%M:%S")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST).astimezone(UTC)
        else:
            dt = dt.astimezone(UTC)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return val


def upgrade() -> None:
    bind = op.get_bind()
    try:
        result = bind.execute(text(
            "SELECT id, punch_in_at, punch_out_at, created_at, updated_at FROM attendance_sessions"
        ))
    except Exception:
        # Table might not exist in some branches
        return
    rows = result.fetchall()
    for row in rows:
        sid, pin, pout, created, updated = row
        pin_utc = _parse_and_convert_to_utc(str(pin) if pin else None)
        pout_utc = _parse_and_convert_to_utc(str(pout) if pout else None)
        created_utc = _parse_and_convert_to_utc(str(created) if created else None)
        updated_utc = _parse_and_convert_to_utc(str(updated) if updated else None)
        if not (pin_utc or pout_utc or created_utc or updated_utc):
            continue
        updates = []
        params = {"id": sid}
        if pin_utc is not None:
            updates.append("punch_in_at = :pin_utc")
            params["pin_utc"] = pin_utc
        if pout_utc is not None:
            updates.append("punch_out_at = :pout_utc")
            params["pout_utc"] = pout_utc
        if created_utc is not None:
            updates.append("created_at = :created_utc")
            params["created_utc"] = created_utc
        if updated_utc is not None:
            updates.append("updated_at = :updated_utc")
            params["updated_utc"] = updated_utc
        if updates:
            bind.execute(
                text("UPDATE attendance_sessions SET " + ", ".join(updates) + " WHERE id = :id"),
                params,
            )


def downgrade() -> None:
    # No reversible conversion (we don't store original naive values)
    pass
