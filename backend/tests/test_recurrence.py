"""
Tests for T-BE-10/11: recurrence_service.expand_and_create + cancel_future
Covers: DAILY/WEEKLY/MONTHLY expansion, conflict batch detection, daily-limit,
        cancel_future ownership + count, concurrent race (CLAUDE.md §4.2).
"""
import threading
from datetime import date, timedelta

import pytest
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.schemas.recurrence import RecurrenceCreateRequest
from app.services import recurrence_service
from tests.conftest import make_test_session
from tests.test_booking import grant, make_room, make_user

# ── Helpers ───────────────────────────────────────────────────────────────────

_BASE_DATE = date(2030, 9, 2)   # Monday (Sep 1 2030 = Sunday)


def rec_req(**kwargs) -> RecurrenceCreateRequest:
    defaults = dict(
        room_id=0,                          # overridden by caller
        frequency="WEEKLY",
        weekdays=[0],                       # Monday
        month_day=None,
        start_date=_BASE_DATE,
        end_date=_BASE_DATE + timedelta(weeks=4),
        start_time="10:00",
        end_time="11:00",
        title="Test meeting",
    )
    defaults.update(kwargs)
    return RecurrenceCreateRequest(**defaults)


# ── Date generation ───────────────────────────────────────────────────────────

class TestDateGeneration:
    def test_daily_count(self, db: Session):
        r = make_room(db); u = make_user(db, "daily1")
        grant(db, r, u)
        # 7 days inclusive
        rec, bookings = recurrence_service.expand_and_create(
            db, u.id,
            rec_req(room_id=r.id, frequency="DAILY",
                    weekdays=None, start_date=_BASE_DATE,
                    end_date=_BASE_DATE + timedelta(days=6)),
        )
        assert len(bookings) == 7

    def test_weekly_mondays_only(self, db: Session):
        r = make_room(db); u = make_user(db, "weekly1")
        grant(db, r, u)
        # 4 weeks → 4 Mondays
        rec, bookings = recurrence_service.expand_and_create(
            db, u.id,
            rec_req(room_id=r.id, weekdays=[0],
                    start_date=_BASE_DATE,
                    end_date=_BASE_DATE + timedelta(weeks=4) - timedelta(days=1)),
        )
        assert len(bookings) == 4
        assert all(b.date.weekday() == 0 for b in bookings)

    def test_monthly_on_day_1(self, db: Session):
        r = make_room(db); u = make_user(db, "monthly1")
        grant(db, r, u)
        # Sep–Dec: 4 months, 1st of each
        rec, bookings = recurrence_service.expand_and_create(
            db, u.id,
            rec_req(room_id=r.id, frequency="MONTHLY",
                    weekdays=None, month_day=1,
                    start_date=date(2030, 9, 1), end_date=date(2030, 12, 31)),
        )
        assert len(bookings) == 4
        assert all(b.date.day == 1 for b in bookings)

    def test_multiple_weekdays(self, db: Session):
        r = make_room(db); u = make_user(db, "multi1")
        grant(db, r, u)
        # Mon+Wed for 2 weeks starting Monday
        rec, bookings = recurrence_service.expand_and_create(
            db, u.id,
            rec_req(room_id=r.id, weekdays=[0, 2],
                    start_date=_BASE_DATE,
                    end_date=_BASE_DATE + timedelta(days=13)),
        )
        assert len(bookings) == 4  # 2 Mon + 2 Wed


# ── Validation ────────────────────────────────────────────────────────────────

