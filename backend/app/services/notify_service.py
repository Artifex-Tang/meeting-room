"""
T-BE-17: notify_service

Responsibilities:
- report_subscribe: update notify_quota from subscribe-report results
- enqueue_booking_success: create notify_log entries after booking created
- enqueue_booking_cancelled: create notify_log entry after admin cancel
- _try_send_log: check quota → call WeChat API → update log status
- process_pending_logs: scheduler job (T-BE-18) — scan + send pending logs

Rules (CLAUDE.md / SPEC §12):
- Notification failure MUST NOT block the booking main flow
- Enqueue only AFTER the booking transaction commits
- cancelled_by_admin triggers notification; user self-cancel does NOT
- Idempotent: at most one non-skipped log per (booking_id, scene)
"""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.timezone import utc_to_shanghai
from app.models.booking import Booking
from app.models.notify import NotifyLog, NotifyQuota
from app.models.room import Room
from app.models.user import User
from app.services.config_service import get, get_int

logger = logging.getLogger(__name__)

# notify_log.status values
_STATUS_PENDING = 0
_STATUS_SENT = 1
_STATUS_FAILED = 2
_STATUS_SKIPPED = 3

# WeChat subscribeMessage send URL template
_WX_SEND_URL = "https://api.weixin.qq.com/cgi-bin/message/subscribe/send"
_WX_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"

# In-process access_token cache {token: str, expire_at: datetime}
_access_token_cache: dict = {}


# ── Subscribe report (T-BE-17) ────────────────────────────────────────────────

def report_subscribe(db: Session, user_id: int, results: dict[str, str]) -> dict[str, int]:
    """
    Update notify_quota based on wx.requestSubscribeMessage results.
    results = {"booking_success": "accept"|"reject"|"ban", ...}
    Returns the current quota for all affected template keys.
    """
    quota_cap = get_int(db, "notify_quota_cap", 10)
    for template_key, status in results.items():
        if status != "accept":
            continue
        existing = (
            db.query(NotifyQuota)
            .filter(NotifyQuota.user_id == user_id, NotifyQuota.template_key == template_key)
            .first()
        )
        if existing:
            existing.quota = min(existing.quota + 1, quota_cap)
        else:
            db.add(NotifyQuota(user_id=user_id, template_key=template_key, quota=1))
    db.commit()
    return get_quota(db, user_id)


def get_quota(db: Session, user_id: int) -> dict[str, int]:
    """Return remaining quota per template key for user."""
    rows = db.query(NotifyQuota).filter(NotifyQuota.user_id == user_id).all()
    return {r.template_key: r.quota for r in rows}


# ── Enqueueing (T-BE-19) ──────────────────────────────────────────────────────

def enqueue_booking_success(db: Session, booking: Booking) -> None:
    """
    Called after booking transaction commits.
    Creates notify_log for booking_success (immediate) and booking_upcoming (scheduled).
    Errors are caught and logged — never block the caller.
    """
    try:
        _ensure_no_duplicate(db, booking.id, "booking_success")
        log = NotifyLog(
            user_id=booking.user_id,
            booking_id=booking.id,
            template_key="booking_success",
            scene="booking_success",
            status=_STATUS_PENDING,
            planned_at=None,
        )
        db.add(log)
        db.flush()

        # Try to send immediately
        _try_send_log(db, log)
        db.commit()

        # Upcoming: schedule at start_at - notify_upcoming_minutes
        _enqueue_upcoming(db, booking)
    except Exception:
        logger.exception("enqueue_booking_success failed for booking %d", booking.id)
        try:
            db.rollback()
        except Exception:
            pass


