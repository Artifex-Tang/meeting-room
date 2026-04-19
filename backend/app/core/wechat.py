# T-BE-05 will implement the real code2session call here.
# WECHAT_MOCK=true returns the code itself as openid (dev convenience).

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


async def code2session(code: str) -> dict:
    """Exchange a wx.login() code for openid/session_key.

    Returns a dict with at least ``openid`` key.
    Raises ``RuntimeError`` on WeChat API error.
    """
    if settings.wechat_mock:
        logger.warning("WECHAT_MOCK=true — using code as openid (dev only)")
        return {"openid": f"mock_{code}", "session_key": "mock"}

    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_CODE2SESSION_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if "errcode" in data and data["errcode"] != 0:
        raise RuntimeError(f"WeChat code2session error {data['errcode']}: {data.get('errmsg')}")

    return data
