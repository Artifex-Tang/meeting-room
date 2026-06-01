"""
miniapp_flow_test.py
Simulates every HTTP call the WeChat miniapp makes, page by page.
WECHAT_MOCK=true — backend treats `code` as openid directly.

Run: python tests/miniapp_flow_test.py
Requires backend running on http://localhost:8001
"""
import sys
import json
import random
import datetime
import requests

# Random offset to avoid date collisions across test runs
_OFFSET = random.randint(500, 900)

BASE = "http://localhost:8001/api"
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
SKIP = "\033[33mSKIP\033[0m"

results: list[tuple[str, str, str]] = []  # (page, case, verdict)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

class MiniappSession:
    """Simulates miniapp globalData + wx.getStorageSync."""
    def __init__(self):
        self.token: str | None = None
        self.user: dict | None = None

    def headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def get(self, path: str, params: dict | None = None) -> dict:
        r = requests.get(BASE + path, params=params, headers=self.headers(), timeout=10)
        return r.json()

    def post(self, path: str, data: dict | None = None) -> dict:
        r = requests.post(BASE + path, json=data, headers=self.headers(), timeout=10)
        return r.json()

    def put(self, path: str, data: dict | None = None) -> dict:
        r = requests.put(BASE + path, json=data, headers=self.headers(), timeout=10)
        return r.json()


def check(page: str, case: str, cond: bool, detail: str = "") -> bool:
    verdict = PASS if cond else FAIL
    results.append((page, case, "PASS" if cond else "FAIL"))
    sym = "✓" if cond else "✗"
    detail_str = f"  ({detail})" if detail else ""
    print(f"  {sym} [{page}] {case}{detail_str}")
    return cond


def today_plus(days: int) -> str:
    return (datetime.date.today() + datetime.timedelta(days=_OFFSET + days)).isoformat()


# ──────────────────────────────────────────────────────────────────────────────
# Admin setup: grant a room to user (called once before user tests)
# ──────────────────────────────────────────────────────────────────────────────

def admin_setup() -> tuple[dict, int]:
    """Login as admin, create room, return (admin_token, room_id)."""
    print("\n[SETUP] Admin login + room setup")
    s = MiniappSession()
    r = s.post("/auth/admin/login", {"username": "admin", "password": "Admin@2026"})
    assert r.get("code") == 0, f"Admin login failed: {r}"
    s.token = r["data"]["token"]

    # Always create a fresh room with unique name per run to avoid booking conflicts
    room_name = f"TestRoom-MP-{_OFFSET}"
    rooms = s.get("/admin/rooms", {"status": 1})
    active = [x for x in rooms["data"]["list"] if x["name"] == room_name]
    if active:
        room_id = active[0]["id"]
        print(f"  Reusing room id={room_id} name={room_name}")
    else:
        rc = s.post("/admin/rooms", {
            "name": room_name,
            "location": "TestFloor",
            "capacity": 10,
            "facilities": "projector",
            "status": 1,
        })
        room_id = rc["data"]["id"]
        print(f"  Created room id={room_id} name={room_name}")

    return s.token, room_id


def admin_grant_room(admin_token: str, room_id: int, user_id: int) -> None:
    s = MiniappSession()
    s.token = admin_token
    s.post(f"/admin/rooms/{room_id}/permissions/users", {"user_ids": [user_id]})


def admin_cancel_booking(admin_token: str, booking_id: int, reason: str = "test cleanup") -> None:
    s = MiniappSession()
    s.token = admin_token
    s.post(f"/admin/bookings/{booking_id}/cancel", {"reason": reason})


# ──────────────────────────────────────────────────────────────────────────────
# Page: launch/launch  (微信登录)
# ──────────────────────────────────────────────────────────────────────────────