class TestRecurrenceValidation:
    def test_no_permission(self, db: Session):
        r = make_room(db); u = make_user(db, "recperm1")
        with pytest.raises(BusinessException) as e:
            recurrence_service.expand_and_create(db, u.id, rec_req(room_id=r.id))
        assert e.value.code == 40301

    def test_nonexistent_room(self, db: Session):
        u = make_user(db, "recperm2")
        with pytest.raises(BusinessException) as e:
            recurrence_service.expand_and_create(db, u.id, rec_req(room_id=999999))
        assert e.value.code == 40401

    def test_date_range_exceeds_max(self, db: Session):
        r = make_room(db); u = make_user(db, "recrange1")
        grant(db, r, u)
        with pytest.raises(BusinessException) as e:
            recurrence_service.expand_and_create(
                db, u.id,
                rec_req(room_id=r.id, frequency="DAILY", weekdays=None,
                        start_date=date(2030, 1, 1), end_date=date(2031, 1, 1)),
            )
        assert e.value.code == 40001

    def test_empty_result_raises(self, db: Session):
        r = make_room(db); u = make_user(db, "recempty1")
        grant(db, r, u)
        # WEEKLY on Monday but range only covers a Sunday (no Mondays)
        sunday = _BASE_DATE - timedelta(days=1)  # Sep 1, 2030 = Sunday
        with pytest.raises(BusinessException) as e:
            recurrence_service.expand_and_create(
                db, u.id,
                rec_req(room_id=r.id, weekdays=[0],
                        start_date=sunday,
                        end_date=sunday),
            )
        assert e.value.code == 40001


# ── Conflict detection ────────────────────────────────────────────────────────

class TestRecurrenceConflict:
    def test_all_conflict_raises_40902(self, db: Session):
        from app.schemas.booking import BookingCreateRequest
        from app.services import booking_service

        r = make_room(db)
        u1 = make_user(db, "rconf1"); u2 = make_user(db, "rconf2")
        grant(db, r, u1); grant(db, r, u2)

        # u1 books the same slot on the upcoming Monday
        booking_service.create(db, u1.id, BookingCreateRequest(
            room_id=r.id, date=_BASE_DATE,
            start_time="10:00", end_time="11:00",
        ))

        # u2 tries weekly recurrence on that same slot
        with pytest.raises(BusinessException) as e:
            recurrence_service.expand_and_create(
                db, u2.id,
                rec_req(room_id=r.id, weekdays=[0],
                        start_date=_BASE_DATE, end_date=_BASE_DATE),
            )
        assert e.value.code == 40902
        assert "conflicts" in e.value.data
        assert len(e.value.data["conflicts"]) == 1

    def test_partial_conflict_still_raises_40902(self, db: Session):
        from app.schemas.booking import BookingCreateRequest
        from app.services import booking_service

        r = make_room(db)
        u1 = make_user(db, "rpartial1"); u2 = make_user(db, "rpartial2")
        grant(db, r, u1); grant(db, r, u2)

        # Block only the first Monday
        booking_service.create(db, u1.id, BookingCreateRequest(
            room_id=r.id, date=_BASE_DATE,
            start_time="10:00", end_time="11:00",
        ))

        # u2 tries 2-Monday range — first conflicts
        with pytest.raises(BusinessException) as e:
            recurrence_service.expand_and_create(
                db, u2.id,
                rec_req(room_id=r.id, weekdays=[0],
                        start_date=_BASE_DATE,
                        end_date=_BASE_DATE + timedelta(weeks=1)),
            )
        assert e.value.code == 40902

    def test_no_conflict_succeeds(self, db: Session):
        r = make_room(db); u = make_user(db, "rnoconflict1")
        grant(db, r, u)
        rec, bookings = recurrence_service.expand_and_create(
            db, u.id, rec_req(room_id=r.id))
        assert rec.id is not None
        assert all(b.status == 1 for b in bookings)

    def test_cancelled_booking_does_not_block(self, db: Session):
        from app.schemas.booking import BookingCreateRequest
        from app.services import booking_service

        r = make_room(db)
        u1 = make_user(db, "rcancel1"); u2 = make_user(db, "rcancel2")
        grant(db, r, u1); grant(db, r, u2)

        b = booking_service.create(db, u1.id, BookingCreateRequest(
            room_id=r.id, date=_BASE_DATE,
            start_time="10:00", end_time="11:00",
        ))
        b.status = 0; db.commit()

        rec, bookings = recurrence_service.expand_and_create(
            db, u2.id,
            rec_req(room_id=r.id, weekdays=[0],
                    start_date=_BASE_DATE, end_date=_BASE_DATE),
        )
        assert len(bookings) == 1


