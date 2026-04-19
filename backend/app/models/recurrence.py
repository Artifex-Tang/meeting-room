from datetime import date, datetime, time

from sqlalchemy import BigInteger, Date, DateTime, Integer, SmallInteger, String, Time, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BookingRecurrence(Base):
    __tablename__ = "booking_recurrence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    room_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)      # DAILY / WEEKLY / MONTHLY
    weekdays: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "1,3,5"
    month_day: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 1-31
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
