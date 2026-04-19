from datetime import date as DateType

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.response import ok
from app.core.timezone import utc_to_shanghai
from app.deps import get_current_user, get_db
from app.models.booking import Booking
from app.models.user import User
from app.schemas.room import AvailabilityOut, RoomOut, SlotTaken, UserSimple
from app.services import permission_service

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", summary="我的可见会议室列表")
def list_rooms(
    keyword: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rooms = permission_service.get_visible_rooms(db, current_user.id, keyword=keyword)
    return ok([RoomOut.model_validate(r).model_dump() for r in rooms])


@router.get("/{room_id}", summary="会议室详情")
def get_room(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    room = permission_service.get_room_or_404(db, room_id)
    if not permission_service.check_room_visible(db, current_user.id, room_id):
        raise BusinessException(40301, "无权访问该会议室")
    return ok(RoomOut.model_validate(room).model_dump())


@router.get("/{room_id}/availability", summary="查询某日会议室占用情况")
def room_availability(
    room_id: int,
    date: DateType = Query(..., description="查询日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    room = permission_service.get_room_or_404(db, room_id)
    if room.status != 1:
        raise BusinessException(40401, "会议室已停用")
    if not permission_service.check_room_visible(db, current_user.id, room_id):
        raise BusinessException(40301, "无权访问该会议室")

    bookings = (
        db.query(Booking)
        .filter(Booking.room_id == room_id, Booking.date == date, Booking.status == 1)
        .order_by(Booking.start_at)
        .all()
    )

    # Batch-load users
    user_ids = {b.user_id for b in bookings}
    users_map: dict[int, User] = {}
    if user_ids:
        users_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    slots: list[SlotTaken] = []
    for b in bookings:
        u = users_map.get(b.user_id)
        slots.append(
            SlotTaken(
                booking_id=b.id,
                start_at=utc_to_shanghai(b.start_at),
                end_at=utc_to_shanghai(b.end_at),
                user=UserSimple.model_validate(u) if u else UserSimple(id=b.user_id),
                preset=b.preset,
                title=b.title,
            )
        )

    result = AvailabilityOut(room_id=room_id, date=date, slots_taken=slots)
    return ok(result.model_dump())
