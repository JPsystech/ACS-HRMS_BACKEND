import logging
import os
from typing import Any, Dict, List, Optional
from app.core.config import settings
import json

logger = logging.getLogger(__name__)

_firebase_initialized = False
_firebase_error: Optional[str] = None

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    _import_ok = True
except Exception as e:
    firebase_admin = None  # type: ignore
    messaging = None  # type: ignore
    _firebase_error = f"firebase_admin not available: {e}"
    _import_ok = False


def _ensure_firebase() -> None:
    global _firebase_initialized, _firebase_error
    if _firebase_initialized:
        return
    # Effective enablement: either explicit FCM_ENABLED or presence of service account config
    if not settings.FCM_ENABLED:
        sa_cfg = getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", None)
        if not sa_cfg:
            _firebase_error = "FCM disabled: FCM_ENABLED=False and FCM_SERVICE_ACCOUNT_JSON not set"
            return
    if firebase_admin is None or messaging is None:
        return
    sa_cfg = settings.FCM_SERVICE_ACCOUNT_JSON
    if not sa_cfg:
        _firebase_error = "FCM service account not configured"
        return
    try:
        if sa_cfg.strip().startswith("{"):
            cred_dict = json.loads(sa_cfg)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("FCM initialized using JSON from env")
        else:
            if not os.path.exists(sa_cfg):
                _firebase_error = f"FCM service account path does not exist: {sa_cfg}"
                return
            cred = credentials.Certificate(sa_cfg)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("FCM initialized (service_account=%s)", sa_cfg)
    except Exception as e:
        _firebase_error = f"Failed to initialize Firebase Admin: {e}"
        logger.error(_firebase_error)


def diagnose_fcm_config() -> Dict[str, Any]:
    """
    Return startup diagnostics for FCM configuration.
    """
    sa_cfg = getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", None)
    is_json = bool(sa_cfg and sa_cfg.strip().startswith("{"))
    path_exists = bool(sa_cfg) and not is_json and os.path.exists(sa_cfg) if sa_cfg else False
    effective_enabled = bool(settings.FCM_ENABLED or is_json or path_exists)
    return {
        "configured_enabled": bool(settings.FCM_ENABLED),
        "effective_enabled": effective_enabled,
        "service_account_path": ("env:json" if is_json else sa_cfg),
        "service_account_path_exists": path_exists,
        "initialized": _firebase_initialized,
        "init_error": _firebase_error,
        "firebase_admin_present": firebase_admin is not None,
        "firebase_admin_import_ok": _import_ok,
    }


def send_push_to_tokens(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    _ensure_firebase()
    sa_cfg = getattr(settings, "FCM_SERVICE_ACCOUNT_JSON", None)
    is_json = bool(sa_cfg and sa_cfg.strip().startswith("{"))
    path_ok = bool(sa_cfg) and not is_json and os.path.exists(sa_cfg)
    effective_enabled = bool(settings.FCM_ENABLED or is_json or path_ok)
    if not effective_enabled:
        logger.warning("FCM disabled; set FCM_ENABLED=true or provide valid FCM_SERVICE_ACCOUNT_JSON")
        return {"success": False, "error": "FCM disabled"}
    if messaging is None or not _firebase_initialized:
        return {"success": False, "error": _firebase_error or "FCM not initialized"}
    if not tokens:
        return {"success": False, "error": "No tokens provided"}
    try:
        # Prefer send_multicast if available
        if hasattr(messaging, "send_multicast") and hasattr(messaging, "MulticastMessage"):
            msg = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
            )
            response = messaging.send_multicast(msg, dry_run=False)  # type: ignore[attr-defined]
            logger.info(
                "FCM send_multicast: success_count=%s failure_count=%s title=%s",
                getattr(response, "success_count", None),
                getattr(response, "failure_count", None),
                title,
            )
            return {
                "success": True,
                "success_count": getattr(response, "success_count", 0),
                "failure_count": getattr(response, "failure_count", 0),
                "responses": [getattr(r, "__dict__", {}) for r in getattr(response, "responses", [])],
            }
        else:
            # Fallbacks for SDKs without send_multicast
            messages = [
                messaging.Message(
                    token=t,
                    notification=messaging.Notification(title=title, body=body),
                    data={k: str(v) for k, v in (data or {}).items()},
                )
                for t in tokens
            ]
            if hasattr(messaging, "send_all"):
                response = messaging.send_all(messages, dry_run=False)  # type: ignore[attr-defined]
                logger.info(
                    "FCM send_all: success_count=%s failure_count=%s title=%s",
                    getattr(response, "success_count", None),
                    getattr(response, "failure_count", None),
                    title,
                )
                return {
                    "success": True,
                    "success_count": getattr(response, "success_count", 0),
                    "failure_count": getattr(response, "failure_count", 0),
                    "responses": [getattr(r, "__dict__", {}) for r in getattr(response, "responses", [])],
                }
            elif hasattr(messaging, "send_each"):
                response = messaging.send_each(messages, dry_run=False)  # type: ignore[attr-defined]
                success = sum(1 for r in getattr(response, "responses", []) if getattr(r, "success", False))
                failure = sum(1 for r in getattr(response, "responses", []) if not getattr(r, "success", False))
                logger.info(
                    "FCM send_each: success_count=%s failure_count=%s title=%s",
                    success,
                    failure,
                    title,
                )
                return {
                    "success": True,
                    "success_count": success,
                    "failure_count": failure,
                    "responses": [getattr(r, "__dict__", {}) for r in getattr(response, "responses", [])],
                }
            else:
                success = 0
                failure = 0
                responses = []
                for m in messages:
                    try:
                        msg_id = messaging.send(m, dry_run=False)
                        success += 1
                        responses.append({"success": True, "message_id": msg_id})
                    except Exception as ex:
                        failure += 1
                        responses.append({"success": False, "error": str(ex)})
                logger.info(
                    "FCM send(loop): success_count=%s failure_count=%s title=%s",
                    success,
                    failure,
                    title,
                )
                return {
                    "success": True,
                    "success_count": success,
                    "failure_count": failure,
                    "responses": responses,
                }
    except Exception as e:
        logger.exception("Failed to send FCM")
        return {"success": False, "error": str(e)}
