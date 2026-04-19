"""Import all models so Alembic autogenerate can discover them via Base.metadata."""

from app.models.base import Base
from app.models.admin_user import AdminUser
from app.models.booking import Booking
from app.models.department import Department
from app.models.notify import NotifyLog, NotifyQuota, OperationLog
from app.models.permission import RoomDeptPermission, RoomUserPermission
from app.models.recurrence import BookingRecurrence
from app.models.room import Room
from app.models.system_config import SystemConfig
from app.models.user import User

__all__ = [
    "Base",
    "AdminUser",
    "Booking",
    "BookingRecurrence",
    "Department",
    "NotifyLog",
    "NotifyQuota",
    "OperationLog",
    "Room",
    "RoomDeptPermission",
    "RoomUserPermission",
    "SystemConfig",
    "User",
]
