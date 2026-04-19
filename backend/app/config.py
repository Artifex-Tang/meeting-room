import logging
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    """Walk up from cwd to find .env (works whether running from backend/ or project root)."""
    for candidate in [Path(".env"), Path("../.env")]:
        if candidate.exists():
            return str(candidate)
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str

    # Redis (optional)
    redis_url: str = ""

    # JWT
    jwt_secret: str
    jwt_expire_hours_user: int = 168
    jwt_expire_hours_admin: int = 2

    # WeChat mini-program
    wechat_appid: str = ""
    wechat_secret: str = ""
    wechat_mock: bool = False

    # Admin bootstrap
    init_admin_username: str = "admin"
    init_admin_password: str = "admin123"

    # Scheduler
    run_scheduler: bool = True

    # Logging
    log_level: str = "INFO"


settings = Settings()


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