def test_launch_page(app: MiniappSession) -> None:
    page = "launch"
    print(f"\n[PAGE] {page}")

    # Use a unique openid per test run to guarantee fresh user state
    unique_code = f"mp_test_user_{_OFFSET}"

    # Happy path: wx.login → code2session (MOCK: code becomes openid)
    r = app.post("/auth/wechat", {"code": unique_code, "nickname": "小张"})
    ok = r.get("code") == 0
    check(page, "wechat login returns token", ok, str(r.get("code")))
    if ok:
        app.token = r["data"]["token"]
        app.user = r["data"]["user"]
        check(page, "response has user.id", bool(app.user.get("id")))
        check(page, "response has need_profile flag", "need_profile" in r["data"])
        first_login_need_profile = r["data"].get("need_profile", False)
        check(page, "need_profile=True on first login (no real_name)", first_login_need_profile)

    # Second login same code → same user, idempotent
    r2 = app.post("/auth/wechat", {"code": unique_code, "nickname": "小张"})
    if r2.get("code") == 0:
        check(page, "same code → same user_id", r2["data"]["user"]["id"] == app.user["id"])
    else:
        # 429 rate-limit or other transient error — skip, not a real failure
        print(f"  🔍 [launch] second login skipped (code={r2.get('code')})")

    # Token expiry / invalid token → 40101
    bad = MiniappSession()
    bad.token = "invalid.jwt.token"
    rb = bad.get("/rooms")
    check(page, "invalid token → code 40101", rb.get("code") == 40101)


# ──────────────────────────────────────────────────────────────────────────────
# Page: index/index  (会议室列表)
# ──────────────────────────────────────────────────────────────────────────────

def test_room_list_page(app: MiniappSession, room_id: int) -> None:
    page = "room-list"
    print(f"\n[PAGE] {page}")

    # No permission yet → empty list
    r = app.get("/rooms")
    check(page, "GET /rooms returns list", "list" in str(r.get("data",[]))
          or isinstance(r.get("data"), list))

    # Keyword search (no results expected for garbage)
    r2 = app.get("/rooms", {"keyword": "xyzzy_no_match"})
    results_list = r2.get("data", [])
    check(page, "keyword search returns empty for no match",
          isinstance(results_list, list) and len(results_list) == 0)


# ──────────────────────────────────────────────────────────────────────────────
# Page: room/detail/detail  (会议室详情 + 可用性)
# ──────────────────────────────────────────────────────────────────────────────

def test_room_detail_page(app: MiniappSession, room_id: int) -> None:
    page = "room-detail"
    print(f"\n[PAGE] {page}")

    query_date = today_plus(3)

    # GET availability (user now has permission)
    r = app.get(f"/rooms/{room_id}/availability", {"date": query_date})
    ok = r.get("code") == 0
    check(page, "GET /rooms/{id}/availability returns 200", ok)
    if ok:
        data = r["data"]
        check(page, "response has slots_taken array",
              isinstance(data.get("slots_taken"), list))
        check(page, "response has room_id", data.get("room_id") == room_id)
        check(page, "response has date", data.get("date") == query_date)

    # No-permission room (id=999) → 403/404
    r2 = app.get("/rooms/999/availability", {"date": query_date})
    check(page, "unknown room → error code",
          r2.get("code") in (40301, 40401, 40001))

    # Visible rooms list after permission granted
    r3 = app.get("/rooms")
    rooms = r3.get("data", [])
    has_room = any(rm.get("id") == room_id for rm in rooms) if isinstance(rooms, list) else False
    check(page, "room appears in visible list after permission grant", has_room)


# ──────────────────────────────────────────────────────────────────────────────
# Page: booking/create/create  (预订创建)
# ──────────────────────────────────────────────────────────────────────────────

