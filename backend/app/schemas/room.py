from datetime import date, datetime

from pydantic import BaseModel


class RoomOut(BaseModel):
    id: int
    name: str
    location: str | None = None
    capacity: int | None = None
    facilities: str | None = None
    description: str | None = None
    status: int

    model_config = {"from_attributes": True}


class UserSimple(BaseModel):
    id: int
    real_name: str | None = None
    nickname: str | None = None

    model_config = {"from_attributes": True}


class SlotTaken(BaseModel):
    booking_id: int
    start_at: datetime
    end_at: datetime
    user: UserSimple
    preset: str | None = None
    title: str | None = None


class AvailabilityOut(BaseModel):
    room_id: int
    date: date
    slots_taken: list[SlotTaken]
