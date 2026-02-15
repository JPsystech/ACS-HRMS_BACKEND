"""
Leave Wallet Service - ACS policy (Jan-Dec year).

- Entitlements: PL=7, SL=6, CL=5, RH=1 (from policy).
- Monthly accrual: +1 CL, +1 PL (pro-rata from join month).
- PL usable only after 6 months from join_date.
- Only PL carries forward (cap from policy, default 30 in docs).
- On APPROVE: deduct from wallet; on REJECT: no deduct; on CANCEL: optional recredit.
"""
import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.leave import (
    LeaveRequest,
    LeaveBalance,
    LeaveTransaction,
    LeaveType,
    LeaveStatus,
    LeaveTransactionAction,
    WALLET_LEAVE_TYPES,
)
from app.models.employee import Employee
from app.services.policy_validator import get_or_create_policy_settings
from app.utils.datetime_utils import now_utc

logger = logging.getLogger(__name__)

# Default carry forward cap for PL when not in policy (user asked default 30)
DEFAULT_PL_CARRY_FORWARD_CAP = 30


def _entitlements_from_policy(db: Session, year: int) -> Dict[str, Any]:
    policy = get_or_create_policy_settings(db, year)
    return {
        "cl": int(getattr(policy, "annual_cl", 5)),
        "sl": int(getattr(policy, "annual_sl", 6)),
        "pl": int(getattr(policy, "annual_pl", 7)),
        "rh": int(getattr(policy, "annual_rh", 1)),
        "pl_eligibility_months": int(getattr(policy, "pl_eligibility_months", 6)),
        "carry_forward_pl_max": int(getattr(policy, "carry_forward_pl_max", 4)),
    }


def _months_elapsed_in_year(join_date: date, year: int, as_of: date) -> int:
    """Months in year that count for accrual (join month onwards for joiners)."""
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), as_of)
    if join_date.year == year:
        start = date(year, join_date.month, 1)
    elif join_date > end:
        return 0
    if start > end:
        return 0
    return max(0, (end.year - start.year) * 12 + (end.month - start.month) + 1)


def _add_months(d: date, months: int) -> date:
    """Add months to date (same day or last day of month)."""
    year, month = d.year, d.month
    month += months
    while month > 12:
        year += 1
        month -= 12
    while month < 1:
        year -= 1
        month += 12
    try:
        return date(year, month, d.day)
    except ValueError:
        if month in (4, 6, 9, 11):
            return date(year, month, 30)
        if month == 2:
            return date(year, 2, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28)
        return date(year, month, 31)


def is_pl_eligible(employee: Employee, as_of_date: date) -> bool:
    """PL can be used only after employee completes 6 months from join_date."""
    eligibility_date = _add_months(employee.join_date, 6)
    return as_of_date >= eligibility_date


def compute_accrual(
    db: Session,
    employee: Employee,
    year: int,
    as_of_date: Optional[date] = None,
) -> Dict[LeaveType, Dict[str, Any]]:
    """
    Compute accrued/remaining per leave type for the year as of as_of_date.
    Pro-rata for new joiners (from join month). PL accrues but is eligible only after 6 months.
    Returns dict of leave_type -> {accrued, remaining, total_entitlement, eligible (for PL)}.
    """
    as_of = as_of_date or date.today()
    ent = _entitlements_from_policy(db, year)
    months = _months_elapsed_in_year(employee.join_date, year, as_of)
    pl_eligible = is_pl_eligible(employee, as_of)

    # CL: min(cap, months * 1)
    cl_cap = ent["cl"]
    cl_accrued = min(cl_cap, months * 1)

    # PL: min(cap, months * 1); eligibility is separate (use only if pl_eligible)
    pl_cap = ent["pl"]
    pl_accrued = min(pl_cap, months * 1)

    # SL: fixed 6 for year; pro-rata for joiners
    sl_cap = ent["sl"]
    if employee.join_date.year == year:
        join_month = employee.join_date.month
        remaining_months = 12 - join_month + 1
        sl_accrued = round(sl_cap * remaining_months / 12, 1)
    else:
        sl_accrued = float(sl_cap)

    # RH: fixed 1
    rh_entitlement = ent["rh"]

    return {
        LeaveType.CL: {"accrued": float(cl_accrued), "total_entitlement": cl_cap, "eligible": True},
        LeaveType.SL: {"accrued": sl_accrued, "total_entitlement": sl_cap, "eligible": True},
        LeaveType.PL: {"accrued": float(pl_accrued), "total_entitlement": pl_cap, "eligible": pl_eligible},
        LeaveType.RH: {"accrued": int(rh_entitlement), "total_entitlement": rh_entitlement, "eligible": True},
    }


