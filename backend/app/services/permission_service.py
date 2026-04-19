import logging

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.permission import RoomDeptPermission, RoomUserPermission
from app.models.room import Room
from app.models.user import User

logger = logging.getLogger(__name__)


# ── Read helpers ─────────────────────────────────────────────────────────────

def get_visible_room_ids(db: Session, user_id: int) -> set[int]:
    """Union of directly-granted and dept-granted room IDs for a user."""
    direct = {
        r.room_id
        for r in db.query(RoomUserPermission.room_id)
        .filter(RoomUserPermission.user_id == user_id)
        .all()
    }

    user = db.get(User, user_id)
    dept_ids: set[int] = set()
    if user and user.dept_id:
        dept_ids.add(user.dept_id)

    dept = set()
    if dept_ids:
        dept = {
            r.room_id
            for r in db.query(RoomDeptPermission.room_id)
            .filter(RoomDeptPermission.dept_id.in_(dept_ids))
            .all()
        }

    return direct | dept


def check_room_visible(db: Session, user_id: int, room_id: int) -> bool:
    return room_id in get_visible_room_ids(db, user_id)


def get_visible_rooms(
    db: Session,
    user_id: int,
    keyword: str | None = None,
    status: int | None = 1,
) -> list[Room]:
    """Enabled rooms visible to the user, optional keyword filter."""
    visible_ids = get_visible_room_ids(db, user_id)
    if not visible_ids:
        return []

    q = db.query(Room).filter(Room.id.in_(visible_ids))
    if status is not None:
        q = q.filter(Room.status == status)
    if keyword:
        q = q.filter(Room.name.contains(keyword))
    return q.order_by(Room.id).all()


def get_room_or_404(db: Session, room_id: int) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise BusinessException(40401, "会议室不存在")
    return room


# ── Grant / Revoke ────────────────────────────────────────────────────────────

def grant_user(db: Session, room_id: int, user_id: int, granted_by: int) -> RoomUserPermission:
    existing = (
        db.query(RoomUserPermission)
        .filter(RoomUserPermission.room_id == room_id, RoomUserPermission.user_id == user_id)
        .first()
    )
    if existing:
        return existing
    perm = RoomUserPermission(room_id=room_id, user_id=user_id, granted_by=granted_by)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


def revoke_user(db: Session, room_id: int, user_id: int) -> None:
    db.query(RoomUserPermission).filter(
        RoomUserPermission.room_id == room_id, RoomUserPermission.user_id == user_id
    ).delete()
    db.commit()


def grant_dept(db: Session, room_id: int, dept_id: int, granted_by: int) -> RoomDeptPermission:
    existing = (
        db.query(RoomDeptPermission)
        .filter(RoomDeptPermission.room_id == room_id, RoomDeptPermission.dept_id == dept_id)
        .first()
    )
    if existing:
        return existing
    perm = RoomDeptPermission(room_id=room_id, dept_id=dept_id, granted_by=granted_by)
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


def revoke_dept(db: Session, room_id: int, dept_id: int) -> None:
    db.query(RoomDeptPermission).filter(
        RoomDeptPermission.room_id == room_id, RoomDeptPermission.dept_id == dept_id
    ).delete()
    db.commit()


def list_room_permissions(db: Session, room_id: int) -> dict:
    users = (
        db.query(RoomUserPermission)
        .filter(RoomUserPermission.room_id == room_id)
        .all()
    )
    depts = (
        db.query(RoomDeptPermission)
        .filter(RoomDeptPermission.room_id == room_id)
        .all()
    )
    return {
        "user_ids": [p.user_id for p in users],
        "dept_ids": [p.dept_id for p in depts],
    }