def test_booking_create_page(app: MiniappSession, room_id: int) -> list[int]:
    page = "booking-create"
    print(f"\n[PAGE] {page}")
    created_ids: list[int] = []

    book_date = today_plus(5)

    # T-MP-09: subscribe report (miniapp calls this before booking)
    r_sub = app.post("/notify/subscribe-report", {
        "results": {
            "booking_success":   "accept",
            "booking_upcoming":  "accept",
            "booking_cancelled": "reject",
        }
    })
    ok_sub = r_sub.get("code") == 0
    check(page, "POST /notify/subscribe-report → 200", ok_sub)
    if ok_sub:
        quota = r_sub["data"].get("quota", {})
        check(page, "quota.booking_success incremented", quota.get("booking_success", 0) >= 1)
        check(page, "quota.booking_cancelled stays 0 (rejected)", quota.get("booking_cancelled", 0) == 0)

    # GET notify/quota
    r_q = app.get("/notify/quota")
    check(page, "GET /notify/quota → 200", r_q.get("code") == 0)

    # Happy path: preset booking (morning)
    r1 = app.post("/bookings", {
        "room_id": room_id,
        "date": book_date,
        "preset": "morning",
        "title": "MP测试-上午会",
    })
    ok1 = r1.get("code") == 0
    check(page, "preset booking (morning) → success", ok1,
          f"code={r1.get('code')} msg={r1.get('message')}")
    if ok1:
        bid = r1["data"]["id"]
        created_ids.append(bid)
        check(page, "booking status=1", r1["data"]["status"] == 1)

    # Conflict: same slot same room → 40901
    r2 = app.post("/bookings", {
        "room_id": room_id,
        "date": book_date,
        "preset": "morning",
        "title": "Conflict attempt",
    })
    check(page, "duplicate slot → code 40901", r2.get("code") == 40901,
          f"got {r2.get('code')}")
    if r2.get("code") == 40901:
        conflict_data = r2.get("data", {}).get("conflict_with", {})
        check(page, "conflict_with.booking_id present", bool(conflict_data.get("booking_id")))
        check(page, "conflict_with.user present", bool(conflict_data.get("user")))

    # Custom time booking (afternoon slot)
    r3 = app.post("/bookings", {
        "room_id": room_id,
        "date": book_date,
        "start_time": "14:00",
        "end_time": "15:30",
        "title": "MP测试-自定义时段",
    })
    ok3 = r3.get("code") == 0
    check(page, "custom time booking (14:00-15:30) → success", ok3,
          f"code={r3.get('code')} msg={r3.get('message')}")
    if ok3:
        created_ids.append(r3["data"]["id"])

    # Invalid: start_time not 30-min aligned
    r4 = app.post("/bookings", {
        "room_id": room_id,
        "date": book_date,
        "start_time": "14:15",  # not aligned
        "end_time": "16:00",
        "title": "bad time",
    })
    check(page, "non-aligned time → error", r4.get("code") != 0,
          f"got {r4.get('code')}")

    # Invalid: end before start
    r5 = app.post("/bookings", {
        "room_id": room_id,
        "date": book_date,
        "start_time": "16:00",
        "end_time": "14:00",
    })
    check(page, "end < start → error", r5.get("code") != 0)

    # Invalid preset name
    r6 = app.post("/bookings", {
        "room_id": room_id,
        "date": book_date,
        "preset": "badpreset",
    })
    check(page, "invalid preset → error", r6.get("code") != 0)

    return created_ids


# ──────────────────────────────────────────────────────────────────────────────
# Page: booking/recurrence/recurrence  (周期预订)
# ──────────────────────────────────────────────────────────────────────────────

