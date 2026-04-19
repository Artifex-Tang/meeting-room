"""
booking_service.create follows SPEC §5.4 validation order strictly:
1. Auth (handled by get_current_user dependency)
2. Room exists + enabled
3. User permission
4. Time range valid (30-min aligned, 08:00–24:00, start < end)
5. Max duration ≤ max_booking_hours  (preset exempt)
6. Daily count < max_bookings_per_day
7. Transaction: SELECT room FOR UPDATE → conflict check → INSERT
"""
import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.timezone import SHANGHAI_TZ, utc_to_shanghai
from app.models.booking import Booking
from app.models.room import Room
from app.models.user import User
from app.services import config_service, permission_service

logger = logging.getLogger(__name__)

# ── Preset definitions (SPEC §3.1.1) ────────────────────────────────────────
PRESETS: dict[str, tuple[str, str]] = {
    "morning":   ("08:00", "12:00"),
    "noon":      ("12:00", "14:30"),
    "afternoon": ("14:30", "18:00"),
    "evening":   ("18:00", "24:00"),
    "daytime":   ("08:00", "18:00"),
    "allday":    ("08:00", "24:00"),
}


def _parse_hhmm(s: str) -> time | None:
    """Parse 'HH:MM'; '24:00' → None (midnight of next day)."""
    if s == "24:00":
        return None
    h, m = int(s[:2]), int(s[3:5])
    return time(h, m)


def _to_utc(booking_date: date, t: time | None) -> datetime:
    """Combine date + Shanghai time → naive UTC datetime for DB storage."""
    if t is None:  # 24:00 → next-day 00:00 in Shanghai
        local = datetime.combine(booking_date + timedelta(days=1), time(0, 0), tzinfo=SHANGHAI_TZ)
    else:
        local = datetime.combine(booking_date, t, tzinfo=SHANGHAI_TZ)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _validate_time_range(start: time, end: time | None) -> None:
    for t, label in [(start, "开始时间"), (end, "结束时间")]:
        if t is not None and (t.minute % 30 != 0 or t.second != 0):
            raise BusinessException(40001, f"{label}须对齐到 30 分钟边界")
    if start < time(8, 0):
        raise BusinessException(40001, "开始时间不得早于 08:00")
    if start > time(23, 30):
        raise BusinessException(40001, "开始时间不得晚于 23:30")
    if end is not None:
        if end < time(8, 30):
            raise BusinessException(40001, "结束时间不得早于 08:30")
        if end <= start:
            raise BusinessException(40001, "结束时间须晚于开始时间")


# ── Public API ───────────────────────────────────────────────────────────────

