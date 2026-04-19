from datetime import date, time
from typing import Literal

from pydantic import BaseModel, model_validator


class RecurrenceCreateRequest(BaseModel):
    room_id: int
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY"]
    weekdays: list[int] | None = None   # 0=Mon … 6=Sun (Python weekday())
    month_day: int | None = None        # 1–31
    start_date: date
    end_date: date
    start_time: str                     # "HH:MM"
    end_time: str                       # "HH:MM" or "24:00"
    title: str | None = None

    @model_validator(mode="after")
    def _check_frequency_params(self) -> "RecurrenceCreateRequest":
        if self.frequency == "WEEKLY" and not self.weekdays:
            raise ValueError("WEEKLY 频率须提供 weekdays")
        if self.frequency == "MONTHLY" and self.month_day is None:
            raise ValueError("MONTHLY 频率须提供 month_day")
        return self


class ConflictItem(BaseModel):
    date: date
    with_user: str | None = None
    start_at: str
    end_at: str


class RecurrenceCreateOut(BaseModel):
    recurrence_id: int
    booking_ids: list[int]
    count: int


class RecurrenceCancelOut(BaseModel):
    recurrence_id: int
    cancelled_count: int
