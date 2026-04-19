from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator


# ── Room ─────────────────────────────────────────────────────────────────────

class RoomCreateRequest(BaseModel):
    name: str
    location: str | None = None
    capacity: int | None = None
    facilities: str | None = None
    description: str | None = None
    status: int = 1


class RoomUpdateRequest(BaseModel):
    name: str | None = None
    location: str | None = None
    capacity: int | None = None
    facilities: str | None = None
    description: str | None = None
    status: int | None = None


class RoomOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    location: str | None
    capacity: int | None
    facilities: str | None
    description: str | None
    status: int


# ── Permission ────────────────────────────────────────────────────────────────

class GrantUsersRequest(BaseModel):
    user_ids: list[int]


class GrantDeptsRequest(BaseModel):
    dept_ids: list[int]


class UserSimpleOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    openid: str
    nickname: str | None
    real_name: str | None
    dept_id: int | None


class DeptSimpleOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str


class RoomPermissionsOut(BaseModel):
    users: list[UserSimpleOut]
    depts: list[DeptSimpleOut]


# ── User ──────────────────────────────────────────────────────────────────────

class UserUpdateRequest(BaseModel):
    real_name: str | None = None
    dept_id: int | None = None
    status: int | None = None


class UserOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    openid: str
    nickname: str | None
    real_name: str | None
    phone: str | None
    dept_id: int | None
    status: int


# ── Department ────────────────────────────────────────────────────────────────

class DeptCreateRequest(BaseModel):
    name: str
    parent_id: int | None = None


class DeptUpdateRequest(BaseModel):
    name: str | None = None
    parent_id: int | None = None


class DeptOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    name: str
    parent_id: int | None


# ── Booking ───────────────────────────────────────────────────────────────────

class AdminCancelRequest(BaseModel):
    reason: str | None = None


class BookingAdminOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    room_id: int
    user_id: int
    date: date
    start_at: Any   # serialized as Shanghai ISO string in endpoint
    end_at: Any
    preset: str | None
    title: str | None
    status: int
    cancel_reason: str | None
    recurrence_id: int | None


# ── Config ────────────────────────────────────────────────────────────────────

class ConfigUpdateRequest(BaseModel):
    advance_booking_days: int | None = None
    max_booking_hours: int | None = None
    max_bookings_per_day: int | None = None
    cancel_advance_hours: int | None = None
    max_recurrence_months: int | None = None
    notify_quota_cap: int | None = None
    notify_upcoming_minutes: int | None = None
    tpl_booking_success: str | None = None
    tpl_booking_upcoming: str | None = None
    tpl_booking_cancelled: str | None = None

    @field_validator(
        "advance_booking_days", "max_booking_hours", "max_bookings_per_day",
        "cancel_advance_hours", "max_recurrence_months",
        "notify_quota_cap", "notify_upcoming_minutes",
        mode="before",
    )
    @classmethod
    def _positive(cls, v: Any) -> Any:
        if v is not None and int(v) <= 0:
            raise ValueError("参数值须为正整数")
        return v


# ── Stats ─────────────────────────────────────────────────────────────────────

class TopRoom(BaseModel):
    room_id: int
    room_name: str
    count: int


class StatsOverviewOut(BaseModel):
    today_bookings: int
    week_bookings: int
    top_rooms: list[TopRoom]


# ── Admin password change ─────────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