def _enqueue_upcoming(db: Session, booking: Booking) -> None:
    """Create a scheduled upcoming log — no send attempt (scheduler handles it)."""
    try:
        _ensure_no_duplicate(db, booking.id, "booking_upcoming")
        minutes = get_int(db, "notify_upcoming_minutes", 15)
        planned_at_utc = booking.start_at - timedelta(minutes=minutes)
        log = NotifyLog(
            user_id=booking.user_id,
            booking_id=booking.id,
            template_key="booking_upcoming",
            scene="booking_upcoming",
            status=_STATUS_PENDING,
            planned_at=planned_at_utc,
        )
        db.add(log)
        db.commit()
    except Exception:
        logger.exception("_enqueue_upcoming failed for booking %d", booking.id)
        try:
            db.rollback()
        except Exception:
            pass


def enqueue_booking_cancelled(db: Session, booking: Booking) -> None:
    """
    Called after admin cancel commits.
    Creates notify_log for booking_cancelled and tries to send immediately.
    Also marks any pending upcoming log as skipped.
    """
    try:
        # Cancel any pending upcoming notification for this booking
        db.query(NotifyLog).filter(
            NotifyLog.booking_id == booking.id,
            NotifyLog.scene == "booking_upcoming",
            NotifyLog.status == _STATUS_PENDING,
        ).update({"status": _STATUS_SKIPPED})

        _ensure_no_duplicate(db, booking.id, "booking_cancelled")
        log = NotifyLog(
            user_id=booking.user_id,
            booking_id=booking.id,
            template_key="booking_cancelled",
            scene="booking_cancelled",
            status=_STATUS_PENDING,
            planned_at=None,
        )
        db.add(log)
        db.flush()
        _try_send_log(db, log)
        db.commit()
    except Exception:
        logger.exception("enqueue_booking_cancelled failed for booking %d", booking.id)
        try:
            db.rollback()
        except Exception:
            pass


# ── Send logic ────────────────────────────────────────────────────────────────

