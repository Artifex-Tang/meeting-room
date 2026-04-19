from datetime import datetime, timedelta, timezone

SHANGHAI_TZ = timezone(timedelta(hours=8))


def utc_to_shanghai(dt: datetime) -> datetime:
    """Attach UTC tzinfo to a naive DB datetime, then convert to +08:00."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SHANGHAI_TZ)


def shanghai_to_utc_naive(dt: datetime) -> datetime:
    """Convert a +08:00 aware datetime to a naive UTC datetime for DB storage."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SHANGHAI_TZ)
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