def ensure_wallet_for_employee(
    db: Session,
    employee_id: int,
    year: int,
    as_of_date: Optional[date] = None,
) -> List[LeaveBalance]:
    """
    Ensure wallet rows exist for CL/SL/PL/RH for (employee_id, year).
    Creates with opening=0, accrued=0, used=0, remaining=0, carry_forward=0 then recomputes accrued/remaining.
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    as_of = as_of_date or date.today()
    acc = compute_accrual(db, employee, year, as_of)
    rows = []
    for lt in WALLET_LEAVE_TYPES:
        bal = db.query(LeaveBalance).filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year,
            LeaveBalance.leave_type == lt,
        ).first()
        if not bal:
            bal = LeaveBalance(
                employee_id=employee_id,
                year=year,
                leave_type=lt,
                opening=Decimal("0"),
                accrued=Decimal("0"),
                used=Decimal("0"),
                remaining=Decimal("0"),
                carry_forward=Decimal("0"),
            )
            db.add(bal)
            db.flush()
        # Set accrued from computed (opening/carry_forward already set from previous year or 0)
        info = acc[lt]
        accrued_val = Decimal(str(info["accrued"]))
        bal.accrued = accrued_val
        # remaining = opening + accrued + carry_forward - used
        bal.remaining = bal.opening + bal.accrued + bal.carry_forward - bal.used
        rows.append(bal)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


def get_wallet_balances(
    db: Session,
    employee_id: int,
    year: int,
) -> List[LeaveBalance]:
    """Get all wallet rows for employee/year. Ensures wallet exists first."""
    ensure_wallet_for_employee(db, employee_id, year)
    return (
        db.query(LeaveBalance)
        .filter(LeaveBalance.employee_id == employee_id, LeaveBalance.year == year)
        .order_by(LeaveBalance.leave_type)
        .all()
    )


def _get_balance_row(
    db: Session,
    employee_id: int,
    year: int,
    leave_type: LeaveType,
) -> Optional[LeaveBalance]:
    return (
        db.query(LeaveBalance)
        .filter(
            LeaveBalance.employee_id == employee_id,
            LeaveBalance.year == year,
            LeaveBalance.leave_type == leave_type,
        )
        .first()
    )


def _log_transaction(
    db: Session,
    employee_id: int,
    leave_id: Optional[int],
    year: int,
    leave_type: LeaveType,
    delta_days: Decimal,
    action: str,
    remarks: Optional[str],
    action_by_employee_id: Optional[int],
) -> None:
    t = LeaveTransaction(
        employee_id=employee_id,
        leave_id=leave_id,
        year=year,
        leave_type=leave_type,
        delta_days=delta_days,
        action=action,
        remarks=remarks,
        action_by_employee_id=action_by_employee_id,
        action_at=now_utc(),
    )
    db.add(t)


def apply_leave_approval(
    db: Session,
    leave_id: int,
    approver_id: int,
    remark: Optional[str],
) -> LeaveRequest:
    """
    On leave approval: validate sufficient remaining, deduct used, update remaining.
    Sets leave_request.approver_id, approved_remark, approved_at.
    Caller must set status=APPROVED and paid_days/lwp_days.
    """
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Leave status is {leave.status.value}, expected PENDING",
        )
    if leave.leave_type not in WALLET_LEAVE_TYPES:
        # COMPOFF/LWP handled elsewhere
        leave.approver_id = approver_id
        leave.approved_remark = remark
        leave.approved_at = now_utc()
        return leave

    year = leave.from_date.year
    days = float(leave.computed_days)
    ensure_wallet_for_employee(db, leave.employee_id, year)

    # RH: only 1 per year
    if leave.leave_type == LeaveType.RH:
        rh_row = _get_balance_row(db, leave.employee_id, year, LeaveType.RH)
        if rh_row and float(rh_row.used) >= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="RH quota already used for this year",
            )

    bal = _get_balance_row(db, leave.employee_id, year, leave.leave_type)
    if not bal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No balance row for {leave.leave_type.value}",
        )
    remaining = float(bal.remaining)
    paid = min(days, remaining)
    if paid < 0:
        paid = 0

    bal.used = bal.used + Decimal(str(paid))
    bal.remaining = bal.opening + bal.accrued + bal.carry_forward - bal.used
    _log_transaction(
        db, leave.employee_id, leave_id, year, leave.leave_type,
        Decimal(str(-paid)), LeaveTransactionAction.APPROVE_DEDUCT.value, remark, approver_id,
    )
    leave.approver_id = approver_id
    leave.approved_remark = remark
    leave.approved_at = now_utc()
    leave.paid_days = Decimal(str(paid))
    leave.lwp_days = Decimal(str(max(0, days - paid)))
    db.commit()
    db.refresh(leave)
    db.refresh(bal)
    return leave


def apply_leave_rejection(
    db: Session,
    leave_id: int,
    approver_id: int,
    remark: str,
) -> LeaveRequest:
    """Set status=REJECTED, rejected_by_id, rejected_remark, rejected_at. No balance change."""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject leave with status {leave.status.value}",
        )
    leave.status = LeaveStatus.REJECTED
    leave.rejected_by_id = approver_id
    leave.rejected_remark = remark
    leave.rejected_at = now_utc()
    db.commit()
    db.refresh(leave)
    return leave


def apply_leave_cancel(
    db: Session,
    leave_id: int,
    actor_id: int,
    remark: Optional[str],
    recredit: bool = True,
) -> LeaveRequest:
    """
    Set status=CANCELLED, cancelled_by_id, cancelled_remark, cancelled_at.
    If recredit and leave was APPROVED and had paid_days, add back to wallet.
    """
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    if leave.status != LeaveStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only APPROVED leaves can be cancelled",
        )
    leave.status = LeaveStatus.CANCELLED
    leave.cancelled_by_id = actor_id
    leave.cancelled_remark = remark
    leave.cancelled_at = now_utc()

    if recredit and leave.leave_type in WALLET_LEAVE_TYPES and float(leave.paid_days or 0) > 0:
        year = leave.from_date.year
        bal = _get_balance_row(db, leave.employee_id, year, leave.leave_type)
        if bal:
            paid = Decimal(str(leave.paid_days))
            bal.used = bal.used - paid
            bal.remaining = bal.opening + bal.accrued + bal.carry_forward - bal.used
            _log_transaction(
                db, leave.employee_id, leave_id, year, leave.leave_type,
                paid, LeaveTransactionAction.CANCEL_RECREDIT.value, remark, actor_id,
            )
    db.commit()
    db.refresh(leave)
    return leave


def get_transactions(
    db: Session,
    employee_id: int,
    year: Optional[int] = None,
    limit: int = 100,
) -> List[LeaveTransaction]:
    q = db.query(LeaveTransaction).filter(LeaveTransaction.employee_id == employee_id)
    if year is not None:
        q = q.filter(LeaveTransaction.year == year)
    return q.order_by(LeaveTransaction.action_at.desc()).limit(limit).all()
