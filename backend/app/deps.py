from collections.abc import Generator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.security import decode_access_token
from app.db import SessionLocal
from app.models.admin_user import AdminUser
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise BusinessException(40101, "未提供认证 token")
    payload = decode_access_token(credentials.credentials)
    if payload.get("role") != "user":
        raise BusinessException(40101, "无效的 token 角色")
    user = db.get(User, int(payload["sub"]))
    if not user or user.status != 1:
        raise BusinessException(40101, "用户不存在或已禁用")
    return user


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> AdminUser:
    if not credentials:
        raise BusinessException(40101, "未提供认证 token")
    payload = decode_access_token(credentials.credentials)
    if payload.get("role") != "admin":
        raise BusinessException(40101, "无效的 token 角色")
    admin = db.get(AdminUser, int(payload["sub"]))
    if not admin or admin.status != 1:
        raise BusinessException(40101, "管理员不存在或已禁用")
    return admin
