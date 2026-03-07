from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from app.core.deps import get_db, get_current_user, require_roles
from app.models.employee import Employee, Role
from app.models.attendance_correction import AttendanceCorrectionRequest, CorrectionRequestType, CorrectionStatus
from app.models.attendance import AttendanceLog
from app.schemas.attendance_correction import AttendanceCorrectionCreate, AttendanceCorrectionOut, AttendanceCorrectionReview
from app.services.audit_service import log_audit

router = APIRouter()

def _parse_request_type(rt: str) -> CorrectionRequestType:
    try:
        return CorrectionRequestType(rt)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request_type")

@router.post("", response_model=AttendanceCorrectionOut, status_code=status.HTTP_201_CREATED)
async def submit_correction(
    payload: AttendanceCorrectionCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    rt = _parse_request_type(payload.request_type)
    if rt == CorrectionRequestType.FORGOT_PUNCH_IN and not payload.requested_punch_in:
        raise HTTPException(status_code=400, detail="requested_punch_in required for FORGOT_PUNCH_IN")
    if rt == CorrectionRequestType.FORGOT_PUNCH_OUT and not payload.requested_punch_out:
        raise HTTPException(status_code=400, detail="requested_punch_out required for FORGOT_PUNCH_OUT")
    if rt == CorrectionRequestType.CORRECTION and not (payload.requested_punch_in or payload.requested_punch_out):
        raise HTTPException(status_code=400, detail="At least one requested time must be provided for CORRECTION")

    req = AttendanceCorrectionRequest(
        employee_id=current_user.id,
        request_type=rt,
        date=payload.date,
        requested_punch_in=payload.requested_punch_in,
        requested_punch_out=payload.requested_punch_out,
        reason=payload.reason,
        remarks=payload.remarks,
        status=CorrectionStatus.PENDING,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    log_audit(db, current_user.id, "ATTN_CORRECTION_CREATE", "attendance_correction_requests", req.id, {
        "request_type": req.request_type,
        "date": str(req.date),
        "requested_punch_in": req.requested_punch_in.isoformat() if req.requested_punch_in else None,
        "requested_punch_out": req.requested_punch_out.isoformat() if req.requested_punch_out else None,
    })
    return req

@router.get("/my", response_model=List[AttendanceCorrectionOut])
async def list_my_corrections(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user)
):
    return db.query(AttendanceCorrectionRequest).filter(
        AttendanceCorrectionRequest.employee_id == current_user.id
    ).order_by(AttendanceCorrectionRequest.created_at.desc()).all()

@router.get("", response_model=List[AttendanceCorrectionOut])
async def list_corrections(
    status_filter: Optional[str] = Query(None),
    employee_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    q = db.query(AttendanceCorrectionRequest)
    if status_filter:
        try:
            st = CorrectionStatus(status_filter)
            q = q.filter(AttendanceCorrectionRequest.status == st)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid status filter")
    if employee_id:
        q = q.filter(AttendanceCorrectionRequest.employee_id == employee_id)
    if date_from:
        q = q.filter(AttendanceCorrectionRequest.date >= date_from)
    if date_to:
        q = q.filter(AttendanceCorrectionRequest.date <= date_to)
    return q.order_by(AttendanceCorrectionRequest.created_at.desc()).all()

def _apply_correction(db: Session, req: AttendanceCorrectionRequest, admin_id: int):
    # Update AttendanceLog for the given date. Create if needed for punch in.
    log = db.query(AttendanceLog).filter(
        AttendanceLog.employee_id == req.employee_id,
        AttendanceLog.punch_date == req.date
    ).first()

    if req.request_type == CorrectionRequestType.FORGOT_PUNCH_IN:
        if log is None:
            # Create a new log with requested punch in; default lat/lng to 0
            log = AttendanceLog(
                employee_id=req.employee_id,
                punch_date=req.date,
                in_time=req.requested_punch_in,
                in_lat=0.0,
                in_lng=0.0,
                source="ADMIN",
            )
            db.add(log)
        else:
            # Update in_time only if missing or clearly earlier than requested
            log.in_time = req.requested_punch_in
    elif req.request_type == CorrectionRequestType.FORGOT_PUNCH_OUT:
        if log is None:
            # If no log, create minimal record with out_time
            log = AttendanceLog(
                employee_id=req.employee_id,
                punch_date=req.date,
                in_time=req.requested_punch_out,  # fallback to same time; admin can adjust later
                in_lat=0.0,
                in_lng=0.0,
                out_time=req.requested_punch_out,
                out_lat=0.0,
                out_lng=0.0,
                source="ADMIN",
            )
            db.add(log)
        else:
            log.out_time = req.requested_punch_out
    else:
        # CORRECTION: apply whichever fields are present
        if log is None and (req.requested_punch_in or req.requested_punch_out):
            log = AttendanceLog(
                employee_id=req.employee_id,
                punch_date=req.date,
                in_time=req.requested_punch_in or req.requested_punch_out,
                in_lat=0.0,
                in_lng=0.0,
                source="ADMIN",
            )
            if req.requested_punch_out:
                log.out_time = req.requested_punch_out
                log.out_lat = 0.0
                log.out_lng = 0.0
            db.add(log)
        else:
            if req.requested_punch_in:
                log.in_time = req.requested_punch_in
            if req.requested_punch_out:
                log.out_time = req.requested_punch_out

    db.commit()
    db.refresh(log)

    log_audit(db, admin_id, "ATTN_CORRECTION_APPLY", "attendance_logs", log.id, {
        "employee_id": req.employee_id,
        "punch_date": str(req.date),
        "in_time": log.in_time.isoformat() if log.in_time else None,
        "out_time": log.out_time.isoformat() if log.out_time else None,
        "source": log.source,
    })

@router.post("/{req_id}/approve", response_model=AttendanceCorrectionOut)
async def approve_correction(
    req_id: int,
    payload: AttendanceCorrectionReview,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    req = db.query(AttendanceCorrectionRequest).filter(AttendanceCorrectionRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Correction request not found")
    if req.status != CorrectionStatus.PENDING:
        raise HTTPException(status_code=409, detail="Request already reviewed")

    req.status = CorrectionStatus.APPROVED
    req.approved_by = current_user.id
    req.approved_at = datetime.utcnow()
    req.admin_remarks = payload.admin_remarks
    db.commit()
    db.refresh(req)

    # Apply correction to attendance
    _apply_correction(db, req, current_user.id)

    log_audit(db, current_user.id, "ATTN_CORRECTION_APPROVE", "attendance_correction_requests", req.id, {
        "admin_remarks": payload.admin_remarks,
    })
    return req

@router.post("/{req_id}/reject", response_model=AttendanceCorrectionOut)
async def reject_correction(
    req_id: int,
    payload: AttendanceCorrectionReview,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_roles(Role.HR))
):
    req = db.query(AttendanceCorrectionRequest).filter(AttendanceCorrectionRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Correction request not found")
    if req.status != CorrectionStatus.PENDING:
        raise HTTPException(status_code=409, detail="Request already reviewed")

    req.status = CorrectionStatus.REJECTED
    req.approved_by = current_user.id
    req.approved_at = datetime.utcnow()
    req.admin_remarks = payload.admin_remarks
    db.commit()
    db.refresh(req)

    log_audit(db, current_user.id, "ATTN_CORRECTION_REJECT", "attendance_correction_requests", req.id, {
        "admin_remarks": payload.admin_remarks,
    })
    return req
