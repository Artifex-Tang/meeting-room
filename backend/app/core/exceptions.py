from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.response import fail


class BusinessException(Exception):
    def __init__(self, code: int, message: str, data: Any = None) -> None:
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


# ── HTTP status mapping ──────────────────────────────────────────────────────
_CODE_TO_HTTP: dict[int, int] = {
    40001: 400,
    40101: 401,
    40301: 403,
    40401: 404,
    40901: 409,
    40902: 409,
    42201: 422,
    50000: 500,
}


def business_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    http_status = _CODE_TO_HTTP.get(exc.code, 400)
    return JSONResponse(status_code=http_status, content=fail(exc.code, exc.message, exc.data))


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging

    logging.getLogger(__name__).exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content=fail(50000, "服务端异常"))