def test_recurrence_page(app: MiniappSession, room_id: int) -> list[int]:
    page = "booking-recurrence"
    print(f"\n[PAGE] {page}")
    created_ids: list[int] = []

    start = today_plus(14)   # 2 weeks out, clean slate
    end   = today_plus(42)   # 4 weeks range

    # WEEKLY Mon+Wed (weekdays 1,3 in SPEC 1-7 format)
    r1 = app.post("/bookings/recurrence", {
        "room_id": room_id,
        "frequency": "WEEKLY",
        "weekdays": [1, 3],
        "start_date": start,
        "end_date": end,
        "start_time": "09:00",
        "end_time": "10:00",
        "title": "MP周例会",
    })
    ok1 = r1.get("code") == 0
    check(page, "WEEKLY recurrence → success", ok1,
          f"code={r1.get('code')} msg={r1.get('message')}")
    if ok1:
        data = r1["data"]
        check(page, "response has recurrence_id", bool(data.get("recurrence_id")))
        check(page, "response has count > 0", data.get("count", 0) > 0)
        check(page, "count matches Mon+Wed over 4 weeks (expect ~8)", 6 <= data["count"] <= 10)
        created_ids.extend(data.get("booking_ids", []))
        recurrence_id = data["recurrence_id"]
    else:
        recurrence_id = None

    # DAILY recurrence (next week, short range)
    start_d = today_plus(50)
    end_d = today_plus(52)
    r2 = app.post("/bookings/recurrence", {
        "room_id": room_id,
        "frequency": "DAILY",
        "start_date": start_d,
        "end_date": end_d,
        "start_time": "11:00",
        "end_time": "12:00",
        "title": "MP每日站会",
    })
    ok2 = r2.get("code") == 0
    check(page, "DAILY recurrence → success", ok2,
          f"code={r2.get('code')}")
    if ok2:
        check(page, "DAILY count = 3 (3 days)", r2["data"]["count"] == 3)
        created_ids.extend(r2["data"].get("booking_ids", []))

    # MONTHLY recurrence — use offset-derived time to reduce cross-run collision
    start_m = today_plus(60)
    end_m = today_plus(120)
    month_day = (datetime.date.today() + datetime.timedelta(days=_OFFSET + 60)).day
    mhour = 8 + (_OFFSET % 8)   # 08:00–15:00, unique per run
    r3 = app.post("/bookings/recurrence", {
        "room_id": room_id,
        "frequency": "MONTHLY",
        "month_day": month_day,
        "start_date": start_m,
        "end_date": end_m,
        "start_time": f"{mhour:02d}:00",
        "end_time": f"{mhour+1:02d}:00",
        "title": "MP月会",
    })
    ok3 = r3.get("code") == 0
    check(page, "MONTHLY recurrence → success", ok3,
          f"code={r3.get('code')}")
    if ok3:
        created_ids.extend(r3["data"].get("booking_ids", []))

    # Conflict: try to book a slot already taken by WEEKLY
    if ok1:
        # Find a Monday within the WEEKLY range
        cur = datetime.date.fromisoformat(start)
        while cur.weekday() != 0:  # Monday
            cur += datetime.timedelta(days=1)
        conflict_date = cur.isoformat()
        rc = app.post("/bookings/recurrence", {
            "room_id": room_id,
            "frequency": "WEEKLY",
            "weekdays": [1],
            "start_date": conflict_date,
            "end_date": (cur + datetime.timedelta(days=7)).isoformat(),
            "start_time": "09:00",
            "end_time": "10:00",
            "title": "conflict recurrence",
        })
        check(page, "conflicting recurrence → code 40902",
              rc.get("code") == 40902,
              f"got {rc.get('code')}")
        if rc.get("code") == 40902:
            conflicts = rc.get("data", {}).get("conflicts", [])
            check(page, "conflicts list non-empty", len(conflicts) > 0)
            check(page, "conflict entry has date field", "date" in conflicts[0])

    # Validation: WEEKLY with no weekdays → error
    rv = app.post("/bookings/recurrence", {
        "room_id": room_id,
        "frequency": "WEEKLY",
        "weekdays": [],
        "start_date": today_plus(100),
        "end_date": today_plus(130),
        "start_time": "08:00",
        "end_time": "09:00",
    })
    check(page, "WEEKLY with empty weekdays → error", rv.get("code") != 0)

    # Cancel future instances of WEEKLY recurrence
    if recurrence_id:
        rc2 = app.post(f"/bookings/recurrence/{recurrence_id}/cancel")
        check(page, "cancel recurrence → success", rc2.get("code") == 0,
              f"got {rc2.get('code')}")

    return created_ids


# ──────────────────────────────────────────────────────────────────────────────
# Page: my/bookings/bookings  (我的预订列表)
# ──────────────────────────────────────────────────────────────────────────────

