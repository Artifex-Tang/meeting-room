"""
Tests for T-BE-17/18/19: notify_service + scheduler + integration.
Covers:
- subscribe_report: quota increments, cap, reject/ban ignored
- enqueue_booking_success: log created, quota=0 skips, idempotent
- enqueue_booking_cancelled: pending upcoming cancelled, cancelled log created
- process_pending_logs: sends due logs, skips future logs
- User self-cancel does NOT enqueue notification
- Admin cancel does enqueue notification
- Notification failure does not block booking creation
"""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.models.booking import Booking
from app.models.notify import NotifyLog, NotifyQuota
from app.services import notify_service
from tests.test_booking import grant, make_room, make_user


# ── Helpers ───────────────────────────────────────────────────────────────────

_FUTURE_DATE = date(2030, 11, 1)


def make_booking_obj(db: Session, room_id: int, user_id: int,
                     d: date = _FUTURE_DATE,
                     start: str = "10:00", end: str = "11:00") -> Booking:
    from app.services.booking_service import _parse_hhmm, _to_utc
    b = Booking(
        room_id=room_id, user_id=user_id, date=d,
        start_at=_to_utc(d, _parse_hhmm(start)),
        end_at=_to_utc(d, _parse_hhmm(end)),
        status=1,
    )
    db.add(b); db.commit(); db.refresh(b)
    return b


def set_quota(db: Session, user_id: int, template_key: str, amount: int) -> None:
    from sqlalchemy.dialects.mysql import insert as mysql_insert
    existing = db.query(NotifyQuota).filter(
        NotifyQuota.user_id == user_id,
        NotifyQuota.template_key == template_key,
    ).first()
    if existing:
        existing.quota = amount
    else:
        db.add(NotifyQuota(user_id=user_id, template_key=template_key, quota=amount))
    db.commit()


def get_quota(db: Session, user_id: int, template_key: str) -> int:
    row = db.query(NotifyQuota).filter(
        NotifyQuota.user_id == user_id,
        NotifyQuota.template_key == template_key,
    ).first()
    return row.quota if row else 0


def get_logs(db: Session, booking_id: int, scene: str) -> list[NotifyLog]:
    return (
        db.query(NotifyLog)
        .filter(NotifyLog.booking_id == booking_id, NotifyLog.scene == scene)
        .all()
    )


# ── Subscribe report ──────────────────────────────────────────────────────────

class TestSubscribeReport:
    def test_accept_increments_quota(self, db: Session):
        u = make_user(db, "sub1")
        notify_service.report_subscribe(db, u.id, {"booking_success": "accept"})
        assert get_quota(db, u.id, "booking_success") == 1

    def test_reject_does_not_increment(self, db: Session):
        u = make_user(db, "sub2")
        notify_service.report_subscribe(db, u.id, {"booking_success": "reject"})
        assert get_quota(db, u.id, "booking_success") == 0

    def test_ban_does_not_increment(self, db: Session):
        u = make_user(db, "sub3")
        notify_service.report_subscribe(db, u.id, {"booking_success": "ban"})
        assert get_quota(db, u.id, "booking_success") == 0

    def test_multiple_accepts_accumulate(self, db: Session):
        u = make_user(db, "sub4")
        notify_service.report_subscribe(db, u.id, {"booking_success": "accept"})
        notify_service.report_subscribe(db, u.id, {"booking_success": "accept"})
        assert get_quota(db, u.id, "booking_success") == 2

    def test_quota_capped(self, db: Session):
        u = make_user(db, "sub5")
        set_quota(db, u.id, "booking_success", 10)
        notify_service.report_subscribe(db, u.id, {"booking_success": "accept"})
        assert get_quota(db, u.id, "booking_success") == 10  # capped at 10

    def test_all_three_scenes_at_once(self, db: Session):
        u = make_user(db, "sub6")
        notify_service.report_subscribe(db, u.id, {
            "booking_success": "accept",
            "booking_upcoming": "accept",
            "booking_cancelled": "reject",
        })
        assert get_quota(db, u.id, "booking_success") == 1
        assert get_quota(db, u.id, "booking_upcoming") == 1
        assert get_quota(db, u.id, "booking_cancelled") == 0


