"""
Reports and exports endpoints
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.models.employee import Employee
from app.services.report_service import (
    get_attendance_rows,
    get_leave_rows,
    get_compoff_rows
)
from app.utils.csv_export import stream_csv
from app.services.audit_service import log_audit

router = APIRouter()


@router.get("/attendance.csv")
async def export_attendance_csv(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    department_id: Optional[int] = Query(None, description="Filter by department ID (HR only)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Export attendance data as CSV
    
    Role-based scoping:
    - HR: all employees
    - MANAGER: only direct reportees
    - EMPLOYEE: only own records
    
    Filters:
    - from_date, to_date: Required date range
    - employee_id: Optional (role-restricted)
    - department_id: Optional (HR only)
    
    Requires valid JWT token.
    """
    rows = get_attendance_rows(
        db=db,
        current_user=current_user,
        from_date=from_date,
        to_date=to_date,
        employee_id=employee_id,
        department_id=department_id
    )
    
    # Generate filename
    filename = f"attendance_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.csv"
    
    # Log audit
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="REPORT_EXPORT",
        entity_type="report",
        entity_id=None,
        meta={
            "report_type": "attendance",
            "from_date": str(from_date),
            "to_date": str(to_date),
            "employee_id": employee_id,
            "department_id": department_id,
            "row_count": len(rows)
        }
    )
    
    # CSV headers
    headers = [
        "emp_code",
        "employee_name",
        "department_name",
        "punch_date",
        "in_time",
        "in_lat",
        "in_lng",
        "out_time",
        "out_lat",
        "out_lng",
        "source"
    ]
    
    return stream_csv(headers=headers, rows=rows, filename=filename)


@router.get("/leaves.csv")
async def export_leaves_csv(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    department_id: Optional[int] = Query(None, description="Filter by department ID (HR only)"),
    status: Optional[str] = Query(None, description="Filter by status (PENDING, APPROVED, REJECTED)"),
    leave_type: Optional[str] = Query(None, description="Filter by leave type (CL, PL, SL, etc.)"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Export leave data as CSV
    
    Role-based scoping:
    - HR: all employees
    - MANAGER: only direct reportees
    - EMPLOYEE: only own records
    
    Date overlap: Includes leaves that overlap with the date range (not just starts within range).
    
    Filters:
    - from_date, to_date: Required date range
    - employee_id: Optional (role-restricted)
    - department_id: Optional (HR only)
    - status: Optional (PENDING, APPROVED, REJECTED)
    - leave_type: Optional (CL, PL, SL, RH, COMPOFF, LWP)
    
    Requires valid JWT token.
    """
    rows = get_leave_rows(
        db=db,
        current_user=current_user,
        from_date=from_date,
        to_date=to_date,
        employee_id=employee_id,
        department_id=department_id,
        status_filter=status,
        leave_type_filter=leave_type
    )
    
    # Generate filename
    filename = f"leaves_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.csv"
    
    # Log audit
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="REPORT_EXPORT",
        entity_type="report",
        entity_id=None,
        meta={
            "report_type": "leaves",
            "from_date": str(from_date),
            "to_date": str(to_date),
            "employee_id": employee_id,
            "department_id": department_id,
            "status": status,
            "leave_type": leave_type,
            "row_count": len(rows)
        }
    )
    
    # CSV headers
    headers = [
        "emp_code",
        "employee_name",
        "department_name",
        "leave_type",
        "from_date",
        "to_date",
        "status",
        "computed_days",
        "paid_days",
        "lwp_days",
        "applied_at",
        "approved_by_emp_code",
        "approved_at",
        "remarks",
        "override_policy",
        "override_remark"
    ]
    
    return stream_csv(headers=headers, rows=rows, filename=filename)


@router.get("/compoff.csv")
async def export_compoff_csv(
    from_date: date = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: date = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    employee_id: Optional[int] = Query(None, description="Filter by employee ID"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    """
    Export comp-off request data as CSV
    
    Role-based scoping:
    - HR: all employees
    - MANAGER: only direct reportees
    - EMPLOYEE: only own records
    
    Filters:
    - from_date, to_date: Required date range
    - employee_id: Optional (role-restricted)
    
    Requires valid JWT token.
    """
    rows = get_compoff_rows(
        db=db,
        current_user=current_user,
        from_date=from_date,
        to_date=to_date,
        employee_id=employee_id
    )
    
    # Generate filename
    filename = f"compoff_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.csv"
    
    # Log audit
    log_audit(
        db=db,
        actor_id=current_user.id,
        action="REPORT_EXPORT",
        entity_type="report",
        entity_id=None,
        meta={
            "report_type": "compoff",
            "from_date": str(from_date),
            "to_date": str(to_date),
            "employee_id": employee_id,
            "row_count": len(rows)
        }
    )
    
    # CSV headers
    headers = [
        "emp_code",
        "employee_name",
        "department_name",
        "worked_date",
        "status",
        "reason",
        "requested_at"
    ]
    
    return stream_csv(headers=headers, rows=rows, filename=filename)
