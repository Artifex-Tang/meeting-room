"""
Tests for T-BE-12 + T-BE-16: all admin endpoints + password change.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.admin_user import AdminUser
from app.models.booking import Booking
from app.models.department import Department
from app.models.room import Room
from app.models.user import User
from tests.test_booking import grant, make_room, make_user


# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def admin(db: Session) -> AdminUser:
    a = AdminUser(username="testadmin", password_hash=hash_password("pass123"), status=1)
    db.add(a); db.commit(); db.refresh(a)
    return a


@pytest.fixture
def auth(admin: AdminUser) -> dict:
    token, _ = create_access_token(str(admin.id), "admin", 1)
    return {"Authorization": f"Bearer {token}"}


def make_dept(db: Session, name: str = "D") -> Department:
    d = Department(name=name)
    db.add(d); db.commit(); db.refresh(d)
    return d


def make_booking(db: Session, room: Room, user: User,
                 d: date = date(2030, 10, 1),
                 start: str = "10:00", end: str = "11:00") -> Booking:
    from app.services.booking_service import _parse_hhmm, _to_utc
    b = Booking(
        room_id=room.id, user_id=user.id, date=d,
        start_at=_to_utc(d, _parse_hhmm(start)),
        end_at=_to_utc(d, _parse_hhmm(end)),
        status=1,
    )
    db.add(b); db.commit(); db.refresh(b)
    return b


# ── Auth guard ────────────────────────────────────────────────────────────────

class TestAdminAuthGuard:
    def test_no_token_returns_401(self, client: TestClient):
        resp = client.get("/api/admin/rooms")
        assert resp.json()["code"] in (40101, 40100)

    def test_user_token_rejected(self, client: TestClient, db: Session):
        u = make_user(db, "authcheck")
        from tests.test_booking import user_token
        resp = client.get("/api/admin/rooms",
                          headers={"Authorization": f"Bearer {user_token(u)}"})
        assert resp.json()["code"] == 40101


# ── Rooms CRUD ────────────────────────────────────────────────────────────────

class TestAdminRooms:
    def test_create_room(self, client: TestClient, auth: dict):
        resp = client.post("/api/admin/rooms",
                           json={"name": "创新室", "capacity": 10},
                           headers=auth)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "创新室"
        assert data["status"] == 1

    def test_list_rooms_empty(self, client: TestClient, auth: dict):
        resp = client.get("/api/admin/rooms", headers=auth)
        assert resp.json()["data"]["total"] == 0

    def test_list_rooms_with_keyword_filter(self, client: TestClient, auth: dict, db: Session):
        make_room(db, "Alpha"); make_room(db, "Beta"); make_room(db, "Alpha2")
        resp = client.get("/api/admin/rooms?keyword=Alpha", headers=auth)
        assert resp.json()["data"]["total"] == 2

    def test_update_room(self, client: TestClient, auth: dict, db: Session):
        r = make_room(db, "Old name")
        resp = client.put(f"/api/admin/rooms/{r.id}",
                          json={"name": "New name", "capacity": 20},
                          headers=auth)
        assert resp.json()["data"]["name"] == "New name"

    def test_delete_room_no_future_bookings(self, client: TestClient, auth: dict, db: Session):
        r = make_room(db, "ToDelete")
        resp = client.delete(f"/api/admin/rooms/{r.id}", headers=auth)
        assert resp.json()["code"] == 0
        db.expire_all()
        assert db.get(Room, r.id).status == 0

    def test_delete_room_with_future_bookings_rejected(
            self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); u = make_user(db, "futurebooker")
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        start = now_utc + timedelta(hours=2)
        end = start + timedelta(hours=1)
        b = Booking(room_id=r.id, user_id=u.id, date=start.date(),
                    start_at=start, end_at=end, status=1)
        db.add(b); db.commit()
        resp = client.delete(f"/api/admin/rooms/{r.id}", headers=auth)
        assert resp.json()["code"] == 40901

    def test_delete_nonexistent_room(self, client: TestClient, auth: dict):
        resp = client.delete("/api/admin/rooms/999999", headers=auth)
        assert resp.json()["code"] == 40401


# ── Permissions ───────────────────────────────────────────────────────────────

class TestAdminPermissions:
    def test_grant_and_list_user_permission(
            self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); u = make_user(db, "perm_u1")
        client.post(f"/api/admin/rooms/{r.id}/permissions/users",
                    json={"user_ids": [u.id]}, headers=auth)
        resp = client.get(f"/api/admin/rooms/{r.id}/permissions", headers=auth)
        assert any(u2["id"] == u.id for u2 in resp.json()["data"]["users"])

    def test_revoke_user_permission(self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); u = make_user(db, "perm_u2")
        grant(db, r, u)
        client.delete(f"/api/admin/rooms/{r.id}/permissions/users/{u.id}", headers=auth)
        resp = client.get(f"/api/admin/rooms/{r.id}/permissions", headers=auth)
        assert not any(u2["id"] == u.id for u2 in resp.json()["data"]["users"])

    def test_grant_and_revoke_dept_permission(
            self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); d = make_dept(db, "Tech")
        client.post(f"/api/admin/rooms/{r.id}/permissions/depts",
                    json={"dept_ids": [d.id]}, headers=auth)
        resp = client.get(f"/api/admin/rooms/{r.id}/permissions", headers=auth)
        assert any(dept["id"] == d.id for dept in resp.json()["data"]["depts"])

        client.delete(f"/api/admin/rooms/{r.id}/permissions/depts/{d.id}", headers=auth)
        resp2 = client.get(f"/api/admin/rooms/{r.id}/permissions", headers=auth)
        assert not any(dept["id"] == d.id for dept in resp2.json()["data"]["depts"])

    def test_get_user_visible_rooms(self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); u = make_user(db, "visible1")
        grant(db, r, u)
        resp = client.get(f"/api/admin/users/{u.id}/rooms", headers=auth)
        assert any(room["id"] == r.id for room in resp.json()["data"])


# ── Users ─────────────────────────────────────────────────────────────────────

class TestAdminUsers:
    def test_list_users(self, client: TestClient, auth: dict, db: Session):
        make_user(db, "list_u1"); make_user(db, "list_u2")
        resp = client.get("/api/admin/users", headers=auth)
        assert resp.json()["data"]["total"] >= 2

    def test_list_users_keyword_filter(self, client: TestClient, auth: dict, db: Session):
        u = make_user(db, "search_u1")
        u.real_name = "张三"; db.commit()
        resp = client.get("/api/admin/users?keyword=张三", headers=auth)
        assert resp.json()["data"]["total"] >= 1

    def test_update_user(self, client: TestClient, auth: dict, db: Session):
        u = make_user(db, "upd_u1")
        resp = client.put(f"/api/admin/users/{u.id}",
                          json={"real_name": "李四", "status": 1},
                          headers=auth)
        assert resp.json()["data"]["real_name"] == "李四"

    def test_update_nonexistent_user(self, client: TestClient, auth: dict):
        resp = client.put("/api/admin/users/999999",
                          json={"real_name": "X"}, headers=auth)
        assert resp.json()["code"] == 40401


# ── Departments ───────────────────────────────────────────────────────────────

class TestAdminDepartments:
    def test_create_and_list(self, client: TestClient, auth: dict):
        client.post("/api/admin/departments", json={"name": "研发部"}, headers=auth)
        resp = client.get("/api/admin/departments", headers=auth)
        names = [d["name"] for d in resp.json()["data"]]
        assert "研发部" in names

    def test_update_department(self, client: TestClient, auth: dict, db: Session):
        d = make_dept(db, "OldDept")
        resp = client.put(f"/api/admin/departments/{d.id}",
                          json={"name": "NewDept"}, headers=auth)
        assert resp.json()["data"]["name"] == "NewDept"

    def test_delete_department_unlinks_users(
            self, client: TestClient, auth: dict, db: Session):
        d = make_dept(db, "ToDelete")
        u = make_user(db, "deptuser1"); u.dept_id = d.id; db.commit()

        resp = client.delete(f"/api/admin/departments/{d.id}", headers=auth)
        assert resp.json()["code"] == 0
        assert db.get(Department, d.id) is None
        db.expire(u); assert u.dept_id is None


# ── Bookings ──────────────────────────────────────────────────────────────────

class TestAdminBookings:
    def test_list_bookings_all(self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); u = make_user(db, "bklist1")
        make_booking(db, r, u)
        resp = client.get("/api/admin/bookings", headers=auth)
        assert resp.json()["data"]["total"] >= 1

    def test_list_bookings_filter_by_room(self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); u = make_user(db, "bklist2")
        make_booking(db, r, u)
        resp = client.get(f"/api/admin/bookings?room_id={r.id}", headers=auth)
        assert resp.json()["data"]["total"] == 1

    def test_admin_cancel_booking(self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); u = make_user(db, "cancel_admin1")
        b = make_booking(db, r, u)
        resp = client.post(f"/api/admin/bookings/{b.id}/cancel",
                           json={"reason": "admin reason"},
                           headers=auth)
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["status"] == 0

    def test_admin_cancel_nonexistent(self, client: TestClient, auth: dict):
        resp = client.post("/api/admin/bookings/999999/cancel",
                           json={}, headers=auth)
        assert resp.json()["code"] == 40401

    def test_admin_cancel_no_time_restriction(
            self, client: TestClient, auth: dict, db: Session):
        # Admin can cancel bookings that are starting soon (no advance-hours check)
        r = make_room(db); u = make_user(db, "cancel_admin2")
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        start = now_utc + timedelta(minutes=10)
        end = start + timedelta(hours=1)
        b = Booking(room_id=r.id, user_id=u.id, date=start.date(),
                    start_at=start, end_at=end, status=1)
        db.add(b); db.commit(); db.refresh(b)
        resp = client.post(f"/api/admin/bookings/{b.id}/cancel",
                           json={}, headers=auth)
        assert resp.json()["code"] == 0


# ── Stats ─────────────────────────────────────────────────────────────────────

class TestAdminStats:
    def test_overview_structure(self, client: TestClient, auth: dict):
        resp = client.get("/api/admin/stats/overview", headers=auth)
        data = resp.json()["data"]
        assert "today_bookings" in data
        assert "week_bookings" in data
        assert isinstance(data["top_rooms"], list)

    def test_today_count_increments(self, client: TestClient, auth: dict, db: Session):
        r = make_room(db); u = make_user(db, "stats1")
        today = datetime.now(timezone.utc).date()
        make_booking(db, r, u, d=today)
        resp = client.get("/api/admin/stats/overview", headers=auth)
        assert resp.json()["data"]["today_bookings"] >= 1


# ── Config ────────────────────────────────────────────────────────────────────

class TestAdminConfig:
    def test_get_config_returns_dict(self, client: TestClient, auth: dict):
        resp = client.get("/api/admin/config", headers=auth)
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], dict)

    def test_update_config(self, client: TestClient, auth: dict):
        resp = client.put("/api/admin/config",
                          json={"cancel_advance_hours": 3},
                          headers=auth)
        assert resp.json()["code"] == 0

    def test_update_config_invalid_value_rejected(self, client: TestClient, auth: dict):
        resp = client.put("/api/admin/config",
                          json={"cancel_advance_hours": -1},
                          headers=auth)
        assert resp.status_code == 422


# ── Password change (T-BE-16) ─────────────────────────────────────────────────

class TestAdminPasswordChange:
    def test_wrong_old_password_rejected(self, client: TestClient, db: Session):
        a = AdminUser(username="pw_test", password_hash=hash_password("correct"), status=1)
        db.add(a); db.commit(); db.refresh(a)
        token, _ = create_access_token(str(a.id), "admin", 1)
        resp = client.put("/api/admin/me/password",
                          json={"old_password": "wrong", "new_password": "newpass123"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.json()["code"] == 40001

    def test_change_password_success(self, client: TestClient, db: Session):
        a = AdminUser(username="pw_test2", password_hash=hash_password("oldpass"), status=1)
        db.add(a); db.commit(); db.refresh(a)
        token, _ = create_access_token(str(a.id), "admin", 1)
        resp = client.put("/api/admin/me/password",
                          json={"old_password": "oldpass", "new_password": "newpass123"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.json()["code"] == 0

    def test_new_password_too_short(self, client: TestClient, db: Session):
        a = AdminUser(username="pw_test3", password_hash=hash_password("oldpass"), status=1)
        db.add(a); db.commit(); db.refresh(a)
        token, _ = create_access_token(str(a.id), "admin", 1)
        resp = client.put("/api/admin/me/password",
                          json={"old_password": "oldpass", "new_password": "abc"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.json()["code"] == 40001
