"""
recurrence_service.expand_and_create follows SPEC §5.2:
1. Validate params (date range, time, permission)
2. Generate candidate dates by frequency
3. Transaction: lock room FOR UPDATE → check all conflicts → bulk insert
4. If any conflict: rollback + 40902
"""
import calendar
import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.timezone import SHANGHAI_TZ, utc_to_shanghai
from app.models.booking import Booking
from app.models.recurrence import BookingRecurrence
from app.models.room import Room
from app.models.user import User
from app.services import config_service, permission_service
from app.services.booking_service import _parse_hhmm, _to_utc, _validate_time_range

logger = logging.getLogger(__name__)


def _generate_dates(
    frequency: str,
    weekdays: list[int] | None,
    month_day: int | None,
    start_date: date,
    end_date: date,
) -> list[date]:
    """Generate all candidate dates in [start_date, end_date] matching the rule."""
    dates: list[date] = []
    d = start_date
    while d <= end_date:
        if frequency == "DAILY":
            dates.append(d)
        elif frequency == "WEEKLY":
            if d.weekday() in (weekdays or []):
                dates.append(d)
        elif frequency == "MONTHLY":
            # Skip months where month_day exceeds month length
            last = calendar.monthrange(d.year, d.month)[1]
            if month_day and d.day == month_day and month_day <= last:
                dates.append(d)
        d += timedelta(days=1)
    return dates


def _months_between(d1: date, d2: date) -> float:
    """Approximate month count d2 - d1 (for range limit check)."""
    return (d2.year - d1.year) * 12 + (d2.month - d1.month) + (d2.day - d1.day) / 31


