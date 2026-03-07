from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging
from app.core.deps import get_db, get_current_user, require_roles
from app.models.employee import Employee, Role
from app.models.notification_device import NotificationDevice
from app.schemas.notifications import (
    RegisterDeviceRequest,
    RegisterDeviceResponse,
    TestPushRequest,
    TestPushResponse,
)
from app.services.push_service import send_push_to_tokens
from app.services.reminder_service import send_punch_in_reminders, send_punch_out_reminders

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register-device", response_model=RegisterDeviceResponse)
def register_device(
    req: RegisterDeviceRequest,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
) -> RegisterDeviceResponse:
    logger.info(
        "Notifications: register-device user_id=%s platform=%s token_prefix=%s",
        user.id, req.platform, req.fcm_token[:10]
    )
    try:
        device = (
            db.query(NotificationDevice)
            .filter(NotificationDevice.fcm_token == req.fcm_token)
            .one_or_none()
        )
        if device:
            device.user_id = user.id
            device.platform = req.platform
            device.app_version = req.app_version
            device.is_active = req.is_active
        else:
            device = NotificationDevice(
                user_id=user.id,
                fcm_token=req.fcm_token,
                platform=req.platform,
                app_version=req.app_version,
                is_active=req.is_active,
            )
            db.add(device)
        db.commit()
        db.refresh(device)
        logger.info("Notifications: device saved id=%s", device.id)
        return RegisterDeviceResponse(status="ok", device_id=device.id)
    except Exception as e:
        logger.exception("Notifications: register-device failed")
        detail = str(e)
        # Provide a clearer hint when table is missing
        if "notification_devices" in detail or "no such table" in detail or "relation" in detail:
            raise HTTPException(
                status_code=500,
                detail=f"Device registration failed: {detail}. Ensure migrations are applied (alembic upgrade head)."
            )
        raise HTTPException(status_code=500, detail=f"Device registration failed: {detail}")


@router.post("/test", response_model=TestPushResponse, dependencies=[Depends(require_roles([Role.ADMIN, Role.HR]))])
def send_test_push(
    req: TestPushRequest,
    db: Session = Depends(get_db),
) -> TestPushResponse:
    tokens: List[str] = []
    if req.token:
        tokens = [req.token]
    elif req.user_id is not None:
        logger.info("Notifications: test push requested for user_id=%s", req.user_id)
        rows = (
            db.query(NotificationDevice)
            .filter(NotificationDevice.user_id == req.user_id, NotificationDevice.is_active.is_(True))
            .all()
        )
        tokens = [r.fcm_token for r in rows]
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide user_id or token")
    result = send_push_to_tokens(tokens, req.title, req.body, req.data)
    if not result.get("success"):
        logger.error("Notifications: push failed error=%s", result.get("error"))
        raise HTTPException(status_code=500, detail=f"Push failed: {result.get('error')}")
    logger.info(
        "Notifications: push sent success=%s success_count=%s failure_count=%s",
        result.get("success"),
        result.get("success_count"),
        result.get("failure_count"),
    )
    return TestPushResponse(status="sent", result=result)


@router.post("/run-punch-in-reminders")
def run_punch_in_reminders(
    db: Session = Depends(get_db),
    _: Employee = Depends(require_roles([Role.ADMIN, Role.HR])),
):
    result = send_punch_in_reminders(db)
    logger.info("run_punch_in_reminders: %s", result)
    return {"status": "ok", **result}


@router.post("/run-punch-out-reminders")
def run_punch_out_reminders(
    db: Session = Depends(get_db),
    _: Employee = Depends(require_roles([Role.ADMIN, Role.HR])),
):
    result = send_punch_out_reminders(db)
    logger.info("run_punch_out_reminders: %s", result)
    return {"status": "ok", **result}
