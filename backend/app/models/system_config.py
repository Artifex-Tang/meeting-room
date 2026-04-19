from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    # `key` is a MySQL reserved word; map DB column "key" to Python attr config_key
    config_key: Mapped[str] = mapped_column("key", String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