# ── Enqueue success (mock mode, template_id empty → skipped) ─────────────────

class TestEnqueueSuccess:
    def test_creates_notify_logs(self, db: Session):
        r = make_room(db); u = make_user(db, "enq1")
        b = make_booking_obj(db, r.id, u.id)

        notify_service.enqueue_booking_success(db, b)

        success_logs = get_logs(db, b.id, "booking_success")
        upcoming_logs = get_logs(db, b.id, "booking_upcoming")
        assert len(success_logs) == 1
        assert len(upcoming_logs) == 1

    def test_skipped_when_no_quota_and_no_template(self, db: Session):
        r = make_room(db); u = make_user(db, "enq2")
        b = make_booking_obj(db, r.id, u.id)

        notify_service.enqueue_booking_success(db, b)
        db.expire_all()

        # Template is empty in test DB → status should be SKIPPED
        log = get_logs(db, b.id, "booking_success")[0]
        assert log.status == 3  # skipped

    def test_sent_when_quota_and_mock_template(self, db: Session):
        r = make_room(db); u = make_user(db, "enq3")
        b = make_booking_obj(db, r.id, u.id)

        # Set a non-empty template_id and give quota
        from app.models.system_config import SystemConfig
        sc = db.get(SystemConfig, "wx_tpl_booking_success")
        if sc:
            sc.value = "tpl_mock_id"
        else:
            db.add(SystemConfig(config_key="wx_tpl_booking_success", value="tpl_mock_id"))
        db.commit()
        set_quota(db, u.id, "booking_success", 1)

        with patch("app.config.settings") as mock_settings:
            mock_settings.wechat_mock = True
            mock_settings.run_scheduler = False
            notify_service.enqueue_booking_success(db, b)

        db.expire_all()
        log = get_logs(db, b.id, "booking_success")[0]
        assert log.status == 1  # sent
        assert get_quota(db, u.id, "booking_success") == 0  # deducted

    def test_idempotent_no_duplicate_log(self, db: Session):
        r = make_room(db); u = make_user(db, "enq4")
        b = make_booking_obj(db, r.id, u.id)

        notify_service.enqueue_booking_success(db, b)
        notify_service.enqueue_booking_success(db, b)  # second call silently ignored

        success_logs = get_logs(db, b.id, "booking_success")
        assert len(success_logs) == 1

    def test_upcoming_planned_at_set(self, db: Session):
        r = make_room(db); u = make_user(db, "enq5")
        b = make_booking_obj(db, r.id, u.id)

        notify_service.enqueue_booking_success(db, b)
        upcoming = get_logs(db, b.id, "booking_upcoming")[0]
        expected = b.start_at - timedelta(minutes=15)
        assert abs((upcoming.planned_at - expected).total_seconds()) < 2


# ── Enqueue cancelled ─────────────────────────────────────────────────────────

class TestEnqueueCancelled:
    def test_creates_cancelled_log(self, db: Session):
        r = make_room(db); u = make_user(db, "canc1")
        b = make_booking_obj(db, r.id, u.id)
        b.status = 0; b.cancelled_by = 1; b.cancel_source = 2
        db.commit()

        notify_service.enqueue_booking_cancelled(db, b)
        logs = get_logs(db, b.id, "booking_cancelled")
        assert len(logs) == 1

    def test_cancels_pending_upcoming(self, db: Session):
        r = make_room(db); u = make_user(db, "canc2")
        b = make_booking_obj(db, r.id, u.id)

        # Create a pending upcoming log
        upcoming_log = NotifyLog(
            user_id=u.id, booking_id=b.id,
            template_key="booking_upcoming", scene="booking_upcoming",
            status=0, planned_at=b.start_at - timedelta(minutes=15),
        )
        db.add(upcoming_log); db.commit()

        b.status = 0; db.commit()
        notify_service.enqueue_booking_cancelled(db, b)

        db.expire_all()
        assert upcoming_log.status == 3  # skipped


