"""
Admin business logic: rooms CRUD, users/depts, bookings overview,
admin cancel, system config, stats, password change.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.security import hash_password, verify_password
from app.core.timezone import utc_to_shanghai
from app.models.admin_user import AdminUser
from app.models.booking import Booking
from app.models.department import Department
from app.models.permission import RoomDeptPermission, RoomUserPermission
from app.models.room import Room
from app.models.system_config import SystemConfig
from app.models.user import User
from app.services import permission_service

logger = logging.getLogger(__name__)

_CONFIG_KEYS = {
    "advance_booking_days", "max_booking_hours", "max_bookings_per_day",
    "cancel_advance_hours", "max_recurrence_months",
    "notify_quota_cap", "notify_upcoming_minutes",
    "tpl_booking_success", "tpl_booking_upcoming", "tpl_booking_cancelled",
}


# ── Rooms ─────────────────────────────────────────────────────────────────────

def list_rooms(
    db: Session,
    keyword: str | None,
    status: int | None,
    page: int,
    page_size: int,
) -> tuple[list[Room], int]:
    q = db.query(Room)
    if status is not None:
        q = q.filter(Room.status == status)
    if keyword:
        q = q.filter(Room.name.contains(keyword))
    total = q.count()
    items = q.order_by(Room.id).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def create_room(db: Session, data) -> Room:
    room = Room(
        name=data.name,
        location=data.location,
        capacity=data.capacity,
        facilities=data.facilities,
        description=data.description,
        status=data.status,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def update_room(db: Session, room_id: int, data) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise BusinessException(40401, "会议室不存在")
    for field in ("name", "location", "capacity", "facilities", "description", "status"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(room, field, val)
    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, room_id: int) -> None:
    """Soft-delete: set status=0. Reject if active future bookings exist."""
    room = db.get(Room, room_id)
    if room is None:
        raise BusinessException(40401, "会议室不存在")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    future_count = (
        db.query(func.count(Booking.id))
        .filter(
            Booking.room_id == room_id,
            Booking.status == 1,
            Booking.start_at > now_utc,
        )
        .scalar()
        or 0
    )
    if future_count > 0:
        raise BusinessException(
            40901,
            f"该会议室有 {future_count} 条未来预订，请先取消后再停用",
            {"future_bookings": future_count},
        )

    room.status = 0
    db.commit()


# ── Permissions ───────────────────────────────────────────────────────────────

def get_room_permissions(db: Session, room_id: int) -> dict:
    _require_room(db, room_id)
    user_perms = (
        db.query(RoomUserPermission)
        .filter(RoomUserPermission.room_id == room_id)
        .all()
    )
    dept_perms = (
        db.query(RoomDeptPermission)
        .filter(RoomDeptPermission.room_id == room_id)
        .all()
    )
    user_ids = [p.user_id for p in user_perms]
    dept_ids = [p.dept_id for p in dept_perms]

    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    depts = db.query(Department).filter(Department.id.in_(dept_ids)).all() if dept_ids else []
    return {"users": users, "depts": depts}


def grant_users(db: Session, room_id: int, user_ids: list[int], admin_id: int) -> None:
    _require_room(db, room_id)
    for uid in user_ids:
        permission_service.grant_user(db, room_id, uid, granted_by=admin_id)


def revoke_user(db: Session, room_id: int, user_id: int) -> None:
    _require_room(db, room_id)
    permission_service.revoke_user(db, room_id, user_id)


def grant_depts(db: Session, room_id: int, dept_ids: list[int], admin_id: int) -> None:
    _require_room(db, room_id)
    for did in dept_ids:
        permission_service.grant_dept(db, room_id, did, granted_by=admin_id)


def revoke_dept(db: Session, room_id: int, dept_id: int) -> None:
    _require_room(db, room_id)
    permission_service.revoke_dept(db, room_id, dept_id)


def get_user_rooms(db: Session, user_id: int) -> list[Room]:
    _require_user(db, user_id)
    room_ids = permission_service.get_visible_room_ids(db, user_id)
    if not room_ids:
        return []
    return db.query(Room).filter(Room.id.in_(room_ids)).order_by(Room.id).all()


# ── Users ─────────────────────────────────────────────────────────────────────

def list_users(
    db: Session,
    keyword: str | None,
    dept_id: int | None,
    status: int | None,
    page: int,
    page_size: int,
) -> tuple[list[User], int]:
    q = db.query(User)
    if status is not None:
        q = q.filter(User.status == status)
    if dept_id is not None:
        q = q.filter(User.dept_id == dept_id)
    if keyword:
        q = q.filter(
            User.nickname.contains(keyword) | User.real_name.contains(keyword)
        )
    total = q.count()
    items = q.order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def update_user(db: Session, user_id: int, data) -> User:
    user = _require_user(db, user_id)
    if data.real_name is not None:
        user.real_name = data.real_name
    if data.dept_id is not None:
        user.dept_id = data.dept_id
    if data.status is not None:
        user.status = data.status
    db.commit()
    db.refresh(user)
    return user


# ── Departments ───────────────────────────────────────────────────────────────

def list_departments(db: Session) -> list[Department]:
    return db.query(Department).order_by(Department.id).all()


def create_department(db: Session, data) -> Department:
    dept = Department(name=data.name, parent_id=data.parent_id)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def update_department(db: Session, dept_id: int, data) -> Department:
    dept = _require_dept(db, dept_id)
    if data.name is not None:
        dept.name = data.name
    if data.parent_id is not None:
        dept.parent_id = data.parent_id
    db.commit()
    db.refresh(dept)
    return dept


def delete_department(db: Session, dept_id: int) -> None:
    dept = _require_dept(db, dept_id)
    # Unlink users from this dept
    db.query(User).filter(User.dept_id == dept_id).update({"dept_id": None})
    db.delete(dept)
    db.commit()


# ── Bookings ──────────────────────────────────────────────────────────────────

def list_bookings(
    db: Session,
    room_id: int | None,
    user_id: int | None,
    date_from: date | None,
    date_to: date | None,
    status: int | None,
    page: int,
    page_size: int,
) -> tuple[list[Booking], int]:
    q = db.query(Booking)
    if room_id is not None:
        q = q.filter(Booking.room_id == room_id)
    if user_id is not None:
        q = q.filter(Booking.user_id == user_id)
    if date_from is not None:
        q = q.filter(Booking.date >= date_from)
    if date_to is not None:
        q = q.filter(Booking.date <= date_to)
    if status is not None:
        q = q.filter(Booking.status == status)
    total = q.count()
    items = (
        q.order_by(Booking.date.desc(), Booking.start_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def admin_cancel_booking(db: Session, booking_id: int, admin_id: int, reason: str | None) -> Booking:
    b = db.get(Booking, booking_id)
    if b is None or b.status != 1:
        raise BusinessException(40401, "预订不存在或已取消")

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    b.status = 0
    b.cancel_reason = reason
    b.cancelled_by = admin_id
    b.cancel_source = 2   # admin cancel
    b.cancelled_at = now_utc
    db.commit()
    db.refresh(b)
    logger.info("booking %d cancelled by admin %d", booking_id, admin_id)

    # Enqueue cancelled notification AFTER commit (user self-cancel does NOT notify)
    from app.services.notify_service import enqueue_booking_cancelled
    enqueue_booking_cancelled(db, b)

    return b


# ── Config ────────────────────────────────────────────────────────────────────

def get_config(db: Session) -> dict[str, str]:
    rows = db.query(SystemConfig).filter(SystemConfig.config_key.in_(_CONFIG_KEYS)).all()
    return {r.config_key: r.value for r in rows}


def update_config(db: Session, data) -> dict[str, str]:
    updates = {
        k: str(v)
        for k, v in {
            "advance_booking_days":    data.advance_booking_days,
            "max_booking_hours":       data.max_booking_hours,
            "max_bookings_per_day":    data.max_bookings_per_day,
            "cancel_advance_hours":    data.cancel_advance_hours,
            "max_recurrence_months":   data.max_recurrence_months,
            "notify_quota_cap":        data.notify_quota_cap,
            "notify_upcoming_minutes": data.notify_upcoming_minutes,
            "tpl_booking_success":     data.tpl_booking_success,
            "tpl_booking_upcoming":    data.tpl_booking_upcoming,
            "tpl_booking_cancelled":   data.tpl_booking_cancelled,
        }.items()
        if v is not None
    }
    for key, value in updates.items():
        row = db.get(SystemConfig, key)
        if row:
            row.value = value
        else:
            db.add(SystemConfig(config_key=key, value=value))
    db.commit()
    return get_config(db)


# ── Stats ─────────────────────────────────────────────────────────────────────

def stats_overview(db: Session) -> dict:
    today = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=today.weekday())

    today_count = (
        db.query(func.count(Booking.id))
        .filter(Booking.date == today, Booking.status == 1)
        .scalar()
        or 0
    )
    week_count = (
        db.query(func.count(Booking.id))
        .filter(Booking.date >= week_start, Booking.status == 1)
        .scalar()
        or 0
    )

    top_raw = (
        db.query(Booking.room_id, func.count(Booking.id).label("cnt"))
        .filter(Booking.status == 1)
        .group_by(Booking.room_id)
        .order_by(func.count(Booking.id).desc())
        .limit(5)
        .all()
    )
    room_ids = [row.room_id for row in top_raw]
    rooms = {r.id: r.name for r in db.query(Room).filter(Room.id.in_(room_ids)).all()} if room_ids else {}
    top_rooms = [
        {"room_id": row.room_id, "room_name": rooms.get(row.room_id, ""), "count": row.cnt}
        for row in top_raw
    ]

    return {
        "today_bookings": today_count,
        "week_bookings": week_count,
        "top_rooms": top_rooms,
    }


# ── Admin password change ─────────────────────────────────────────────────────

def change_admin_password(db: Session, admin_id: int, old_password: str, new_password: str) -> None:
    admin = db.get(AdminUser, admin_id)
    if admin is None:
        raise BusinessException(40401, "管理员不存在")
    if not verify_password(old_password, admin.password_hash):
        raise BusinessException(40001, "原密码错误")
    if len(new_password) < 6:
        raise BusinessException(40001, "新密码长度不得少于 6 位")
    admin.password_hash = hash_password(new_password)
    admin.must_change_password = 0
    db.commit()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _require_room(db: Session, room_id: int) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise BusinessException(40401, "会议室不存在")
    return room


def _require_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise BusinessException(40401, "用户不存在")
    return user


def _require_dept(db: Session, dept_id: int) -> Department:
    dept = db.get(Department, dept_id)
    if dept is None:
        raise BusinessException(40401, "部门不存在")
    return dept
