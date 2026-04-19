"""Initial schema: all tables, default system_config, default admin user

Revision ID: 0001
Revises:
Create Date: 2026-04-18

"""
import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── department ────────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS department (
          id           BIGINT       PRIMARY KEY AUTO_INCREMENT,
          name         VARCHAR(64)  NOT NULL,
          parent_id    BIGINT       NULL,
          created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          KEY idx_parent (parent_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── user ──────────────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS `user` (
          id             BIGINT       PRIMARY KEY AUTO_INCREMENT,
          openid         VARCHAR(64)  NOT NULL,
          unionid        VARCHAR(64)  NULL,
          nickname       VARCHAR(64)  NULL,
          real_name      VARCHAR(64)  NULL,
          phone          VARCHAR(32)  NULL,
          dept_id        BIGINT       NULL,
          status         TINYINT      NOT NULL DEFAULT 1,
          last_login_at  DATETIME     NULL,
          created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_openid (openid),
          KEY idx_dept (dept_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── admin_user ────────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS admin_user (
          id                    BIGINT       PRIMARY KEY AUTO_INCREMENT,
          username              VARCHAR(64)  NOT NULL,
          password_hash         VARCHAR(128) NOT NULL,
          real_name             VARCHAR(64)  NULL,
          must_change_password  TINYINT      NOT NULL DEFAULT 0,
          status                TINYINT      NOT NULL DEFAULT 1,
          last_login_at         DATETIME     NULL,
          created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_username (username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── room ──────────────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS room (
          id           BIGINT       PRIMARY KEY AUTO_INCREMENT,
          name         VARCHAR(64)  NOT NULL,
          location     VARCHAR(128) NULL,
          capacity     INT          NULL,
          facilities   VARCHAR(255) NULL,
          description  VARCHAR(500) NULL,
          status       TINYINT      NOT NULL DEFAULT 1,
          created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          KEY idx_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── room_user_permission ──────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS room_user_permission (
          id          BIGINT   PRIMARY KEY AUTO_INCREMENT,
          room_id     BIGINT   NOT NULL,
          user_id     BIGINT   NOT NULL,
          granted_by  BIGINT   NULL,
          created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE KEY uk_room_user (room_id, user_id),
          KEY idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── room_dept_permission ──────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS room_dept_permission (
          id          BIGINT   PRIMARY KEY AUTO_INCREMENT,
          room_id     BIGINT   NOT NULL,
          dept_id     BIGINT   NOT NULL,
          granted_by  BIGINT   NULL,
          created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE KEY uk_room_dept (room_id, dept_id),
          KEY idx_dept (dept_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── booking_recurrence ────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS booking_recurrence (
          id             BIGINT       PRIMARY KEY AUTO_INCREMENT,
          user_id        BIGINT       NOT NULL,
          room_id        BIGINT       NOT NULL,
          frequency      VARCHAR(16)  NOT NULL,
          weekdays       VARCHAR(32)  NULL,
          month_day      INT          NULL,
          start_date     DATE         NOT NULL,
          end_date       DATE         NOT NULL,
          start_time     TIME         NOT NULL,
          end_time       TIME         NOT NULL,
          title          VARCHAR(128) NULL,
          status         TINYINT      NOT NULL DEFAULT 1,
          created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          KEY idx_user (user_id),
          KEY idx_room (room_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── booking ───────────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS booking (
          id             BIGINT       PRIMARY KEY AUTO_INCREMENT,
          room_id        BIGINT       NOT NULL,
          user_id        BIGINT       NOT NULL,
          recurrence_id  BIGINT       NULL,
          date           DATE         NOT NULL,
          start_at       DATETIME     NOT NULL,
          end_at         DATETIME     NOT NULL,
          preset         VARCHAR(16)  NULL,
          title          VARCHAR(128) NULL,
          attendees      VARCHAR(500) NULL,
          status         TINYINT      NOT NULL DEFAULT 1,
          cancel_reason  VARCHAR(255) NULL,
          cancelled_by   BIGINT       NULL,
          cancel_source  TINYINT      NULL,
          cancelled_at   DATETIME     NULL,
          created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          KEY idx_room_date (room_id, date, status),
          KEY idx_user_date (user_id, date, status),
          KEY idx_recurrence (recurrence_id),
          KEY idx_time_range (room_id, start_at, end_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── system_config ─────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS system_config (
          `key`         VARCHAR(64)  PRIMARY KEY,
          value         VARCHAR(500) NOT NULL,
          description   VARCHAR(255) NULL,
          updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          updated_by    BIGINT       NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── operation_log ─────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS operation_log (
          id           BIGINT       PRIMARY KEY AUTO_INCREMENT,
          actor_type   TINYINT      NOT NULL,
          actor_id     BIGINT       NOT NULL,
          action       VARCHAR(32)  NOT NULL,
          target_type  VARCHAR(32)  NULL,
          target_id    BIGINT       NULL,
          payload      JSON         NULL,
          created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          KEY idx_actor (actor_type, actor_id, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── notify_quota ──────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS notify_quota (
          id            BIGINT       PRIMARY KEY AUTO_INCREMENT,
          user_id       BIGINT       NOT NULL,
          template_key  VARCHAR(32)  NOT NULL,
          quota         INT          NOT NULL DEFAULT 0,
          updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          UNIQUE KEY uk_user_template (user_id, template_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── notify_log ────────────────────────────────────────────────────────────
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS notify_log (
          id            BIGINT       PRIMARY KEY AUTO_INCREMENT,
          user_id       BIGINT       NOT NULL,
          booking_id    BIGINT       NULL,
          template_key  VARCHAR(32)  NOT NULL,
          scene         VARCHAR(32)  NOT NULL,
          status        TINYINT      NOT NULL,
          errmsg        VARCHAR(500) NULL,
          planned_at    DATETIME     NULL,
          sent_at       DATETIME     NULL,
          created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          KEY idx_booking_scene (booking_id, scene),
          KEY idx_planned (status, planned_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    # ── Default system_config rows (§4.2.8 + §13.2) ───────────────────────────
    conn.execute(text("""
        INSERT INTO system_config (`key`, value, description) VALUES
          ('cancel_advance_hours',   '2',  '最早可取消提前时长（小时）'),
          ('max_booking_hours',      '16', '单次预订最长时长（小时）'),
          ('max_bookings_per_day',   '3',  '同一用户同天最多预订次数'),
          ('max_recurrence_months',  '6',  '周期性预订展开最大月数'),
          ('wx_tpl_booking_success',   '', '订阅消息模板ID：预订成功'),
          ('wx_tpl_booking_upcoming',  '', '订阅消息模板ID：即将开始'),
          ('wx_tpl_booking_cancelled', '', '订阅消息模板ID：被管理员取消'),
          ('notify_quota_cap',        '10','单用户单模板配额上限（防累积滥用）'),
          ('notify_upcoming_minutes', '15','提前多少分钟推送"即将开始"')
        ON DUPLICATE KEY UPDATE `key` = `key`
    """))

    # ── Default admin user (§13.1) ────────────────────────────────────────────
    # Use bcrypt directly to avoid passlib 1.7.x / bcrypt 4.x incompatibility
    import bcrypt as _bcrypt

    username = os.environ.get("INIT_ADMIN_USERNAME", "admin")
    password = os.environ.get("INIT_ADMIN_PASSWORD", "admin123")
    pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(12)).decode()

    conn.execute(
        text("""
            INSERT INTO admin_user
              (username, password_hash, real_name, must_change_password, status)
            VALUES
              (:username, :pw_hash, '系统管理员', 1, 1)
            ON DUPLICATE KEY UPDATE id = id
        """),
        {"username": username, "pw_hash": pw_hash},
    )


def downgrade() -> None:
    conn = op.get_bind()
    for table in [
        "notify_log",
        "notify_quota",
        "operation_log",
        "booking",
        "booking_recurrence",
        "room_dept_permission",
        "room_user_permission",
        "room",
        "`user`",
        "department",
        "admin_user",
        "system_config",
    ]:
        conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