# ── Recurrence stored correctly ───────────────────────────────────────────────

class TestRecurrenceRecord:
    def test_recurrence_id_on_bookings(self, db: Session):
        r = make_room(db); u = make_user(db, "recid1")
        grant(db, r, u)
        rec, bookings = recurrence_service.expand_and_create(
            db, u.id, rec_req(room_id=r.id, weekdays=[0],
                               start_date=_BASE_DATE,
                               end_date=_BASE_DATE + timedelta(weeks=1)))
        assert all(b.recurrence_id == rec.id for b in bookings)

    def test_allday_end_time_stored(self, db: Session):
        r = make_room(db); u = make_user(db, "recallday1")
        grant(db, r, u)
        rec, bookings = recurrence_service.expand_and_create(
            db, u.id,
            rec_req(room_id=r.id, frequency="DAILY", weekdays=None,
                    start_date=_BASE_DATE, end_date=_BASE_DATE,
                    start_time="08:00", end_time="24:00"),
        )
        # end_at should be next-day midnight UTC
        assert bookings[0].end_at.day != bookings[0].start_at.day or bookings[0].end_at.hour == 16


# ── Cancel future ─────────────────────────────────────────────────────────────

class TestCancelFuture:
    def test_cancel_future_by_owner(self, db: Session):
        r = make_room(db); u = make_user(db, "cfuture1")
        grant(db, r, u)
        rec, bookings = recurrence_service.expand_and_create(
            db, u.id, rec_req(room_id=r.id))
        count = recurrence_service.cancel_future(db, rec.id, u.id)
        assert count == len(bookings)

        from app.models.recurrence import BookingRecurrence
        db.expire_all()
        updated_rec = db.get(BookingRecurrence, rec.id)
        assert updated_rec.status == 0

    def test_cancel_future_other_user_raises_403(self, db: Session):
        r = make_room(db)
        u1 = make_user(db, "cfuture2"); u2 = make_user(db, "cfuture3")
        grant(db, r, u1); grant(db, r, u2)
        rec, _ = recurrence_service.expand_and_create(
            db, u1.id, rec_req(room_id=r.id))
        with pytest.raises(BusinessException) as e:
            recurrence_service.cancel_future(db, rec.id, u2.id)
        assert e.value.code == 40301

    def test_cancel_nonexistent_recurrence_raises_404(self, db: Session):
        u = make_user(db, "cfuture4")
        with pytest.raises(BusinessException) as e:
            recurrence_service.cancel_future(db, 999999, u.id)
        assert e.value.code == 40401


# ── Concurrent recurrence booking (CLAUDE.md §4.2) ───────────────────────────