def _try_send_log(db: Session, log: NotifyLog) -> None:
    """
    Check quota → build payload → call WeChat → update log status.
    Uses a new transaction-safe approach: all writes go through the same session.
    Errors mark the log as failed; nothing is raised to the caller.
    """
    from app.config import settings

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    template_id = get(db, f"wx_tpl_{log.scene}", "")
    if not template_id:
        logger.debug("No template_id for scene %s — skipping", log.scene)
        log.status = _STATUS_SKIPPED
        return

    # Check + deduct quota
    quota_row = (
        db.query(NotifyQuota)
        .filter(
            NotifyQuota.user_id == log.user_id,
            NotifyQuota.template_key == log.scene,
        )
        .with_for_update()
        .first()
    )
    if not quota_row or quota_row.quota <= 0:
        logger.debug("No quota for user %d scene %s — skipping", log.user_id, log.scene)
        log.status = _STATUS_SKIPPED
        return

    quota_row.quota -= 1

    # Build payload
    payload = _build_payload(db, log)

    # Get user openid
    user = db.get(User, log.user_id)
    if not user or not user.openid:
        log.status = _STATUS_SKIPPED
        return

    if settings.wechat_mock:
        logger.info(
            "[MOCK] notify send: user=%d scene=%s openid=%s data=%s",
            log.user_id, log.scene, user.openid, payload,
        )
        log.status = _STATUS_SENT
        log.sent_at = now_utc
        return

    # Real WeChat send
    try:
        access_token = _get_access_token(settings)
        resp = httpx.post(
            _WX_SEND_URL,
            params={"access_token": access_token},
            json={
                "touser": user.openid,
                "template_id": template_id,
                "page": "pages/booking/detail",
                "data": payload,
            },
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("errcode", 0) == 0:
            log.status = _STATUS_SENT
            log.sent_at = now_utc
        else:
            errmsg = f"{result.get('errcode')}: {result.get('errmsg')}"
            log.errmsg = errmsg
            # Permanent failures (template error, user blocked, etc.) — no retry
            log.status = _STATUS_FAILED
            logger.warning("WeChat send failed (permanent) for log %d: %s", log.id, errmsg)
    except httpx.HTTPError as e:
        # Network/timeout — scheduler will retry
        log.status = _STATUS_PENDING
        log.errmsg = str(e)[:500]
        logger.warning("WeChat send HTTP error for log %d: %s", log.id, e)


def _build_payload(db: Session, log: NotifyLog) -> dict:
    """Build template data dict based on scene."""
    if not log.booking_id:
        return {}

    booking = db.get(Booking, log.booking_id)
    if not booking:
        return {}

    room = db.get(Room, booking.room_id)
    room_name = room.name if room else "未知会议室"

    start_sh = utc_to_shanghai(booking.start_at)
    end_sh = utc_to_shanghai(booking.end_at)
    time_str = f"{start_sh.strftime('%Y-%m-%d %H:%M')}-{end_sh.strftime('%H:%M')}"

    if log.scene == "booking_success":
        return {
            "thing1": {"value": room_name[:20]},
            "date2": {"value": time_str[:20]},
            "thing3": {"value": (booking.title or "会议")[:20]},
            "thing4": {"value": "如需取消请提前操作"[:20]},
        }
    elif log.scene == "booking_upcoming":
        return {
            "thing1": {"value": room_name[:20]},
            "time2": {"value": start_sh.strftime("%H:%M")},
            "thing3": {"value": (booking.title or "会议")[:20]},
            "thing4": {"value": (room.location or "")[:20] if room else ""},
        }
    elif log.scene == "booking_cancelled":
        canceller = db.get(User, booking.cancelled_by) if booking.cancelled_by else None
        canceller_name = "管理员"
        if canceller:
            canceller_name = canceller.real_name or canceller.nickname or "管理员"
        return {
            "thing1": {"value": room_name[:20]},
            "date2": {"value": time_str[:20]},
            "thing3": {"value": (booking.cancel_reason or "无")[:20]},
            "thing4": {"value": canceller_name[:20]},
        }
    return {}


def _ensure_no_duplicate(db: Session, booking_id: int, scene: str) -> None:
    """Raise if any log already exists for (booking_id, scene) — prevents double-enqueue."""
    existing = (
        db.query(NotifyLog)
        .filter(NotifyLog.booking_id == booking_id, NotifyLog.scene == scene)
        .first()
    )
    if existing:
        raise ValueError(f"Duplicate notify_log for booking {booking_id} scene {scene}")


# ── Scheduler job (T-BE-18) ──────────────────────────────────────────────────

def process_pending_logs(db: Session) -> int:
    """
    Called by the scheduler every minute.
    Scans notify_log for status=0 where planned_at <= NOW (or planned_at IS NULL).
    Returns count of processed entries.
    """
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    pending = (
        db.query(NotifyLog)
        .filter(
            NotifyLog.status == _STATUS_PENDING,
            (NotifyLog.planned_at.is_(None)) | (NotifyLog.planned_at <= now_utc),
        )
        .limit(100)
        .all()
    )

    if not pending:
        return 0

    count = 0
    for log in pending:
        try:
            _try_send_log(db, log)
            db.commit()
            count += 1
        except Exception:
            logger.exception("Error processing notify_log %d", log.id)
            try:
                db.rollback()
            except Exception:
                pass

    return count


# ── WeChat access_token helper ────────────────────────────────────────────────

def _get_access_token(settings) -> str:
    global _access_token_cache
    now = datetime.now(timezone.utc)
    if _access_token_cache.get("token") and _access_token_cache.get("expire_at", now) > now:
        return _access_token_cache["token"]

    resp = httpx.get(
        _WX_TOKEN_URL,
        params={
            "grant_type": "client_credential",
            "appid": settings.wechat_appid,
            "secret": settings.wechat_secret,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"WeChat token error: {data}")

    _access_token_cache = {
        "token": data["access_token"],
        "expire_at": now + timedelta(seconds=data.get("expires_in", 7200) - 300),
    }
    return _access_token_cache["token"]
