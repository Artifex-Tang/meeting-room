from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
async def wechat_login(req: WechatLoginRequest, db: Session = Depends(get_db)) -> dict:
    result = await auth_service.wechat_login(db, req.code, req.nickname, req.avatar_url)
    data = WechatLoginData(
        token=result["token"],
        expire_at=result["expire_at"],
        user=UserOut.model_validate(result["user"]),
        need_profile=result["need_profile"],
    )
    return ok(data.model_dump())


@router.post("/admin/login", summary="管理员登录")
def admin_login(req: AdminLoginRequest, db: Session = Depends(get_db)) -> dict:
    result = auth_service.admin_login(db, req.username, req.password)
    data = AdminLoginData(
        token=result["token"],
        expire_at=result["expire_at"],
        admin=AdminOut.model_validate(result["admin"]),
    )
    return ok(data.model_dump())
