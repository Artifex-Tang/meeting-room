from datetime import datetime

from sqlalchemy import BigInteger, DateTime, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RoomUserPermission(Base):
    __tablename__ = "room_user_permission"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uk_room_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    granted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class RoomDeptPermission(Base):
    __tablename__ = "room_dept_permission"
    __table_args__ = (UniqueConstraint("room_id", "dept_id", name="uk_room_dept"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dept_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    granted_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
