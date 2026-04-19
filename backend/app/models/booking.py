from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Booking(Base):
    __tablename__ = "booking"
    __table_args__ = (
        Index("idx_room_date", "room_id", "date", "status"),
        Index("idx_user_date", "user_id", "date", "status"),
        Index("idx_recurrence", "recurrence_id"),
        Index("idx_time_range", "room_id", "start_at", "end_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recurrence_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    preset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attendees: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    cancel_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancelled_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cancel_source: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
