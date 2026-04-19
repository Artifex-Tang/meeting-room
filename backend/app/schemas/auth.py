from datetime import datetime

from pydantic import BaseModel


class WechatLoginRequest(BaseModel):
    code: str
    nickname: str | None = None
    avatar_url: str | None = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    openid: str
    nickname: str | None = None
    real_name: str | None = None
    dept_id: int | None = None
    status: int

    model_config = {"from_attributes": True}


class AdminOut(BaseModel):
    id: int
    username: str
    real_name: str | None = None
    must_change_password: int
    status: int

    model_config = {"from_attributes": True}


class WechatLoginData(BaseModel):
    token: str
    expire_at: datetime
    user: UserOut
    need_profile: bool


class AdminLoginData(BaseModel):
    token: str
    expire_at: datetime
    admin: AdminOut
