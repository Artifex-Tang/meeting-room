"""Tests for T-BE-04 (JWT), T-BE-05 (wechat stub), T-BE-06 (admin login)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.admin_user import AdminUser


# ── Password hashing (T-BE-04) ───────────────────────────────────────────────
class TestPasswordHashing:
    def test_hash_and_verify_correct(self):
        pw = "supersecret"
        assert verify_password(pw, hash_password(pw))

    def test_wrong_password_fails(self):
        assert not verify_password("wrong", hash_password("correct"))

    def test_two_hashes_differ(self):
        pw = "same"
        assert hash_password(pw) != hash_password(pw)  # different salts


# ── JWT (T-BE-04) ─────────────────────────────────────────────────────────────
class TestJWT:
    def test_create_and_decode(self):
        token, expire_at = create_access_token("42", "admin", 2)
        payload = decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "admin"

    def test_invalid_token_raises_401(self):
        with pytest.raises(BusinessException) as exc_info:
            decode_access_token("invalid.token.here")
        assert exc_info.value.code == 40101

    def test_tampered_token_raises_401(self):
        token, _ = create_access_token("1", "user", 1)
        tampered = token[:-4] + "XXXX"
        with pytest.raises(BusinessException):
            decode_access_token(tampered)


# ── Admin login (T-BE-06) ─────────────────────────────────────────────────────
class TestAdminLogin:
    def _insert_admin(self, db: Session, username: str, password: str, status: int = 1) -> AdminUser:
        admin = AdminUser(
            username=username,
            password_hash=hash_password(password),
            must_change_password=0,
            status=status,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin

    def test_happy_path(self, client: TestClient, db: Session):
        self._insert_admin(db, "testadmin", "pass123")
        resp = client.post("/api/auth/admin/login", json={"username": "testadmin", "password": "pass123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "token" in body["data"]
        assert body["data"]["admin"]["username"] == "testadmin"

    def test_wrong_password(self, client: TestClient, db: Session):
        self._insert_admin(db, "admin2", "correctpass")
        resp = client.post("/api/auth/admin/login", json={"username": "admin2", "password": "wrong"})
        assert resp.json()["code"] == 40001

    def test_nonexistent_user(self, client: TestClient):
        resp = client.post("/api/auth/admin/login", json={"username": "nobody", "password": "x"})
        assert resp.json()["code"] == 40001

    def test_disabled_admin_denied(self, client: TestClient, db: Session):
        self._insert_admin(db, "disabled", "pass", status=0)
        resp = client.post("/api/auth/admin/login", json={"username": "disabled", "password": "pass"})
        assert resp.json()["code"] == 40001

    def test_token_is_decodable(self, client: TestClient, db: Session):
        self._insert_admin(db, "jwtadmin", "jwtpass")
        resp = client.post("/api/auth/admin/login", json={"username": "jwtadmin", "password": "jwtpass"})
        token = resp.json()["data"]["token"]
        payload = decode_access_token(token)
        assert payload["role"] == "admin"


# ── WeChat login mock (T-BE-05) ───────────────────────────────────────────────
class TestWechatLogin:
    """WECHAT_MOCK=true in .env, so code is used as openid."""

    def test_first_login_creates_user(self, client: TestClient):
        resp = client.post("/api/auth/wechat", json={"code": "testcode001", "nickname": "Alice"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "token" in body["data"]
        assert body["data"]["user"]["nickname"] == "Alice"
        assert body["data"]["need_profile"] is True  # real_name is null

    def test_second_login_returns_same_user(self, client: TestClient):
        resp1 = client.post("/api/auth/wechat", json={"code": "samecode"})
        resp2 = client.post("/api/auth/wechat", json={"code": "samecode"})
        assert resp1.json()["data"]["user"]["id"] == resp2.json()["data"]["user"]["id"]

    def test_token_role_is_user(self, client: TestClient):
        resp = client.post("/api/auth/wechat", json={"code": "rolecheck"})
        token = resp.json()["data"]["token"]
        assert decode_access_token(token)["role"] == "user"


# ── Protected endpoint requires token (T-BE-04 deps) ─────────────────────────
class TestAuthDeps:
    def test_missing_token_returns_401(self, client: TestClient):
        # /api/ping is unprotected; use a future protected endpoint stub
        # For now verify the bearer scheme rejects missing header via decode
        with pytest.raises(BusinessException) as exc_info:
            decode_access_token("")
        assert exc_info.value.code == 40101
