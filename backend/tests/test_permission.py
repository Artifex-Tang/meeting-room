"""Tests for T-BE-07 (permission_service) and T-BE-09 (availability endpoint)."""
from datetime import date, datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.booking import Booking
from app.models.department import Department
from app.models.room import Room
from app.models.user import User
from app.services import permission_service

SHANGHAI_TZ = timezone(timedelta(hours=8))


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_room(db: Session, name: str = "Room A", status: int = 1) -> Room:
    r = Room(name=name, status=status)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def make_dept(db: Session, name: str = "Dept A") -> Department:
    d = Department(name=name)
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def make_user(db: Session, openid: str = "u1", dept_id: int | None = None) -> User:
    u = User(openid=openid, status=1, dept_id=dept_id)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def user_token(user: User) -> str:
    token, _ = create_access_token(str(user.id), "user", 1)
    return token


# ── permission_service unit tests ────────────────────────────────────────────

class TestGetVisibleRooms:
    def test_no_permissions_returns_empty(self, db: Session):
        make_room(db, "R1")
        u = make_user(db, "u_noperm")
        assert permission_service.get_visible_rooms(db, u.id) == []

    def test_direct_permission(self, db: Session):
        r = make_room(db, "R2")
        u = make_user(db, "u_direct")
        permission_service.grant_user(db, r.id, u.id, granted_by=0)
        visible = permission_service.get_visible_rooms(db, u.id)
        assert len(visible) == 1 and visible[0].id == r.id

    def test_dept_permission(self, db: Session):
        r = make_room(db, "R3")
        d = make_dept(db)
        u = make_user(db, "u_dept", dept_id=d.id)
        permission_service.grant_dept(db, r.id, d.id, granted_by=0)
        visible = permission_service.get_visible_rooms(db, u.id)
        assert len(visible) == 1 and visible[0].id == r.id

    def test_union_deduplicates(self, db: Session):
        """User has both direct + dept permission to same room — should appear once."""
        r = make_room(db, "R4")
        d = make_dept(db)
        u = make_user(db, "u_both", dept_id=d.id)
        permission_service.grant_user(db, r.id, u.id, granted_by=0)
        permission_service.grant_dept(db, r.id, d.id, granted_by=0)
        visible = permission_service.get_visible_rooms(db, u.id)
        assert len(visible) == 1

    def test_disabled_room_excluded(self, db: Session):
        r = make_room(db, "R5", status=0)
        u = make_user(db, "u_disabled_room")
        permission_service.grant_user(db, r.id, u.id, granted_by=0)
        assert permission_service.get_visible_rooms(db, u.id) == []

    def test_keyword_filter(self, db: Session):
        r1 = make_room(db, "大会议室")
        r2 = make_room(db, "小会议室")
        u = make_user(db, "u_kw")
        permission_service.grant_user(db, r1.id, u.id, granted_by=0)
        permission_service.grant_user(db, r2.id, u.id, granted_by=0)
        visible = permission_service.get_visible_rooms(db, u.id, keyword="大")
        assert len(visible) == 1 and visible[0].name == "大会议室"


class TestCheckRoomVisible:
    def test_visible_with_direct(self, db: Session):
        r = make_room(db); u = make_user(db, "chk1")
        permission_service.grant_user(db, r.id, u.id, granted_by=0)
        assert permission_service.check_room_visible(db, u.id, r.id) is True

    def test_not_visible_without_permission(self, db: Session):
        r = make_room(db); u = make_user(db, "chk2")
        assert permission_service.check_room_visible(db, u.id, r.id) is False

    def test_visible_after_revoke_becomes_false(self, db: Session):
        r = make_room(db); u = make_user(db, "chk3")
        permission_service.grant_user(db, r.id, u.id, granted_by=0)
        assert permission_service.check_room_visible(db, u.id, r.id) is True
        permission_service.revoke_user(db, r.id, u.id)
        assert permission_service.check_room_visible(db, u.id, r.id) is False

    def test_grant_idempotent(self, db: Session):
        r = make_room(db); u = make_user(db, "chk4")
        p1 = permission_service.grant_user(db, r.id, u.id, granted_by=0)
        p2 = permission_service.grant_user(db, r.id, u.id, granted_by=0)
        assert p1.id == p2.id


# ── /api/rooms endpoint tests ─────────────────────────────────────────────────

class TestListRoomsEndpoint:
    def test_returns_only_visible(self, client: TestClient, db: Session):
        r1 = make_room(db, "Visible")
        make_room(db, "Hidden")
        u = make_user(db, "ep_u1")
        permission_service.grant_user(db, r1.id, u.id, granted_by=0)
        resp = client.get("/api/rooms", headers={"Authorization": f"Bearer {user_token(u)}"})
        assert resp.status_code == 200
        names = [x["name"] for x in resp.json()["data"]]
        assert "Visible" in names and "Hidden" not in names

    def test_no_token_returns_401(self, client: TestClient):
        resp = client.get("/api/rooms")
        assert resp.json()["code"] == 40101


# ── /api/rooms/{id}/availability tests ───────────────────────────────────────

class TestAvailabilityEndpoint:
    def _make_booking(self, db: Session, room: Room, user: User,
                      date_str: str, start_h: int, end_h: int) -> Booking:
        d = date.fromisoformat(date_str)
        # Store as naive UTC (in real flow Shanghai→UTC conversion happens in booking_service)
        start_utc = datetime(d.year, d.month, d.day, start_h - 8, 0, 0)  # -8 for Shanghai offset
        end_utc = datetime(d.year, d.month, d.day, end_h - 8, 0, 0)
        b = Booking(
            room_id=room.id, user_id=user.id,
            date=d, start_at=start_utc, end_at=end_utc,
            status=1,
        )
        db.add(b)
        db.commit()
        db.refresh(b)
        return b

    def test_returns_occupied_slots(self, client: TestClient, db: Session):
        r = make_room(db, "AvailRoom")
        u = make_user(db, "av_u1")
        permission_service.grant_user(db, r.id, u.id, granted_by=0)
        self._make_booking(db, r, u, "2026-05-10", 9, 11)

        resp = client.get(
            f"/api/rooms/{r.id}/availability",
            params={"date": "2026-05-10"},
            headers={"Authorization": f"Bearer {user_token(u)}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["room_id"] == r.id
        assert len(data["slots_taken"]) == 1
        slot = data["slots_taken"][0]
        assert "+08:00" in slot["start_at"]  # timezone-aware response

    def test_empty_when_no_bookings(self, client: TestClient, db: Session):
        r = make_room(db, "Empty")
        u = make_user(db, "av_u2")
        permission_service.grant_user(db, r.id, u.id, granted_by=0)
        resp = client.get(
            f"/api/rooms/{r.id}/availability",
            params={"date": "2026-05-11"},
            headers={"Authorization": f"Bearer {user_token(u)}"},
        )
        assert resp.json()["data"]["slots_taken"] == []

    def test_no_permission_returns_403(self, client: TestClient, db: Session):
        r = make_room(db, "NoPerm")
        u = make_user(db, "av_u3")
        resp = client.get(
            f"/api/rooms/{r.id}/availability",
            params={"date": "2026-05-10"},
            headers={"Authorization": f"Bearer {user_token(u)}"},
        )
        assert resp.json()["code"] == 40301

    def test_nonexistent_room_returns_404(self, client: TestClient, db: Session):
        u = make_user(db, "av_u4")
        resp = client.get(
            "/api/rooms/999999/availability",
            params={"date": "2026-05-10"},
            headers={"Authorization": f"Bearer {user_token(u)}"},
        )
        assert resp.json()["code"] == 40401