def create(db: Session, user_id: int, req) -> Booking:
    # 2. Room exists + enabled
    room = db.get(Room, req.room_id)
    if room is None or room.status != 1:
        raise BusinessException(40401, "会议室不存在或已停用")

    # 3. Permission
    if not permission_service.check_room_visible(db, user_id, req.room_id):
        raise BusinessException(40301, "无权访问该会议室")

    # 4. Resolve + validate time interval
    is_preset = req.preset is not None
    if is_preset:
        if req.preset not in PRESETS:
            raise BusinessException(40001, f"无效的预设时段: {req.preset}")
        s_str, e_str = PRESETS[req.preset]
    else:
        if not req.start_time or not req.end_time:
            raise BusinessException(40001, "自定义时段须同时提供 start_time 与 end_time")
        s_str, e_str = req.start_time, req.end_time

    start_t = _parse_hhmm(s_str)
    end_t = _parse_hhmm(e_str)
    if start_t is None:
        raise BusinessException(40001, "开始时间不得为 24:00")
    _validate_time_range(start_t, end_t)

    start_at = _to_utc(req.date, start_t)
    end_at = _to_utc(req.date, end_t)

    # 5. Max duration (preset exempt)
    if not is_preset:
        max_h = config_service.get_int(db, "max_booking_hours", 16)
        duration_h = (end_at - start_at).total_seconds() / 3600
        if duration_h > max_h:
            raise BusinessException(
                42201, f"超过最长预订时长 {max_h} 小时", {"rule": "max_booking_hours"}
            )

    # 6. Daily booking count
    max_day = config_service.get_int(db, "max_bookings_per_day", 3)
    day_count = (
        db.query(func.count(Booking.id))
        .filter(Booking.user_id == user_id, Booking.date == req.date, Booking.status == 1)
        .scalar()
        or 0
    )
    if day_count >= max_day:
        raise BusinessException(
            42201, f"超过每日预订次数上限 {max_day}", {"rule": "max_bookings_per_day"}
        )

    # 7. Transaction: lock room row → conflict check → insert
    db.execute(
        text("SELECT id FROM room WHERE id = :id AND status = 1 FOR UPDATE"),
        {"id": req.room_id},
    )
    conflict = (
        db.query(Booking)
        .filter(
            Booking.room_id == req.room_id,
            Booking.status == 1,
            Booking.start_at < end_at,
            Booking.end_at > start_at,
        )
        .first()
    )
    if conflict:
        cu = db.get(User, conflict.user_id)
        raise BusinessException(
            40901,
            "时间冲突",
            {
                "conflict_with": {
                    "booking_id": conflict.id,
                    "user": (cu.real_name or cu.nickname) if cu else None,
                    "start_at": utc_to_shanghai(conflict.start_at).isoformat(),
                    "end_at": utc_to_shanghai(conflict.end_at).isoformat(),
                }
            },
        )

    booking = Booking(
        room_id=req.room_id,
        user_id=user_id,
        date=req.date,
        start_at=start_at,
        end_at=end_at,
        preset=req.preset,
        title=req.title,
        attendees=getattr(req, "attendees", None),
        status=1,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    logger.info("booking %d created by user %d", booking.id, user_id)

    # Enqueue notifications AFTER commit — failure must not block main flow (CLAUDE.md)
    try:
        from app.services.notify_service import enqueue_booking_success
        enqueue_booking_success(db, booking)
    except Exception:
        logger.exception("notify enqueue failed for booking %d — booking unaffected", booking.id)

    return booking


def get_booking(db: Session, booking_id: int, user_id: int) -> Booking:
    b = db.get(Booking, booking_id)
    if b is None:
        raise BusinessException(40401, "预订不存在")
    if b.user_id != user_id:
        raise BusinessException(40301, "无权查看该预订")
    return b


def list_bookings(
    db: Session,
    user_id: int,
    status_filter: int | None = None,   # 1=active, 0=cancelled, None=all
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Booking], int]:
    q = db.query(Booking).filter(Booking.user_id == user_id)
    if status_filter is not None:
        q = q.filter(Booking.status == status_filter)
    if start_date:
        q = q.filter(Booking.date >= start_date)
    if end_date:
        q = q.filter(Booking.date <= end_date)
    total = q.count()
    items = (
        q.order_by(Booking.date.desc(), Booking.start_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def cancel_by_user(db: Session, booking_id: int, user_id: int, reason: str | None) -> Booking:
    b = db.get(Booking, booking_id)
    if b is None or b.status != 1:
        raise BusinessException(40401, "预订不存在或已取消")
    if b.user_id != user_id:
        raise BusinessException(40301, "只能取消自己的预订")

    cancel_h = config_service.get_int(db, "cancel_advance_hours", 2)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    remaining_s = (b.start_at - now_utc).total_seconds()
    if remaining_s < cancel_h * 3600:
        raise BusinessException(
            42201,
            f"距开始时间不足 {cancel_h} 小时，无法取消",
            {"rule": "cancel_advance_hours"},
        )

    b.status = 0
    b.cancel_reason = reason
    b.cancelled_by = user_id
    b.cancel_source = 1  # user self-cancel
    b.cancelled_at = now_utc
    db.commit()
    db.refresh(b)
    return b
