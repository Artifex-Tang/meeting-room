from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import check_rate
from app.core.response import ok
from app.deps import get_db
from app.schemas.auth import (
    AdminLoginData,
    AdminLoginRequest,
    AdminOut,
    UserOut,
    WechatLoginData,
    WechatLoginRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/wechat", summary="微信小程序登录")
async def wechat_login(req: WechatLoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    check_rate(f"wechat_login:{ip}", limit=10, window=60)
    result = await auth_service.wechat_login(db, req.code, req.nickname, req.avatar_url)
    data = WechatLoginData(
        token=result["token"],
        expire_at=result["expire_at"],
        user=UserOut.model_validate(result["user"]),
        need_profile=result["need_profile"],
    )
    return ok(data.model_dump())


@router.post("/admin/login", summary="管理员登录")
def admin_login(req: AdminLoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    check_rate(f"admin_login:{ip}:{req.username}", limit=5, window=60)
    result = auth_service.admin_login(db, req.username, req.password)
    data = AdminLoginData(
        token=result["token"],
        expire_at=result["expire_at"],
        admin=AdminOut.model_validate(result["admin"]),
    )
    return ok(data.model_dump())
