from datetime import date, datetime

from pydantic import BaseModel, model_validator


class BookingCreateRequest(BaseModel):
    room_id: int
    date: date
    preset: str | None = None
    start_time: str | None = None   # "HH:MM"
    end_time: str | None = None     # "HH:MM" or "24:00"
    title: str | None = None
    attendees: str | None = None

    @model_validator(mode="after")
    def _check_time_input(self) -> "BookingCreateRequest":
        if self.preset is None and (self.start_time is None or self.end_time is None):
            raise ValueError("需提供 preset 或同时提供 start_time 与 end_time")
        return self


class CancelRequest(BaseModel):
    reason: str | None = None


class BookingOut(BaseModel):
    id: int
    room_id: int
    user_id: int
    recurrence_id: int | None = None
    date: date
    start_at: datetime
    end_at: datetime
    preset: str | None = None
    title: str | None = None
    attendees: str | None = None
    status: int
    cancel_reason: str | None = None
    cancelled_by: int | None = None
    cancel_source: int | None = None   # 1=user self / 2=admin
    cancelled_at: datetime | None = None

    model_config = {"from_attributes": True}


class BookingListOut(BaseModel):
    list: list[BookingOut]
    total: int
    page: int