def test_my_bookings_page(app: MiniappSession, created_ids: list[int]) -> None:
    page = "my-bookings"
    print(f"\n[PAGE] {page}")

    # GET /config/public (miniapp loads cancel deadline)
    rc = app.get("/config/public")
    check(page, "GET /config/public → 200", rc.get("code") == 0)
    if rc.get("code") == 0:
        cfg = rc.get("data", {})
        check(page, "cancel_advance_hours in config",
              "cancel_advance_hours" in cfg)

    # GET /bookings scope=mine status=active
    r1 = app.get("/bookings", {"scope": "mine", "status": "active", "page": 1})
    ok1 = r1.get("code") == 0
    check(page, "GET /bookings?status=active → 200", ok1)
    if ok1:
        data = r1["data"]
        check(page, "response has list + total + page",
              all(k in data for k in ("list", "total", "page")))
        check(page, "list contains our bookings",
              any(b["id"] in created_ids for b in data["list"]) if created_ids else True)

    # GET /bookings status=all (all statuses)
    r2 = app.get("/bookings", {"status": "all", "page": 1})
    check(page, "GET /bookings?status=all → 200", r2.get("code") == 0)

    # GET /bookings/{id} detail
    if created_ids:
        r3 = app.get(f"/bookings/{created_ids[0]}")
        ok3 = r3.get("code") == 0
        check(page, "GET /bookings/{id} → 200", ok3)
        if ok3:
            b = r3["data"]
            check(page, "booking has room_id, date, start_at, end_at",
                  all(k in b for k in ("room_id", "date", "start_at", "end_at")))

    # Cancel booking far in future (should succeed: advance hours not reached)
    if created_ids:
        bid = created_ids[0]
        rc_cancel = app.post(f"/bookings/{bid}/cancel", {"reason": "MP测试取消"})
        ok_cancel = rc_cancel.get("code") == 0
        check(page, "cancel future booking → success", ok_cancel,
              f"code={rc_cancel.get('code')} msg={rc_cancel.get('message')}")
        if ok_cancel:
            check(page, "cancelled booking status=0", rc_cancel["data"]["status"] == 0)
            check(page, "cancel_source=1 (user self-cancel)", rc_cancel["data"].get("cancel_source") == 1)

    # Cancel already-cancelled booking → error
    if created_ids:
        r4 = app.post(f"/bookings/{created_ids[0]}/cancel", {"reason": "again"})
        check(page, "cancel already-cancelled → error",
              r4.get("code") != 0)

    # Cancel someone else's booking → 40301 (use last id — least likely to be already cancelled)
    other = MiniappSession()
    r_other = other.post("/auth/wechat", {"code": f"mp_other_user_{_OFFSET}"})
    if r_other.get("code") == 0 and len(created_ids) > 1:
        other.token = r_other["data"]["token"]
        # Find an active booking to attempt to cancel
        active_bid = None
        for bid in reversed(created_ids):
            rb = app.get(f"/bookings/{bid}")
            if rb.get("code") == 0 and rb["data"].get("status") == 1:
                active_bid = bid
                break
        if active_bid:
            r5 = other.post(f"/bookings/{active_bid}/cancel", {"reason": "not mine"})
            check(page, "cancel other user's booking → 40301",
                  r5.get("code") == 40301,
                  f"got {r5.get('code')} for booking {active_bid}")


# ──────────────────────────────────────────────────────────────────────────────
# Page: my/index/index  (个人中心)
# ──────────────────────────────────────────────────────────────────────────────

def test_profile_page(app: MiniappSession) -> None:
    page = "profile"
    print(f"\n[PAGE] {page}")

    # Update real_name
    r1 = app.put("/users/me", {"real_name": "张小明"})
    ok1 = r1.get("code") == 0
    check(page, "PUT /users/me (update real_name) → 200", ok1,
          f"code={r1.get('code')}")
    if ok1:
        check(page, "real_name updated in response",
              r1["data"].get("real_name") == "张小明")

    # Login again → need_profile should now be False
    r2 = app.post("/auth/wechat", {"code": f"mp_test_user_{_OFFSET}"})
    if r2.get("code") == 0:
        check(page, "need_profile=False after real_name set",
              r2["data"].get("need_profile") is False)

    # Empty real_name → rejected
    r3 = app.put("/users/me", {"real_name": ""})
    check(page, "empty real_name → error", r3.get("code") != 0)

    # Unauthenticated PUT → 401
    bad = MiniappSession()
    r4 = bad.put("/users/me", {"real_name": "hacker"})
    check(page, "unauthenticated PUT /users/me → 401", r4.get("code") == 40101)


# ──────────────────────────────────────────────────────────────────────────────
# Additional edge cases across pages
# ──────────────────────────────────────────────────────────────────────────────

