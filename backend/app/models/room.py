from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Room(Base):
    __tablename__ = "room"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    facilities: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
