import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import configure_logging, settings
from app.core.exceptions import BusinessException, business_exception_handler, unhandled_exception_handler
from app.middlewares import RequestLoggingMiddleware
from app.api.router import router

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _warn_default_password()
    logger.info("Meeting-room backend starting up")
    from app import scheduler
    scheduler.start()
    yield
    scheduler.stop()
    logger.info("Meeting-room backend shut down")


def _warn_default_password() -> None:
    import os

    if os.environ.get("INIT_ADMIN_PASSWORD", "admin123") == "admin123":
        msg = (
            "\033[1;31m"  # bold red
            "[SECURITY WARNING] INIT_ADMIN_PASSWORD is still the default 'admin123'. "
            "Please change it immediately after first login!"
            "\033[0m"
        )
        logger.warning(msg)


app = FastAPI(
    title="会议室预订系统",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ───────────────────────────────────────────────────────
app.add_exception_handler(BusinessException, business_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(router, prefix="/api")
