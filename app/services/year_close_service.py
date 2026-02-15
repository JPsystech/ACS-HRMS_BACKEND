"""
Year-end close - PL carry forward to next year (wallet model).
Only PL carries forward (cap from policy). CL/SL/RH lapse.
"""
from datetime import date
from typing import Dict, List
from sqlalchemy.orm import Session
from decimal import Decimal
from app.models.leave import LeaveBalance, LeaveTransaction, LeaveType, LeaveTransactionAction, WALLET_LEAVE_TYPES
from app.models.employee import Employee
from app.models.hr_actions import HRPolicyAction, HRPolicyActionType
from app.services.audit_service import log_audit
from app.services.policy_validator import get_or_create_policy_settings
from app.services import leave_wallet_service as wallet


def run_year_close(
    db: Session,
    year: int,
    actor_id: int
) -> Dict:
    """
    For each employee with a PL balance row: carry forward min(remaining, cap) to next year.
    Create next year's wallet rows: CL/SL/RH opening=0; PL opening=carry_forward.
    """
    next_year = year + 1
    settings = get_or_create_policy_settings(db, year)
    carry_forward_max = int(getattr(settings, "carry_forward_pl_max", 4))

    pl_rows = db.query(LeaveBalance).filter(
        LeaveBalance.year == year,
        LeaveBalance.leave_type == LeaveType.PL,
    ).all()

    total_processed = 0
    employees_with_carry = 0
    employees_with_encash = 0
    total_carry_forward = Decimal("0")
    total_encash = Decimal("0")
    details = []

    for pl_bal in pl_rows:
        total_processed += 1
        employee = db.query(Employee).filter(Employee.id == pl_bal.employee_id).first()
        if not employee:
            continue

        unused_pl = pl_bal.remaining
        carry_forward = min(unused_pl, Decimal(str(carry_forward_max)))
        encash = max(Decimal("0"), unused_pl - carry_forward)

        pl_bal.carry_forward = carry_forward
        if carry_forward > 0:
            employees_with_carry += 1
            total_carry_forward += carry_forward
        if encash > 0:
            employees_with_encash += 1
            total_encash += encash

        for lt in WALLET_LEAVE_TYPES:
            next_row = db.query(LeaveBalance).filter(
                LeaveBalance.employee_id == pl_bal.employee_id,
                LeaveBalance.year == next_year,
                LeaveBalance.leave_type == lt,
            ).first()
            if not next_row:
                opening = carry_forward if lt == LeaveType.PL else Decimal("0")
                accrued = Decimal("0")
                used = Decimal("0")
                rem = opening
                cf = Decimal("0") if lt != LeaveType.PL else opening
                next_row = LeaveBalance(
                    employee_id=pl_bal.employee_id,
                    year=next_year,
                    leave_type=lt,
                    opening=opening,
                    accrued=accrued,
                    used=used,
                    remaining=rem,
                    carry_forward=cf if lt == LeaveType.PL else Decimal("0"),
                )
                db.add(next_row)
                if lt == LeaveType.PL and carry_forward > 0:
                    db.add(LeaveTransaction(
                        employee_id=pl_bal.employee_id,
                        leave_id=None,
                        year=next_year,
                        leave_type=LeaveType.PL,
                        delta_days=carry_forward,
                        action=LeaveTransactionAction.YEAR_CLOSE.value,
                        remarks=f"Carry forward from {year}",
                        action_by_employee_id=actor_id,
                    ))
            else:
                if lt == LeaveType.PL:
                    next_row.opening = carry_forward
                    next_row.remaining = next_row.opening + next_row.accrued + next_row.carry_forward - next_row.used
                    if carry_forward > 0:
                        db.add(LeaveTransaction(
                            employee_id=pl_bal.employee_id,
                            leave_id=None,
                            year=next_year,
                            leave_type=LeaveType.PL,
                            delta_days=carry_forward,
                            action=LeaveTransactionAction.YEAR_CLOSE.value,
                            remarks=f"Carry forward from {year}",
                            action_by_employee_id=actor_id,
                        ))
            db.flush()

        if encash > 0:
            db.add(HRPolicyAction(
                employee_id=pl_bal.employee_id,
                action_type=HRPolicyActionType.OTHER,
                reference_entity_type="leave_balance",
                reference_entity_id=pl_bal.id,
                meta_json={
                    "year": year,
                    "unused_pl": float(unused_pl),
                    "carry_forward": float(carry_forward),
                    "encash_days": float(encash),
                    "carry_forward_max": carry_forward_max,
                },
                action_by=actor_id,
                remarks=f"Year-end close: PL encashment of {encash} days (above carry forward max {carry_forward_max})",
            ))

        details.append({
            "employee_id": employee.id,
            "emp_code": employee.emp_code,
            "name": employee.name,
            "unused_pl": float(unused_pl),
            "carry_forward": float(carry_forward),
            "encash_days": float(encash),
        })

    db.commit()

    log_audit(
        db=db,
        actor_id=actor_id,
        action="YEAR_CLOSE_RUN",
        entity_type="year_close",
        entity_id=None,
        meta={
            "year": year,
            "next_year": next_year,
            "total_employees_processed": total_processed,
            "employees_with_carry_forward": employees_with_carry,
            "employees_with_encash": employees_with_encash,
            "total_carry_forward": float(total_carry_forward),
            "total_encash": float(total_encash),
        },
    )

    return {
        "year": year,
        "next_year": next_year,
        "total_employees_processed": total_processed,
        "employees_with_carry_forward": employees_with_carry,
        "employees_with_encash": employees_with_encash,
        "total_carry_forward": float(total_carry_forward),
        "total_encash": float(total_encash),
        "details": details,
    }