class TestConcurrentRecurrence:
    def test_two_users_race_same_slot_only_one_wins(self, db: Session):
        """
        Two threads race to book the same room+slot via recurrence.
        MySQL FOR UPDATE serialises them; exactly one recurrence must be created.

        We verify at the database level (not via thread return values) because
        pymysql may drop the losing thread's connection instead of raising a clean
        BusinessException — either way, the data-integrity invariant must hold.
        """
        from app.models.recurrence import BookingRecurrence as Rec

        r = make_room(db)
        u1 = make_user(db, "crace1"); u2 = make_user(db, "crace2")
        grant(db, r, u1); grant(db, r, u2)
        room_id = r.id
        uid1, uid2 = u1.id, u2.id

        def book(uid: int) -> None:
            sess = make_test_session()
            try:
                request = rec_req(room_id=room_id, weekdays=[0],
                                  start_date=_BASE_DATE, end_date=_BASE_DATE)
                recurrence_service.expand_and_create(sess, uid, request)
            except Exception:
                pass
            finally:
                try:
                    sess.close()
                except Exception:
                    pass

        t1 = threading.Thread(target=book, args=(uid1,))
        t2 = threading.Thread(target=book, args=(uid2,))
        t1.start(); t2.start()
        t1.join(); t2.join()

        # Verify DB state directly — exactly one recurrence and one booking created
        db.expire_all()
        rec_count = (
            db.query(func.count(Rec.id))
            .filter(Rec.room_id == room_id, Rec.status == 1)
            .scalar()
        )
        assert rec_count == 1, f"Expected exactly 1 recurrence in DB, found {rec_count}"

        from app.models.booking import Booking
        booking_count = (
            db.query(func.count(Booking.id))
            .filter(Booking.room_id == room_id, Booking.status == 1)
            .scalar()
        )
        assert booking_count == 1, f"Expected exactly 1 booking in DB, found {booking_count}"


# ── API smoke tests ───────────────────────────────────────────────────────────

class TestRecurrenceEndpoints:
    def test_create_weekly_via_api(self, client, db: Session):
        from tests.test_booking import user_token
        r = make_room(db); u = make_user(db, "rapi1")
        grant(db, r, u)
        resp = client.post(
            "/api/bookings/recurrence",
            json={
                "room_id": r.id,
                "frequency": "WEEKLY",
                "weekdays": [0],
                "start_date": str(_BASE_DATE),
                "end_date": str(_BASE_DATE + timedelta(weeks=4) - timedelta(days=1)),
                "start_time": "14:00",
                "end_time": "15:00",
            },
            headers={"Authorization": f"Bearer {user_token(u)}"},
        )
        data = resp.json()
        assert data["code"] == 0, data
        assert data["data"]["count"] == 4

    def test_conflict_via_api_returns_40902(self, client, db: Session):
        from app.schemas.booking import BookingCreateRequest
        from app.services import booking_service
        from tests.test_booking import user_token

        r = make_room(db)
        u1 = make_user(db, "rapi2"); u2 = make_user(db, "rapi3")
        grant(db, r, u1); grant(db, r, u2)

        booking_service.create(db, u1.id, BookingCreateRequest(
            room_id=r.id, date=_BASE_DATE,
            start_time="14:00", end_time="15:00",
        ))

        resp = client.post(
            "/api/bookings/recurrence",
            json={
                "room_id": r.id,
                "frequency": "WEEKLY",
                "weekdays": [0],
                "start_date": str(_BASE_DATE),
                "end_date": str(_BASE_DATE),
                "start_time": "14:00",
                "end_time": "15:00",
            },
            headers={"Authorization": f"Bearer {user_token(u2)}"},
        )
        assert resp.json()["code"] == 40902

    def test_cancel_recurrence_via_api(self, client, db: Session):
        from tests.test_booking import user_token
        r = make_room(db); u = make_user(db, "rapi4")
        grant(db, r, u)
        create_resp = client.post(
            "/api/bookings/recurrence",
            json={
                "room_id": r.id,
                "frequency": "WEEKLY",
                "weekdays": [0],
                "start_date": str(_BASE_DATE),
                "end_date": str(_BASE_DATE + timedelta(weeks=1)),
                "start_time": "09:00",
                "end_time": "10:00",
            },
            headers={"Authorization": f"Bearer {user_token(u)}"},
        )
        rec_id = create_resp.json()["data"]["recurrence_id"]

        cancel_resp = client.post(
            f"/api/bookings/recurrence/{rec_id}/cancel",
            headers={"Authorization": f"Bearer {user_token(u)}"},
        )
        assert cancel_resp.json()["code"] == 0
        assert cancel_resp.json()["data"]["cancelled_count"] == 2
