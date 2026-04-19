from datetime import datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminUser(Base):
    __tablename__ = "admin_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    must_change_password: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
