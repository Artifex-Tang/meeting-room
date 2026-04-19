from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.core.exceptions import BusinessException

_ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(sub: str, role: str, expire_hours: int) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=expire_hours)
    payload = {"sub": sub, "role": role, "exp": expire, "iat": now}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)
    return token, expire


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise BusinessException(40101, "token 无效或已过期") from exc