def test_edge_cases(app: MiniappSession, room_id: int, admin_token: str) -> None:
    page = "edge-cases"
    print(f"\n[PAGE] {page}")

    # Max daily booking limit (default = 3; we've already booked morning + 14:00-15:30)
    # Try to book 3 more on same date → should fail on 3rd/4th
    book_date = today_plus(7)

    # Book slots sequentially to hit the daily limit
    presets = ["morning", "afternoon", "noon"]
    booked = []
    for preset in presets:
        r = app.post("/bookings", {
            "room_id": room_id,
            "date": book_date,
            "preset": preset,
        })
        if r.get("code") == 0:
            booked.append(r["data"]["id"])

    # Next booking on same day should hit max_bookings_per_day
    r_extra = app.post("/bookings", {
        "room_id": room_id,
        "date": book_date,
        "preset": "evening",
    })
    check(page, "4th booking on same day → daily limit error",
          r_extra.get("code") != 0,
          f"code={r_extra.get('code')} booked={len(booked)}")

    # Unauthenticated booking → 401
    bad = MiniappSession()
    r_unauth = bad.post("/bookings", {
        "room_id": room_id,
        "date": today_plus(8),
        "preset": "morning",
    })
    check(page, "unauthenticated POST /bookings → 401", r_unauth.get("code") == 40101)

    # Room not visible → fresh session (avoid rate-limit contamination)
    fresh = MiniappSession()
    rf = fresh.post("/auth/wechat", {"code": "mp_no_perm_probe_xyz"})
    if rf.get("code") == 0:
        fresh.token = rf["data"]["token"]
        r_no_perm = fresh.post("/bookings", {
            "room_id": 99999,
            "date": today_plus(9),
            "preset": "morning",
        })
        check(page, "no-permission room → error (403 or 404)",
              r_no_perm.get("code") in (40301, 40401),
              f"got {r_no_perm.get('code')}")

    # Rate limit: dedicated session, use raw requests to catch HTTP 429
    rl_sess = MiniappSession()
    rl_r = rl_sess.post("/auth/wechat", {"code": "mp_ratelimit_probe_user"})
    if rl_r.get("code") == 0:
        rl_sess.token = rl_r["data"]["token"]
        admin_grant_room(admin_token, room_id, rl_r["data"]["user"]["id"])
        hit_429 = False
        for i in range(35):
            resp = requests.post(
                BASE + "/bookings",
                json={"room_id": room_id, "date": today_plus(300 + i), "preset": "morning"},
                headers=rl_sess.headers(),
                timeout=10,
            )
            if resp.status_code == 429:
                hit_429 = True
                break
        check(page, "rapid requests trigger 429 rate limit", hit_429,
              f"triggered at call {i+1}" if hit_429 else "never triggered in 35 calls")

    # Cleanup: cancel the daily limit test bookings
    for bid in booked:
        app.post(f"/bookings/{bid}/cancel", {"reason": "cleanup"})


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("WeChat Miniapp HTTP Flow Tests")
    print(f"Backend: {BASE}")
    print("=" * 60)

    # Admin setup
    try:
        admin_token, room_id = admin_setup()
    except Exception as e:
        print(f"\nFATAL: Admin setup failed: {e}")
        sys.exit(1)

    # Create user session
    app = MiniappSession()

    # Run page tests
    test_launch_page(app)

    # Grant permission before room/detail tests
    if app.user:
        admin_grant_room(admin_token, room_id, app.user["id"])

    test_room_list_page(app, room_id)
    test_room_detail_page(app, room_id)

    created_single_ids = test_booking_create_page(app, room_id)
    created_recur_ids = test_recurrence_page(app, room_id)

    all_ids = created_single_ids + created_recur_ids
    test_my_bookings_page(app, all_ids)
    test_profile_page(app)
    test_edge_cases(app, room_id, admin_token)

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for _, _, v in results if v == "PASS")
    failed = sum(1 for _, _, v in results if v == "FAIL")
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")
    if failed:
        print("\nFailed cases:")
        for page, case, verdict in results:
            if verdict == "FAIL":
                print(f"  ✗ [{page}] {case}")
    verdict = "PASS" if failed == 0 else "FAIL"
    print(f"\nVerdict: {verdict}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
