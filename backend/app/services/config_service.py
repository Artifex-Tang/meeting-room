import logging

from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

# Default fallback values — must match alembic/versions/0001_init.py inserts
_DEFAULTS: dict[str, str] = {
    "advance_booking_days":    "7",
    "cancel_advance_hours":    "2",
    "max_booking_hours":       "16",
    "max_bookings_per_day":    "3",
    "max_recurrence_months":   "6",
    "notify_quota_cap":        "10",
    "notify_upcoming_minutes": "15",
    "tpl_booking_success":     "",
    "tpl_booking_upcoming":    "",
    "tpl_booking_cancelled":   "",
}


def get(db: Session, key: str, default: str = "") -> str:
    row = db.get(SystemConfig, key)
    if row is None:
        return _DEFAULTS.get(key, default)
    return row.value


def get_int(db: Session, key: str, default: int = 0) -> int:
    return int(get(db, key, str(default)))
