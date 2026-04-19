from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotifyQuota(Base):
    __tablename__ = "notify_quota"
    __table_args__ = (UniqueConstraint("user_id", "template_key", name="uk_user_template"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    template_key: Mapped[str] = mapped_column(String(32), nullable=False)
    quota: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class NotifyLog(Base):
    __tablename__ = "notify_log"
    __table_args__ = (
        Index("idx_booking_scene", "booking_id", "scene"),
        Index("idx_planned", "status", "planned_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    booking_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    template_key: Mapped[str] = mapped_column(String(32), nullable=False)
    scene: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    errmsg: Mapped[str | None] = mapped_column(String(500), nullable=True)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class OperationLog(Base):
    __tablename__ = "operation_log"
    __table_args__ = (Index("idx_actor", "actor_type", "actor_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
