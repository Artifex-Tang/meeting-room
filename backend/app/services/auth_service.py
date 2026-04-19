import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import BusinessException
from app.core.security import create_access_token, verify_password
from app.core.wechat import code2session
from app.models.admin_user import AdminUser
from app.models.user import User

logger = logging.getLogger(__name__)

_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for DB storage


async def wechat_login(
    db: Session,
    code: str,
    nickname: str | None,
    avatar_url: str | None,  # noqa: ARG001 — stored for future avatar feature
) -> dict:
    wechat_data = await code2session(code)
    openid: str = wechat_data["openid"]
    unionid: str | None = wechat_data.get("unionid")

    user = db.query(User).filter(User.openid == openid).first()
    if user is None:
        user = User(openid=openid, unionid=unionid, nickname=nickname, status=1)
        db.add(user)
        db.flush()
    else:
        if nickname and not user.nickname:
            user.nickname = nickname
        if unionid and not user.unionid:
            user.unionid = unionid

    user.last_login_at = _now()
    db.commit()
    db.refresh(user)

    token, expire_at = create_access_token(str(user.id), "user", settings.jwt_expire_hours_user)
    return {"token": token, "expire_at": expire_at, "user": user, "need_profile": user.real_name is None}


def admin_login(db: Session, username: str, password: str) -> dict:
    admin = (
        db.query(AdminUser)
        .filter(AdminUser.username == username, AdminUser.status == 1)
        .first()
    )
    if admin is None or not verify_password(password, admin.password_hash):
        raise BusinessException(40001, "用户名或密码错误")

    admin.last_login_at = _now()
    db.commit()
    db.refresh(admin)

    token, expire_at = create_access_token(str(admin.id), "admin", settings.jwt_expire_hours_admin)
    return {"token": token, "expire_at": expire_at, "admin": admin}
