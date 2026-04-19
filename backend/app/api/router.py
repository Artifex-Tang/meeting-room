from fastapi import APIRouter

from app.api.v1 import admin, auth, bookings, notify, recurrence, rooms, users
from app.core.response import ok

router = APIRouter()


@router.get("/ping", tags=["health"])
def ping() -> dict:
    return ok({"pong": True})


router.include_router(auth.router)
router.include_router(rooms.router)
router.include_router(admin.router)
router.include_router(notify.router)
router.include_router(recurrence.router)
router.include_router(bookings.router)
router.include_router(users.router)