# ── Process pending logs ──────────────────────────────────────────────────────

class TestProcessPending:
    def test_skips_future_planned_logs(self, db: Session):
        u = make_user(db, "proc1")
        future_log = NotifyLog(
            user_id=u.id, booking_id=None,
            template_key="booking_upcoming", scene="booking_upcoming",
            status=0,
            planned_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        )
        db.add(future_log); db.commit()

        count = notify_service.process_pending_logs(db)
        assert count == 0  # future log should not be processed

    def test_processes_due_logs(self, db: Session):
        r = make_room(db); u = make_user(db, "proc2")
        b = make_booking_obj(db, r.id, u.id)

        # Create a past-due pending log
        past_log = NotifyLog(
            user_id=u.id, booking_id=b.id,
            template_key="booking_upcoming", scene="booking_upcoming",
            status=0,
            planned_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        )
        db.add(past_log); db.commit()

        count = notify_service.process_pending_logs(db)
        assert count == 1  # processed (will be skipped since no template, but still processed)
        db.expire_all()
        assert past_log.status in (1, 3)  # sent or skipped (not pending)


# ── Integration: booking creation enqueues notification ───────────────────────

class TestBookingNotifyIntegration:
    def test_booking_create_does_not_fail_on_notify_error(self, db: Session):
        """Notification failure must not block booking creation (CLAUDE.md)."""
        r = make_room(db); u = make_user(db, "bnotify1")
        grant(db, r, u)

        from app.schemas.booking import BookingCreateRequest
        from app.services import booking_service
        # Even if notify service has an error, booking should succeed
        with patch("app.services.notify_service.enqueue_booking_success",
                   side_effect=RuntimeError("notify error")):
            b = booking_service.create(db, u.id, BookingCreateRequest(
                room_id=r.id, date=_FUTURE_DATE,
                start_time="14:00", end_time="15:00",
            ))
        assert b.id is not None
        assert b.status == 1

    def test_admin_cancel_enqueues_cancelled_notification(self, db: Session):
        r = make_room(db); u = make_user(db, "bnotify2")
        b = make_booking_obj(db, r.id, u.id)

        enqueued = []
        original = notify_service.enqueue_booking_cancelled
        with patch.object(notify_service, "enqueue_booking_cancelled",
                          side_effect=lambda db, b: enqueued.append(b.id) or original(db, b)):
            from app.services import admin_service
            admin_service.admin_cancel_booking(db, b.id, admin_id=1, reason="test")

        assert b.id in enqueued

    def test_user_self_cancel_does_not_enqueue_notification(self, db: Session):
        r = make_room(db); u = make_user(db, "bnotify3")
        grant(db, r, u)

        from app.schemas.booking import BookingCreateRequest
        from app.services import booking_service
        b = booking_service.create(db, u.id, BookingCreateRequest(
            room_id=r.id, date=date(2030, 12, 1),
            start_time="09:00", end_time="10:00",
        ))
        with patch.object(notify_service, "enqueue_booking_cancelled") as mock_enq:
            booking_service.cancel_by_user(db, b.id, u.id, reason="self cancel")
            mock_enq.assert_not_called()


# ── Subscribe report API ──────────────────────────────────────────────────────

class TestSubscribeReportAPI:
    def test_report_via_endpoint(self, client, db: Session):
        from tests.test_booking import user_token
        u = make_user(db, "api_sub1")
        resp = client.post(
            "/api/notify/subscribe-report",
            json={"results": {"booking_success": "accept", "booking_upcoming": "accept"}},
            headers={"Authorization": f"Bearer {user_token(u)}"},
        )
        assert resp.json()["code"] == 0
        assert get_quota(db, u.id, "booking_success") == 1
        assert get_quota(db, u.id, "booking_upcoming") == 1
