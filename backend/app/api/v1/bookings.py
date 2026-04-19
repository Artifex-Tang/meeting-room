from datetime import date as DateType

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import ok
from app.core.timezone import utc_to_shanghai
from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.booking import BookingCreateRequest, BookingListOut, BookingOut, CancelRequest
from app.services import booking_service

router = APIRouter(prefix="/bookings", tags=["bookings"])


def _serialize(b) -> dict:
    """Convert Booking ORM → dict with Shanghai-timezone datetimes."""
    d = BookingOut.model_validate(b).model_dump()
    d["start_at"] = utc_to_shanghai(b.start_at).isoformat()
    d["end_at"] = utc_to_shanghai(b.end_at).isoformat()
    if b.cancelled_at:
        d["cancelled_at"] = utc_to_shanghai(b.cancelled_at).isoformat()
    return d


@router.post("", summary="创建单次预订")
def create_booking(
    req: BookingCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    booking = booking_service.create(db, current_user.id, req)
    return ok(_serialize(booking))


@router.get("", summary="我的预订列表")
def list_bookings(
    status: str | None = Query(None, description="active | cancelled | all"),
    start_date: DateType | None = Query(None),
    end_date: DateType | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    status_filter: int | None = None
    if status == "active":
        status_filter = 1
    elif status == "cancelled":
        status_filter = 0
    # "all" or None → no filter

    items, total = booking_service.list_bookings(
        db, current_user.id, status_filter, start_date, end_date, page, page_size
    )
    return ok({"list": [_serialize(b) for b in items], "total": total, "page": page})


@router.get("/{booking_id}", summary="预订详情")
def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    b = booking_service.get_booking(db, booking_id, current_user.id)
    return ok(_serialize(b))


@router.post("/{booking_id}/cancel", summary="取消预订")
def cancel_booking(
    booking_id: int,
    req: CancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    b = booking_service.cancel_by_user(db, booking_id, current_user.id, req.reason)
    return ok(_serialize(b))
