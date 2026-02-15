"""
Report service - data export for attendance and leaves
"""
from datetime import date
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status
from app.models.employee import Employee, Role
from app.models.attendance import AttendanceLog
from app.models.attendance_session import AttendanceSession
from app.models.leave import LeaveRequest, LeaveStatus, LeaveType
from app.models.department import Department
from app.models.compoff import CompoffRequest, CompoffRequestStatus
from app.services.leave_service import get_subordinate_ids


def get_attendance_rows(
    db: Session,
    current_user: Employee,
    from_date: date,
    to_date: date,
    employee_id: Optional[int] = None,
    department_id: Optional[int] = None
) -> List[Dict]:
    """
    Get attendance rows for export with role-based scoping
    
    Args:
        db: Database session
        current_user: Current authenticated user
        from_date: Start date filter
        to_date: End date filter
        employee_id: Optional employee ID filter
        department_id: Optional department ID filter (HR only)
    
    Returns:
        List of dictionaries with attendance data
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate date range
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be <= to_date"
        )
    
    # --- First, prefer new session-based attendance (AttendanceSession with IST work_date) ---
    session_query = db.query(
        AttendanceSession,
        Employee,
        Department,
    ).join(
        Employee, AttendanceSession.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        AttendanceSession.work_date >= from_date,
        AttendanceSession.work_date <= to_date,
    )

    # Apply role-based scoping (same rules as legacy AttendanceLog)
    session_results: List[Dict] = []

    if current_user.role == Role.HR:
        # HR can see all
        if employee_id:
            session_query = session_query.filter(Employee.id == employee_id)
        if department_id:
            session_query = session_query.filter(Department.id == department_id)
        session_results = session_query.order_by(
            AttendanceSession.work_date, Employee.emp_code
        ).all()
    elif current_user.role == Role.MANAGER:
        # MANAGER can see full hierarchical subtree (direct and indirect reports)
        subordinate_ids = get_subordinate_ids(db, current_user.id)
        
        # Include manager's own attendance in the visible set
        subordinate_ids.append(current_user.id)

        if not subordinate_ids:
            session_results = []
        else:
            session_query = session_query.filter(Employee.id.in_(subordinate_ids))

            if employee_id:
                if employee_id not in subordinate_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only export attendance for employees in your reporting hierarchy"
                    )
                session_query = session_query.filter(Employee.id == employee_id)

            # MANAGER cannot filter by department_id (only HR)
            if department_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only HR can filter by department",
                )

            session_results = session_query.order_by(
                AttendanceSession.work_date, Employee.emp_code
            ).all()
    else:
        # EMPLOYEE can see only their own
        session_query = session_query.filter(Employee.id == current_user.id)

        if employee_id and employee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only export your own attendance",
            )

        # EMPLOYEE cannot filter by department_id
        if department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR can filter by department",
            )

        session_results = session_query.order_by(
            AttendanceSession.work_date, Employee.emp_code
        ).all()

    rows: List[Dict] = []

    # If we have any session-based rows, use them as the source of truth.
    if session_results:
        for session, emp, dept in session_results:
            in_geo = session.punch_in_geo or {}
            out_geo = session.punch_out_geo or {}

            rows.append(
                {
                    "emp_code": emp.emp_code,
                    "employee_name": emp.name,
                    "department_name": dept.name,
                    "punch_date": str(session.work_date),
                    "in_time": session.punch_in_at.isoformat()
                    if session.punch_in_at
                    else "",
                    "in_lat": str(in_geo.get("lat", "")),
                    "in_lng": str(in_geo.get("lng", "")),
                    "out_time": session.punch_out_at.isoformat()
                    if session.punch_out_at
                    else "",
                    "out_lat": str(out_geo.get("lat", "")),
                    "out_lng": str(out_geo.get("lng", "")),
                    "source": (session.punch_in_source or "").lower(),
                }
            )

        return rows

    # --- Fallback: legacy AttendanceLog (for older data / tests) ---
    query = db.query(
        AttendanceLog,
        Employee,
        Department,
    ).join(
        Employee, AttendanceLog.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        AttendanceLog.punch_date >= from_date,
        AttendanceLog.punch_date <= to_date,
    )

    # Apply role-based scoping for legacy logs
    if current_user.role == Role.HR:
        # HR can see all
        if employee_id:
            query = query.filter(Employee.id == employee_id)
        if department_id:
            query = query.filter(Department.id == department_id)
    elif current_user.role == Role.MANAGER:
        # MANAGER can see only direct reportees
        reportee_ids = [
            emp_id for (emp_id,) in db.query(Employee.id).filter(
                Employee.reporting_manager_id == current_user.id
            ).all()
        ]
        
        if not reportee_ids:
            return []  # No reportees
        
        query = query.filter(Employee.id.in_(reportee_ids))
        
        if employee_id:
            if employee_id not in reportee_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only export attendance for your direct reportees"
                )
            query = query.filter(Employee.id == employee_id)
        
        # MANAGER cannot filter by department_id (only HR)
        if department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR can filter by department"
            )
    else:
        # EMPLOYEE can see only their own
        query = query.filter(Employee.id == current_user.id)
        
        if employee_id and employee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only export your own attendance"
            )
        
        # EMPLOYEE cannot filter by department_id
        if department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR can filter by department"
            )
    
    # Execute query and build rows
    results = query.order_by(AttendanceLog.punch_date, Employee.emp_code).all()
    
    rows = []
    for attendance, emp, dept in results:
        rows.append({
            "emp_code": emp.emp_code,
            "employee_name": emp.name,
            "department_name": dept.name,
            "punch_date": str(attendance.punch_date),
            "in_time": attendance.in_time.isoformat() if attendance.in_time else "",
            "in_lat": str(attendance.in_lat) if attendance.in_lat else "",
            "in_lng": str(attendance.in_lng) if attendance.in_lng else "",
            "out_time": attendance.out_time.isoformat() if attendance.out_time else "",
            "out_lat": str(attendance.out_lat) if attendance.out_lat else "",
            "out_lng": str(attendance.out_lng) if attendance.out_lng else "",
            "source": attendance.source or ""
        })
    
    return rows


def get_leave_rows(
    db: Session,
    current_user: Employee,
    from_date: date,
    to_date: date,
    employee_id: Optional[int] = None,
    department_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    leave_type_filter: Optional[str] = None
) -> List[Dict]:
    """
    Get leave rows for export with role-based scoping and date overlap filtering
    
    Args:
        db: Database session
        current_user: Current authenticated user
        from_date: Start date filter
        to_date: End date filter
        employee_id: Optional employee ID filter
        department_id: Optional department ID filter (HR only)
        status_filter: Optional status filter (PENDING, APPROVED, REJECTED)
        leave_type_filter: Optional leave type filter (CL, PL, SL, etc.)
    
    Returns:
        List of dictionaries with leave data
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate date range
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be <= to_date"
        )
    
    # Build base query
    query = db.query(
        LeaveRequest,
        Employee,
        Department
    ).join(
        Employee, LeaveRequest.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    )
    
    # Date overlap filter: include leave if NOT (to_date < filter_from OR from_date > filter_to)
    # Which means: include if (to_date >= filter_from AND from_date <= filter_to)
    query = query.filter(
        LeaveRequest.to_date >= from_date,
        LeaveRequest.from_date <= to_date
    )
    
    # Apply role-based scoping
    if current_user.role == Role.HR:
        # HR can see all
        if employee_id:
            query = query.filter(Employee.id == employee_id)
        if department_id:
            query = query.filter(Department.id == department_id)
    elif current_user.role == Role.MANAGER:
        # MANAGER can see full hierarchical subtree (direct and indirect reports)
        subordinate_ids = get_subordinate_ids(db, current_user.id)
        
        # Include manager's own leaves in the visible set
        subordinate_ids.append(current_user.id)
        
        if not subordinate_ids:
            return []  # No subordinates
        
        query = query.filter(Employee.id.in_(subordinate_ids))
        
        if employee_id:
            if employee_id not in subordinate_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only export leaves for employees in your reporting hierarchy"
                )
            query = query.filter(Employee.id == employee_id)
        
        # MANAGER cannot filter by department_id (only HR)
        if department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR can filter by department"
            )
    else:
        # EMPLOYEE can see only their own
        query = query.filter(Employee.id == current_user.id)
        
        if employee_id and employee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only export your own leaves"
            )
        
        # EMPLOYEE cannot filter by department_id
        if department_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only HR can filter by department"
            )
    
    # Apply optional filters
    if status_filter:
        try:
            status_enum = LeaveStatus(status_filter)
            query = query.filter(LeaveRequest.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    
    if leave_type_filter:
        try:
            leave_type_enum = LeaveType(leave_type_filter)
            query = query.filter(LeaveRequest.leave_type == leave_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid leave_type: {leave_type_filter}"
            )
    
    # Get approval info (if approved/rejected)
    from app.models.leave import LeaveApproval
    
    # Execute query
    results = query.order_by(LeaveRequest.from_date.desc(), Employee.emp_code).all()
    
    rows = []
    for leave_request, emp, dept in results:
        # Get approval info
        approval = db.query(LeaveApproval).filter(
            LeaveApproval.leave_request_id == leave_request.id,
            LeaveApproval.action.in_(["APPROVE", "REJECT"])
        ).order_by(LeaveApproval.action_at.desc()).first()
        
        approved_by_emp_code = ""
        approved_at = ""
        remarks = ""
        
        if approval:
            approver = db.query(Employee).filter(Employee.id == approval.action_by).first()
            if approver:
                approved_by_emp_code = approver.emp_code
            approved_at = approval.action_at.isoformat() if approval.action_at else ""
            remarks = approval.remarks or ""
        
        rows.append({
            "emp_code": emp.emp_code,
            "employee_name": emp.name,
            "department_name": dept.name,
            "leave_type": leave_request.leave_type.value,
            "from_date": str(leave_request.from_date),
            "to_date": str(leave_request.to_date),
            "status": leave_request.status.value,
            "computed_days": str(float(leave_request.computed_days)),
            "paid_days": str(float(leave_request.paid_days)) if leave_request.paid_days else "0",
            "lwp_days": str(float(leave_request.lwp_days)) if leave_request.lwp_days else "0",
            "applied_at": leave_request.applied_at.isoformat() if leave_request.applied_at else "",
            "approved_by_emp_code": approved_by_emp_code,
            "approved_at": approved_at,
            "remarks": remarks,
            "override_policy": "Yes" if leave_request.override_policy else "No",
            "override_remark": leave_request.override_remark or ""
        })
    
    return rows


def get_compoff_rows(
    db: Session,
    current_user: Employee,
    from_date: date,
    to_date: date,
    employee_id: Optional[int] = None
) -> List[Dict]:
    """
    Get comp-off request rows for export with role-based scoping
    
    Args:
        db: Database session
        current_user: Current authenticated user
        from_date: Start date filter
        to_date: End date filter
        employee_id: Optional employee ID filter
    
    Returns:
        List of dictionaries with comp-off data
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate date range
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from_date must be <= to_date"
        )
    
    # Build base query
    query = db.query(
        CompoffRequest,
        Employee,
        Department
    ).join(
        Employee, CompoffRequest.employee_id == Employee.id
    ).join(
        Department, Employee.department_id == Department.id
    ).filter(
        CompoffRequest.worked_date >= from_date,
        CompoffRequest.worked_date <= to_date
    )
    
    # Apply role-based scoping
    if current_user.role == Role.HR:
        # HR can see all
        if employee_id:
            query = query.filter(Employee.id == employee_id)
    elif current_user.role == Role.MANAGER:
        # MANAGER can see full hierarchical subtree (direct and indirect reports)
        subordinate_ids = get_subordinate_ids(db, current_user.id)
        
        # Include manager's own compoff in the visible set
        subordinate_ids.append(current_user.id)
        
        if not subordinate_ids:
            return []  # No subordinates
        
        query = query.filter(Employee.id.in_(subordinate_ids))
        
        if employee_id:
            if employee_id not in subordinate_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only export comp-off requests for employees in your reporting hierarchy"
                )
            query = query.filter(Employee.id == employee_id)
    else:
        # EMPLOYEE can see only their own
        query = query.filter(Employee.id == current_user.id)
        
        if employee_id and employee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only export your own comp-off requests"
            )
    
    # Execute query
    results = query.order_by(CompoffRequest.worked_date.desc(), Employee.emp_code).all()
    
    rows = []
    for compoff_request, emp, dept in results:
        rows.append({
            "emp_code": emp.emp_code,
            "employee_name": emp.name,
            "department_name": dept.name,
            "worked_date": str(compoff_request.worked_date),
            "status": compoff_request.status.value,
            "reason": compoff_request.reason or "",
            "requested_at": compoff_request.requested_at.isoformat() if compoff_request.requested_at else ""
        })
    
    return rows
