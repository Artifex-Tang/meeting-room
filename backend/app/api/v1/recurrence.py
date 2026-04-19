from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import ok
from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.recurrence import RecurrenceCreateRequest
from app.services import recurrence_service
from app.api.v1.bookings import _serialize

router = APIRouter(prefix="/bookings/recurrence", tags=["recurrence"])


@router.post("", summary="创建周期性预订")
def create_recurrence(
    req: RecurrenceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rec, bookings = recurrence_service.expand_and_create(db, current_user.id, req)
    return ok({
        "recurrence_id": rec.id,
        "booking_ids": [b.id for b in bookings],
        "count": len(bookings),
    })


@router.post("/{recurrence_id}/cancel", summary="取消周期规则全部未来实例")
def cancel_recurrence(
    recurrence_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    cancelled_count = recurrence_service.cancel_future(db, recurrence_id, current_user.id)
    return ok({"recurrence_id": recurrence_id, "cancelled_count": cancelled_count})
