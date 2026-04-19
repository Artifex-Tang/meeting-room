from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.response import ok
from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import UserOut
from app.services import config_service

router = APIRouter(tags=["users"])


class UpdateProfileRequest(BaseModel):
    real_name: str | None = None


@router.put("/users/me", summary="更新当前用户资料")
def update_profile(
    req: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if req.real_name is not None:
        real_name = req.real_name.strip()
        if not real_name:
            raise BusinessException(40001, "真实姓名不能为空")
        current_user.real_name = real_name
    db.commit()
    db.refresh(current_user)
    return ok(UserOut.model_validate(current_user).model_dump())


# Public config keys exposed to miniapp (read-only subset)
_PUBLIC_KEYS = {"cancel_advance_hours", "advance_booking_days", "max_booking_hours"}


@router.get("/config/public", summary="小程序可读系统参数（无需鉴权）")
def public_config(db: Session = Depends(get_db)) -> dict:
    result = {key: config_service.get(db, key) for key in _PUBLIC_KEYS}
    return ok(result)