def expand_and_create(db: Session, user_id: int, req) -> tuple[BookingRecurrence, list[Booking]]:
    """
    Validate, generate, conflict-check, and bulk-insert a recurrence rule.
    Returns (recurrence_record, list_of_bookings).
    Raises BusinessException 40902 if any date conflicts.
    """
    # 2. Room exists + enabled
    room = db.get(Room, req.room_id)
    if room is None or room.status != 1:
        raise BusinessException(40401, "会议室不存在或已停用")

    # 3. Permission
    if not permission_service.check_room_visible(db, user_id, req.room_id):
        raise BusinessException(40301, "无权访问该会议室")

    # 1. Date range
    if req.end_date < req.start_date:
        raise BusinessException(40001, "结束日期须不早于开始日期")
    max_months = config_service.get_int(db, "max_recurrence_months", 6)
    if _months_between(req.start_date, req.end_date) > max_months:
        raise BusinessException(
            40001,
            f"周期跨度不得超过 {max_months} 个月",
            {"rule": "max_recurrence_months"},
        )

    # 4. Time validation
    start_t = _parse_hhmm(req.start_time)
    end_t = _parse_hhmm(req.end_time)
    if start_t is None:
        raise BusinessException(40001, "开始时间不得为 24:00")
    _validate_time_range(start_t, end_t)

    # 2. Generate candidate dates
    dates = _generate_dates(
        req.frequency, req.weekdays, req.month_day, req.start_date, req.end_date
    )
    if not dates:
        raise BusinessException(40001, "展开后无有效日期，请检查频率与日期范围")

    max_day = config_service.get_int(db, "max_bookings_per_day", 3)

    # 3. Transaction: lock room FOR UPDATE
    db.execute(
        text("SELECT id FROM room WHERE id = :id AND status = 1 FOR UPDATE"),
        {"id": req.room_id},
    )

    # Per-date conflict + daily-count check
    conflicts: list[dict] = []
    # Track new bookings being added per date to correctly count daily totals
    new_per_day: dict[date, int] = {}

    for d in dates:
        start_at = _to_utc(d, start_t)
        end_at = _to_utc(d, end_t)

        # 6. Daily count (existing + already-planned in this batch)
        existing_count = (
            db.query(func.count(Booking.id))
            .filter(Booking.user_id == user_id, Booking.date == d, Booking.status == 1)
            .scalar()
            or 0
        )
        batch_count = new_per_day.get(d, 0)
        if existing_count + batch_count >= max_day:
            conflicts.append(
                {"date": d, "with_user": None, "start_at": req.start_time, "end_at": req.end_time,
                 "reason": "daily_limit"}
            )
            continue

        # 7. Overlap check
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
            conflicts.append({
                "date": d,
                "with_user": (cu.real_name or cu.nickname) if cu else None,
                "start_at": utc_to_shanghai(conflict.start_at).isoformat(),
                "end_at": utc_to_shanghai(conflict.end_at).isoformat(),
            })
        else:
            new_per_day[d] = batch_count + 1

    if conflicts:
        # Rollback handled by caller (or SQLAlchemy session expiry); just raise
        raise BusinessException(
            40902,
            "周期预订存在冲突",
            {"conflicts": [
                {
                    "date": str(c["date"]),
                    "with_user": c.get("with_user"),
                    "start_at": c.get("start_at"),
                    "end_at": c.get("end_at"),
                }
                for c in conflicts
            ]},
        )

    # Store time(0,0) for 24:00 end_time — convention: 00:00 in this field = next-day midnight
    stored_end_time = end_t if end_t is not None else time(0, 0)

    rec = BookingRecurrence(
        user_id=user_id,
        room_id=req.room_id,
        frequency=req.frequency,
        weekdays=",".join(str(w) for w in (req.weekdays or [])) or None,
        month_day=req.month_day,
        start_date=req.start_date,
        end_date=req.end_date,
        start_time=start_t,
        end_time=stored_end_time,
        title=req.title,
        status=1,
    )
    db.add(rec)
    db.flush()  # get rec.id without committing

    bookings: list[Booking] = []
    for d in dates:
        start_at = _to_utc(d, start_t)
        end_at = _to_utc(d, end_t)
        b = Booking(
            room_id=req.room_id,
            user_id=user_id,
            recurrence_id=rec.id,
            date=d,
            start_at=start_at,
            end_at=end_at,
            title=req.title,
            status=1,
        )
        db.add(b)
        bookings.append(b)

    db.commit()
    db.refresh(rec)
    for b in bookings:
        db.refresh(b)

    logger.info(
        "recurrence %d created by user %d: %d instances (%s → %s)",
        rec.id, user_id, len(bookings), req.start_date, req.end_date,
    )

    # Enqueue notifications AFTER commit — failure must not block main flow (CLAUDE.md)
    try:
        from app.services.notify_service import enqueue_booking_success
        for b in bookings:
            enqueue_booking_success(db, b)
    except Exception:
        logger.exception("notify enqueue failed for recurrence %d — bookings unaffected", rec.id)

    return rec, bookings


def cancel_future(db: Session, recurrence_id: int, user_id: int) -> int:
    """
    Cancel all future (date >= today UTC) instances of a recurrence owned by user_id.
    Returns count of cancelled bookings.
    """
    rec = db.get(BookingRecurrence, recurrence_id)
    if rec is None or rec.status != 1:
        raise BusinessException(40401, "周期预订规则不存在或已取消")
    if rec.user_id != user_id:
        raise BusinessException(40301, "只能取消自己的周期预订")

    today = datetime.now(timezone.utc).date()
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    future_bookings = (
        db.query(Booking)
        .filter(
            Booking.recurrence_id == recurrence_id,
            Booking.status == 1,
            Booking.date >= today,
            Booking.start_at > now_utc,
        )
        .all()
    )

    for b in future_bookings:
        b.status = 0
        b.cancelled_by = user_id
        b.cancel_source = 1
        b.cancelled_at = now_utc

    rec.status = 0
    db.commit()

    logger.info(
        "recurrence %d: %d future bookings cancelled by user %d",
        recurrence_id, len(future_bookings), user_id,
    )
    return len(future_bookings)
