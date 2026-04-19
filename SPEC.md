# 会议室预订系统 — 设计文档

> **用途**：本文档作为 SPEC 交付给 Claude Code 实现。文档中所有"任务编号"（如 `T-BE-08`）为 Claude Code 可独立执行的工作项，见第 11 章。
>
> **版本**：v1.0　　**日期**：2026-04-17

---

## 目录

1. [系统概述](#1-系统概述)
2. [总体架构](#2-总体架构)
3. [核心业务规则](#3-核心业务规则)
4. [数据库设计](#4-数据库设计)
5. [核心算法与并发](#5-核心算法与并发)
6. [API 设计](#6-api-设计)
7. [前端设计 — 微信小程序](#7-前端设计--微信小程序)
8. [管理端设计 — Vue 3](#8-管理端设计--vue-3)
9. [安全与鉴权](#9-安全与鉴权)
10. [后端项目结构](#10-后端项目结构)
11. [交付计划与 Claude Code 任务清单](#11-交付计划与-claude-code-任务清单)
12. [消息通知](#12-消息通知)
13. [初始化与部署约定](#13-初始化与部署约定)

---

## 1. 系统概述

### 1.1 项目目标

构建面向企业/组织内部使用的会议室预订系统，提供微信小程序端供员工查询与预订会议室，提供 Web 管理端供管理员维护会议室、用户授权与查看全局使用情况。系统需支持灵活的时间段选择（预设时段 + 半小时粒度自定义）、周期性预订、授权可见性控制、冲突检测与取消规则。

### 1.2 用户角色

| 角色 | 说明 | 入口 |
|---|---|---|
| 员工（普通用户） | 通过微信小程序登录，查看被授权的会议室并预订 | 微信小程序 |
| 管理员 | 维护会议室、授权用户、查看全量预订、管理规则参数 | Web 管理端（Vue） |

权限模型采用"单一管理员"模式：系统内只区分管理员与普通员工两类角色，管理员拥有全部后台权限。

### 1.3 核心功能清单

- 微信登录认证（`code2session`）+ 首次进入需管理员授权可见会议室
- 会议室列表按授权可见，未授权不展示
- 按日查看某会议室的已用/可用时段
- 预设时段预订：上午 / 中午 / 下午 / 晚上 / 白天 / 全天
- 自定义时段预订：08:00–24:00 之间按 30 分钟粒度自由选取，已占用时段禁选
- 周期性预订：每天 / 每周某几天 / 每月某日；遇冲突整批失败并返回冲突日期清单
- 取消预订：提前 N 小时方可取消（可配置）
- 业务规则参数：单次预订最长时长、同一用户同一天预订次数上限、最早可取消提前时长，均由管理员配置
- 管理端：会议室 CRUD、授权管理（按人/按部门两种方式）、预订总览、规则参数、用户管理
- 订阅消息通知：预订成功、即将开始（前 15 分钟）、被管理员取消（详见 [§12](#12-消息通知)）

### 1.4 技术栈

| 层次 | 技术选型 | 说明 |
|---|---|---|
| 员工端 | 微信原生小程序 | 推荐原生以便更稳定地使用 `wx.login` |
| 管理端 | Vue 3 + Vite + Element Plus + Pinia + Vue Router | 后台交互复杂度中等 |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy 2.x + Alembic + Pydantic v2 | FastAPI 自带 OpenAPI 文档便于前后端协作 |
| 数据库 | MySQL 8.0（utf8mb4） | 主库，InnoDB |
| 缓存 | Redis 7（可选） | session、每日已预订索引缓存、周期生成锁 |
| 部署 | Docker Compose（单机）或 K8s（集群） | 提供 `docker-compose.yml` 一键部署样例 |
| 认证 | 微信小程序 `code2session` + JWT；管理端用户名/密码 + JWT | — |

---

## 2. 总体架构

### 2.1 部署视图

系统采用前后端分离架构，后端对外提供统一的 REST API，前端分两个独立工程（小程序、管理端 Vue），分别调用各自权限范围内的接口。

```
[ 员工 / 微信 ]                 [ 管理员 / 浏览器 ]
       │                                │
       │ HTTPS                          │ HTTPS
       ▼                                ▼
┌───────────────┐              ┌──────────────────┐
│  微信小程序   │              │   Vue 管理端     │
│  (miniapp)    │              │   (admin-web)    │
└──────┬────────┘              └────────┬─────────┘
       │                                │
       └────────────┬───────────────────┘
                    ▼
           ┌──────────────────┐
           │  Nginx / API 网关 │  (HTTPS 终结、静态托管管理端)
           └─────────┬────────┘
                     ▼
           ┌──────────────────┐
           │  FastAPI 后端    │  (auth/room/booking/admin 模块)
           └─────┬──────┬─────┘
                 │      │
        ┌────────┘      └────────┐
        ▼                        ▼
   ┌─────────┐             ┌──────────┐
   │  MySQL  │             │  Redis   │
   └─────────┘             └──────────┘
                 │
                 ▼
        [ 微信开放平台 code2session ]
```

### 2.2 模块划分（后端）

| 模块 | 职责 |
|---|---|
| `auth` | 微信登录、管理员登录、JWT 签发与校验 |
| `user` | 用户信息、部门归属、管理员账户 |
| `room` | 会议室的增删改查、状态管理 |
| `permission` | 用户-会议室授权、部门-会议室授权、可见范围计算 |
| `booking` | 单次预订、冲突检测、取消 |
| `recurrence` | 周期规则展开与冲突批量校验（内部服务） |
| `admin` | 管理端专用接口：统计、总览、规则参数 |
| `common` | 通用响应、分页、异常、依赖注入、日志 |

### 2.3 关键时序

#### 2.3.1 微信登录流程

```
小程序                        后端                    微信开放平台
  │  wx.login() 取 code        │                          │
  │────────────────────────────▶│  POST /api/auth/wechat  │
  │                             │────────────────────────▶│
  │                             │  code2session            │
  │                             │◀────────────────────────│
  │                             │  返回 openid/unionid     │
  │                             │  查/建 user，签发 JWT    │
  │◀────────────────────────────│  返回 token + 用户信息   │
  │  本地存储 token              │                          │
  │  后续请求携带 Authorization  │                          │
```

#### 2.3.2 单次预订

```
小程序                        后端
  │ 选择会议室 + 日期           │
  │────────────────────────────▶│  GET /api/rooms/{id}/availability?date=...
  │◀────────────────────────────│  返回当日所有被占用的 30min 槽位
  │ 渲染时间条，禁用占用槽      │
  │ 选择"下午"或 14:00-16:30    │
  │────────────────────────────▶│  POST /api/bookings
  │                             │   ─ 权限校验（会议室授权）
  │                             │   ─ 规则校验（最长时长、每日次数）
  │                             │   ─ 事务内冲突校验 + 插入
  │◀────────────────────────────│  返回预订记录
```

---

## 3. 核心业务规则

### 3.1 时间模型

所有预订时间使用系统本地时区（默认 `Asia/Shanghai`），数据库存储采用 UTC `DATETIME`，API 层负责转换。

- **最小时间粒度**：30 分钟（称为一个"槽位 slot"）
- **可选时间范围**：每天 08:00–24:00，共 32 个槽位（`08:00–08:30` 为 slot 0，`23:30–24:00` 为 slot 31）
- **24:00** 在数据库中存储为次日 `00:00`，便于查询使用 `[start, end)` 半开区间

#### 3.1.1 预设时段

| 模式 | 开始 | 结束 | 说明 |
|---|---|---|---|
| 上午 | 08:00 | 12:00 | 半天 |
| 中午 | 12:00 | 14:30 | 午休 |
| 下午 | 14:30 | 18:00 | 半天 |
| 晚上 | 18:00 | 24:00 | 半天 |
| 白天 | 08:00 | 18:00 | 组合：上午+中午+下午 |
| 全天 | 08:00 | 24:00 | 全时段 |

预设时段在后端作为枚举处理；前端提交时可以传 `preset` 字段（如 `"morning"`），后端展开为 `start/end`；也可以直接提交 `start/end`，由后端做落位对齐到 30 分钟边界。

#### 3.1.2 冲突定义

两条预订在同一会议室、同一天，若 `[start, end)` 区间相交（即 `A.start < B.end AND A.end > B.start`），视为冲突。

### 3.2 授权与可见性

采用"按用户授权"与"按部门授权"并存的双粒度模型。一个用户对某会议室只要满足其中任意一条授权即为可见。

- **直接授权**：`room_user_permission(user_id, room_id)`
- **部门授权**：`room_dept_permission(dept_id, room_id)`，用户通过 `user.dept_id` 继承
- **可见会议室** = 直接授权会议室 ∪ 部门授权会议室（按 `room_id` 去重）
- 会议室列表接口一定要显式校验授权；预订接口也必须二次校验，不能仅依赖前端过滤

### 3.3 业务规则参数（管理端可配）

| 参数名 | 键 | 默认值 | 说明 |
|---|---|---|---|
| 最早可取消提前时长（小时） | `cancel_advance_hours` | `2` | 开始时间 − 当前时间 < 该值，则不允许取消 |
| 单次预订最长时长（小时） | `max_booking_hours` | `16` | 全天为 16 小时，超过报错；预设时段豁免此限制 |
| 同一用户同天预订次数上限 | `max_bookings_per_day` | `3` | 按 `date` 统计用户已有的、非取消的预订数量 |
| 周期展开上限（月） | `max_recurrence_months` | `6` | 周期性预订单次生成不得超过该月数 |

所有参数存入 `system_config` 表，管理端提供页面编辑；后端以 `config_service` 读取（带 Redis 缓存，参数变更时清缓存）。

### 3.4 取消规则

- 预订人本人可取消自己未开始的预订
- 管理员可取消任意预订（留下操作人记录）
- 取消时需满足：**当前时间 + `cancel_advance_hours` ≤ `booking.start_at`**
- 周期性预订中的单次实例可单独取消，不影响其它实例
- 周期性预订的"整体取消"表示取消该规则未来尚未开始的全部实例

### 3.5 周期性预订规则

支持三种频率：

- **DAILY**：每天，直到截止日期
- **WEEKLY**：每周选中的几天（如周一、周三、周五），直到截止日期
- **MONTHLY**：每月某日（1–31；遇当月不存在该日则跳过该月，如 2 月 30 日）

**展开策略**：

- 在创建接口内一次性展开为 N 条独立的 `booking` 实例，并共享同一 `recurrence_id`
- 展开时需校验每一天是否与现有预订冲突
- 若任一天冲突，则整批不落库，接口返回 `409` 并携带 `conflicts` 数组（日期 + 冲突预订人）
- 周期跨度不得超过 `max_recurrence_months`（默认 6 个月）

这样处理的好处是后续取消、查询、渲染都以单条实例为单位，简单且与单次预订统一；代价是存储行数较多，但周期 ≤ 6 个月完全可接受。

---

## 4. 数据库设计

### 4.1 ER 概览

```
department ─┐
            │ 1:N
user ───────┤       room_user_permission
            │      ┌──────────────────┐
            │      │ user_id, room_id │
            │      └──────────────────┘
            │ 1:N       ↑
booking ────┤           │ N:M
            │           ▼
            │      ┌──────────┐      room_dept_permission
            │      │  room    │ ◀───┤ dept_id, room_id │
            │ N:1  └──────────┘      └──────────────────┘
            │
recurrence ─┘ 1:N booking

system_config: 独立键值表
admin_user:    独立管理员账号表
```

### 4.2 表结构

#### 4.2.1 `department`（部门）

```sql
CREATE TABLE department (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  name         VARCHAR(64)  NOT NULL,
  parent_id    BIGINT       NULL,          -- 支持层级；MVP 可不使用层级
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_parent (parent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.2.2 `user`（员工）

```sql
CREATE TABLE user (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  openid         VARCHAR(64)  NOT NULL,       -- 微信小程序 openid
  unionid        VARCHAR(64)  NULL,
  nickname       VARCHAR(64)  NULL,           -- 微信昵称（如前端提供）
  real_name      VARCHAR(64)  NULL,           -- 真实姓名（管理员维护）
  phone          VARCHAR(32)  NULL,
  dept_id        BIGINT       NULL,
  status         TINYINT      NOT NULL DEFAULT 1,   -- 1 启用 / 0 禁用
  last_login_at  DATETIME     NULL,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_openid (openid),
  KEY idx_dept (dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.2.3 `admin_user`（管理员）

```sql
CREATE TABLE admin_user (
  id                    BIGINT PRIMARY KEY AUTO_INCREMENT,
  username              VARCHAR(64)  NOT NULL,
  password_hash         VARCHAR(128) NOT NULL,    -- bcrypt / argon2
  real_name             VARCHAR(64)  NULL,
  must_change_password  TINYINT      NOT NULL DEFAULT 0,  -- 1 表示下次登录强制改密码
  status                TINYINT      NOT NULL DEFAULT 1,
  last_login_at         DATETIME     NULL,
  created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.2.4 `room`（会议室）

```sql
CREATE TABLE room (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  name         VARCHAR(64)  NOT NULL,
  location     VARCHAR(128) NULL,           -- 楼层/位置描述
  capacity     INT          NULL,           -- 容纳人数
  facilities   VARCHAR(255) NULL,           -- 投影/白板/视频等，逗号分隔或 JSON
  description  VARCHAR(500) NULL,
  status       TINYINT      NOT NULL DEFAULT 1,   -- 1 启用 / 0 禁用（禁用后不可预订）
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.2.5 `room_user_permission` / `room_dept_permission`（授权）

```sql
CREATE TABLE room_user_permission (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  room_id     BIGINT   NOT NULL,
  user_id     BIGINT   NOT NULL,
  granted_by  BIGINT   NULL,   -- admin_user.id
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_room_user (room_id, user_id),
  KEY idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE room_dept_permission (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  room_id     BIGINT   NOT NULL,
  dept_id     BIGINT   NOT NULL,
  granted_by  BIGINT   NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_room_dept (room_id, dept_id),
  KEY idx_dept (dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.2.6 `booking_recurrence`（周期规则）

```sql
CREATE TABLE booking_recurrence (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id        BIGINT       NOT NULL,
  room_id        BIGINT       NOT NULL,
  frequency      VARCHAR(16)  NOT NULL,     -- DAILY / WEEKLY / MONTHLY
  weekdays       VARCHAR(32)  NULL,         -- WEEKLY 时使用，如 "1,3,5"（周一到周日 1-7）
  month_day      INT          NULL,         -- MONTHLY 时使用，1-31
  start_date     DATE         NOT NULL,
  end_date       DATE         NOT NULL,
  start_time     TIME         NOT NULL,     -- 每次预订的时段（同一时段反复）
  end_time       TIME         NOT NULL,
  title          VARCHAR(128) NULL,
  status         TINYINT      NOT NULL DEFAULT 1,  -- 1 有效 / 0 整体取消
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user (user_id),
  KEY idx_room (room_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.2.7 `booking`（预订实例）

```sql
CREATE TABLE booking (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  room_id        BIGINT       NOT NULL,
  user_id        BIGINT       NOT NULL,
  recurrence_id  BIGINT       NULL,         -- 非 NULL 表示属于某周期规则
  date           DATE         NOT NULL,     -- 冗余：start_at 的日期部分，便于按日查询
  start_at       DATETIME     NOT NULL,
  end_at         DATETIME     NOT NULL,     -- 开区间右端，24:00 存为次日 00:00
  preset         VARCHAR(16)  NULL,         -- morning/noon/afternoon/evening/daytime/allday；自定义为 NULL
  title          VARCHAR(128) NULL,
  attendees      VARCHAR(500) NULL,         -- 参会人备注，可选
  status         TINYINT      NOT NULL DEFAULT 1,  -- 1 有效 / 0 已取消
  cancel_reason  VARCHAR(255) NULL,
  cancelled_by   BIGINT       NULL,         -- user.id 或 admin_user.id（根据 cancel_source 区分）
  cancel_source  TINYINT      NULL,         -- 1 用户自助 / 2 管理员
  cancelled_at   DATETIME     NULL,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_room_date (room_id, date, status),
  KEY idx_user_date (user_id, date, status),
  KEY idx_recurrence (recurrence_id),
  KEY idx_time_range (room_id, start_at, end_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

> MySQL 没有简单的区间排斥约束，冲突防护依靠事务 + 行锁 + 业务层查询，详见 [§5](#5-核心算法与并发)。

#### 4.2.8 `system_config`（系统参数）

```sql
CREATE TABLE system_config (
  `key`         VARCHAR(64)  PRIMARY KEY,
  value         VARCHAR(500) NOT NULL,
  description   VARCHAR(255) NULL,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_by    BIGINT   NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO system_config(`key`, value, description) VALUES
 ('cancel_advance_hours',   '2',  '最早可取消提前时长（小时）'),
 ('max_booking_hours',      '16', '单次预订最长时长（小时）'),
 ('max_bookings_per_day',   '3',  '同一用户同天最多预订次数'),
 ('max_recurrence_months',  '6',  '周期性预订展开最大月数');
```

#### 4.2.9 `operation_log`（可选，审计日志）

```sql
CREATE TABLE operation_log (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  actor_type   TINYINT     NOT NULL,     -- 1 user / 2 admin
  actor_id     BIGINT      NOT NULL,
  action       VARCHAR(32) NOT NULL,     -- book.create / book.cancel / perm.grant...
  target_type  VARCHAR(32) NULL,
  target_id    BIGINT      NULL,
  payload      JSON        NULL,
  created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_actor (actor_type, actor_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.2.10 `notify_quota`（订阅消息配额）

每次用户在小程序侧成功 `wx.requestSubscribeMessage` 并选择"允许"，后端会给用户对应模板 +1 配额；每次实际下发消息 -1。用完需要用户重新订阅。

```sql
CREATE TABLE notify_quota (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id       BIGINT       NOT NULL,
  template_key  VARCHAR(32)  NOT NULL,     -- booking_success / booking_upcoming / booking_cancelled
  quota         INT          NOT NULL DEFAULT 0,   -- 剩余可发次数
  updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_template (user_id, template_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 4.2.11 `notify_log`（通知发送记录）

用于幂等控制（防止重复下发）、故障排查、统计。

```sql
CREATE TABLE notify_log (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id       BIGINT       NOT NULL,
  booking_id    BIGINT       NULL,
  template_key  VARCHAR(32)  NOT NULL,
  scene         VARCHAR(32)  NOT NULL,     -- booking_success / upcoming / cancelled_by_admin
  status        TINYINT      NOT NULL,     -- 0 待发 / 1 成功 / 2 失败 / 3 跳过（无配额）
  errmsg        VARCHAR(500) NULL,         -- 微信返回错误
  planned_at    DATETIME     NULL,         -- 计划发送时间（upcoming 用）
  sent_at       DATETIME     NULL,
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_booking_scene (booking_id, scene),  -- 幂等校验：同一 booking+scene 只发一次
  KEY idx_planned (status, planned_at)         -- 调度器扫待发
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 5. 核心算法与并发

### 5.1 冲突检测 SQL

在预订事务内、对 `room` 行加锁（或使用会议室粒度的行级锁）后执行：

```sql
-- 锁定会议室记录，确保同一会议室的并发预订串行化
SELECT id FROM room WHERE id = :room_id AND status = 1 FOR UPDATE;

-- 查冲突
SELECT id, user_id, start_at, end_at
FROM booking
WHERE room_id = :room_id
  AND status  = 1
  AND start_at < :end_at
  AND end_at   > :start_at
LIMIT 1;
-- 如有结果则回滚事务，返回 409 冲突
```

说明：

- 之所以对 `room` 行加锁而不是对 `booking` 区间加锁，是因为 InnoDB 的 gap lock 在非 unique 索引上难以精确覆盖时间区间；对 `room` 行加排他锁是最稳妥、最直接的串行化手段
- 整个写入路径耗时短（查冲突 + 插入），对单会议室并发预订冲击可接受
- 也可使用 Redis 分布式锁 `meeting:room:{room_id}` 在 API 层串行化，作为备选方案

### 5.2 周期性预订展开算法

```
输入：room_id, user_id, frequency, weekdays, month_day,
      start_date, end_date, start_time, end_time

1. 参数校验：
   - end_date - start_date ≤ max_recurrence_months 个月
   - start_time < end_time（24:00 以次日 00:00 表示时按天拆分比较）
   - 会议室授权校验

2. 生成候选日期 dates[]：
   d = start_date
   while d <= end_date:
       if matches(d, frequency, weekdays, month_day):
           dates.append(d)
       d += 1 day

3. 开启事务；SELECT ... FOR UPDATE 锁会议室

4. 对每个 d in dates：
   - 构造 start_at = d + start_time, end_at = d + end_time
   - 跑冲突 SQL（§5.1）
   - 若冲突，conflicts.append({date: d, with: existing})

5. 如果 conflicts 非空：
   - 回滚事务
   - 返回 409 + conflicts 列表
   否则：
   - 插入 booking_recurrence 记录
   - 批量插入所有 booking 实例，写入 recurrence_id
   - 提交事务
```

**关键点**：一次请求内完成全部冲突检查与写入，避免"先查全部、再批量写"之间产生新的并发冲突。对会议室加锁保证串行。

### 5.3 可用性查询算法（渲染时间条）

前端渲染 30 分钟粒度的时间条，后端返回当日所有占用槽位：

```sql
-- 查该会议室当日所有有效预订
SELECT start_at, end_at, user_id, preset, title
FROM booking
WHERE room_id = :room_id
  AND date    = :date
  AND status  = 1
ORDER BY start_at;
```

前端把每条预订映射到 slot 集合：

- `slot_index = (minutes_from_8am) / 30`，范围 `[0, 31]`
- 被占用的 slot 在 UI 上置灰且不可点击

### 5.4 业务规则校验顺序

预订创建时的校验顺序（任一失败立即返回相应错误码）：

1. 身份合法（JWT 有效）
2. 会议室存在且启用
3. 用户对该会议室有授权（直接授权或部门授权）
4. 时间区间合法（对齐 30 分钟、`start < end`、在 08:00–24:00 范围内）
5. 单次时长 ≤ `max_booking_hours`（预设时段豁免此检查）
6. 当日该用户预订数 < `max_bookings_per_day`（周期性预订按展开日分别计数）
7. 事务内冲突检测

---

## 6. API 设计

### 6.1 约定

- **Base URL**：`/api`
- **鉴权**：除 `/api/auth/*` 外，所有接口需要 `Authorization: Bearer <jwt>`
- **统一响应**：`{ "code": 0, "message": "ok", "data": {...} }`；业务错误 `code` 非 0
- **分页参数**：`page`（从 1 起）、`page_size`（默认 20，最大 100）
- **时间字段**：请求与响应均使用 ISO 8601（`YYYY-MM-DDTHH:mm:ss+08:00`）

### 6.2 常见错误码

| code | HTTP | 含义 |
|---|---|---|
| `0` | 200 | 成功 |
| `40001` | 400 | 参数错误 |
| `40101` | 401 | 未登录或 token 失效 |
| `40301` | 403 | 无权访问该会议室 |
| `40401` | 404 | 资源不存在 |
| `40901` | 409 | 预订时间冲突 |
| `40902` | 409 | 周期性预订部分日期冲突（附 `conflicts`） |
| `42201` | 422 | 违反业务规则（超最长时长、每日上限等，附 `rule` 标识） |
| `50000` | 500 | 服务端异常 |

### 6.3 认证类

#### `POST /api/auth/wechat`

微信小程序登录。

```json
// Request
{
  "code": "0x3dF...",
  "nickname": "张三",
  "avatar_url": "https://..."
}

// Response
{
  "code": 0,
  "data": {
    "token": "eyJhbGciOi...",
    "expire_at": "2026-04-18T10:00:00+08:00",
    "user": {
      "id": 123, "openid": "o-xxx", "nickname": "张三",
      "real_name": null, "dept_id": 5, "status": 1
    },
    "need_profile": true
  }
}
```

#### `POST /api/auth/admin/login`

```json
// Request
{ "username": "admin", "password": "***" }

// Response
{ "code": 0, "data": { "token": "...", "expire_at": "...", "admin": {} } }
```

#### `POST /api/auth/refresh`

刷新 token（可选实现，MVP 可不做刷新，直接让小程序每次启动重新 `wx.login`）。

### 6.4 会议室类（小程序视角）

#### `GET /api/rooms`

当前用户"可见"的会议室列表（仅返回授权范围内的）。

```
Query: keyword (可选), status (可选)
```

```json
{ "code": 0, "data": [
    { "id": 1, "name": "大会议室 A", "location": "3F", "capacity": 20,
      "facilities": "投影,白板,视频", "status": 1 }
]}
```

#### `GET /api/rooms/{id}/availability`

查询指定日期下的会议室占用情况，用于渲染时间条。

```
Query: date=2026-04-18
```

```json
{
  "code": 0,
  "data": {
    "room_id": 1,
    "date": "2026-04-18",
    "slots_taken": [
      { "booking_id": 101, "start_at": "2026-04-18T09:00:00+08:00",
        "end_at": "2026-04-18T10:30:00+08:00",
        "user": { "id": 12, "real_name": "李四" },
        "preset": null, "title": "周会" }
    ]
  }
}
```

### 6.5 预订类

#### `POST /api/bookings`（单次预订）

```json
// Request (预设时段)
{
  "room_id": 1,
  "date": "2026-04-18",
  "preset": "morning",
  "title": "产品评审"
}

// Request (自定义时段)
{
  "room_id": 1,
  "date": "2026-04-18",
  "start_time": "14:00",
  "end_time":   "16:30",
  "title": "面试"
}

// Response
{ "code": 0, "data": { "id": 201, "status": 1 } }

// Error (冲突)
{ "code": 40901, "message": "时间冲突",
  "data": { "conflict_with": { "booking_id": 101, "user": "李四",
                               "start_at": "...", "end_at": "..." } } }
```

#### `POST /api/bookings/recurrence`（周期性预订）

```json
// Request
{
  "room_id": 1,
  "frequency": "WEEKLY",
  "weekdays": [1, 3, 5],
  "month_day": null,
  "start_date": "2026-04-20",
  "end_date":   "2026-07-20",
  "start_time": "14:00",
  "end_time":   "15:30",
  "title": "周例会"
}

// Response (成功)
{ "code": 0, "data": { "recurrence_id": 77,
                       "booking_ids": [],
                       "count": 14 } }

// Response (整批失败)
{ "code": 40902, "message": "周期预订存在冲突",
  "data": { "conflicts": [
      { "date": "2026-05-06", "with_user": "王五",
        "start_at": "...", "end_at": "..." },
      { "date": "2026-06-10" }
  ] } }
```

#### `GET /api/bookings`（我的预订列表）

```
Query:
  scope=mine (默认) | room_id=x (只能查看有权限的会议室)
  status=active|cancelled|all
  start_date, end_date (可选), page, page_size
```

```json
{ "code": 0, "data": { "list": [], "total": 42, "page": 1 } }
```

#### `GET /api/bookings/{id}`

详情。仅预订人、管理员、或该会议室有授权的用户可查看（基础可见性即可）。

#### `POST /api/bookings/{id}/cancel`

```json
// Request
{ "reason": "会议取消" }

// Response
{ "code": 0, "data": { "id": 201, "status": 0, "cancelled_at": "..." } }
```

错误：
- `42201` — 超过可取消时限（`cancel_advance_hours`）
- `40301` — 非本人且非管理员

#### `POST /api/bookings/recurrence/{id}/cancel`

取消某个周期规则的全部未来实例（已过去的实例不动）。

#### `POST /api/notify/subscribe-report`

小程序调完 `wx.requestSubscribeMessage` 后上报用户的订阅结果。后端据此更新 `notify_quota`。

```json
// Request
{
  "results": {
    "booking_success":   "accept",    // accept / reject / ban
    "booking_upcoming":  "accept",
    "booking_cancelled": "reject"
  }
}

// Response
{ "code": 0, "data": { "quota": {
    "booking_success": 3,
    "booking_upcoming": 2,
    "booking_cancelled": 0
}}}
```

后端对每个 `accept` 的模板执行 `quota += 1`（封顶如 10 条，防止单用户累积过多）；`reject / ban` 不变。

#### `GET /api/notify/quota`

返回当前用户每个模板的剩余订阅配额，前端据此决定是否要再弹一次订阅授权。

### 6.6 管理端类

#### 会议室管理

- `GET /api/admin/rooms?keyword=&status=&page=`
- `POST /api/admin/rooms`
- `PUT /api/admin/rooms/{id}`
- `DELETE /api/admin/rooms/{id}` — 软删：置 `status=0`；若有未来预订则拒绝或提示管理员先取消

#### 授权管理

- `GET /api/admin/rooms/{id}/permissions` — 返回该会议室的授权用户列表 + 授权部门列表
- `POST /api/admin/rooms/{id}/permissions/users` — body: `{ user_ids: [] }`
- `DELETE /api/admin/rooms/{id}/permissions/users/{user_id}`
- `POST /api/admin/rooms/{id}/permissions/depts` — body: `{ dept_ids: [] }`
- `DELETE /api/admin/rooms/{id}/permissions/depts/{dept_id}`
- `GET /api/admin/users/{id}/rooms` — 某用户当前可见的会议室（合并后）

#### 用户 / 部门

- `GET /api/admin/users?keyword=&dept_id=&status=`
- `PUT /api/admin/users/{id}` — 修改真实姓名、部门、状态
- `GET /api/admin/departments`
- `POST/PUT/DELETE /api/admin/departments`

#### 预订总览

- `GET /api/admin/bookings?room_id=&user_id=&date_from=&date_to=&status=`
- `GET /api/admin/stats/overview` — 今日预订数、本周预订数、活跃会议室 Top
- `POST /api/admin/bookings/{id}/cancel` — 管理员强制取消（记录操作人）

#### 系统参数

- `GET /api/admin/config`
- `PUT /api/admin/config` — body: `{ cancel_advance_hours: 2, ... }`

---

## 7. 前端设计 — 微信小程序

### 7.1 页面结构

| 页面 | 路径 | 说明 |
|---|---|---|
| 启动/登录 | `pages/launch` | 执行 `wx.login` → 调后端换取 JWT；首次进入引导补全真实姓名 |
| 首页（会议室列表） | `pages/index` | 展示授权可见的会议室，点击进入详情 |
| 会议室详情/选择日期 | `pages/room/detail` | 日期选择器 + 当日时间条 |
| 预订创建 | `pages/booking/create` | 选择预设时段或自定义时段，填写标题，提交 |
| 周期性预订 | `pages/booking/recurrence` | 选择频率、日期范围、时段 |
| 我的预订 | `pages/my/bookings` | 列表 + 取消操作 |
| 预订详情 | `pages/booking/detail` | 查看/取消 |
| 个人中心 | `pages/my/index` | 头像、昵称、真实姓名、退出 |

### 7.2 关键交互

**时间条组件**

- 横向或纵向 32 格（08:00–24:00，每格 30 分钟）
- 每格状态：可用 / 已占用（灰色 + 禁用）/ 当前选中 / 不连续选择警示
- 支持两种输入模式切换：预设时段按钮组、自定义时间段拖选
- 自定义模式下约束：必须是"连续"的一段，选择时起点与终点都应该落在 30 分钟边界
- 当用户选择跨越已占用槽位时立即给出提示，不允许提交

**周期性预订**

- 频率单选：每天 / 每周 / 每月
- WEEKLY 提供周一到周日多选；MONTHLY 提供 1–31 的日历格子
- 日期范围选择器：开始日期、结束日期；前端即时显示"将生成约 X 次"
- 提交后如返回 `40902`，弹窗展示冲突日期列表，并引导用户缩短范围或改时间

**取消确认**

- 点击"取消预订"弹出二次确认
- 如果距离 `start_at` 不足 `cancel_advance_hours`，按钮置灰并显示提示文案

### 7.3 网络层 & 状态

- 封装 `request.js`：自动注入 `Authorization`、统一处理 `40101` → 清 token 并重新 `wx.login`
- 全局状态：`app.globalData` 保存 `userInfo / token`；或使用 `MobX-miniprogram`
- 本地缓存：`wx.setStorageSync` 保存 token 与用户信息

### 7.4 目录建议

```
miniapp/
├── app.js / app.json / app.wxss
├── pages/
│   ├── launch/
│   ├── index/
│   ├── room/detail/
│   ├── booking/
│   │   ├── create/
│   │   ├── recurrence/
│   │   └── detail/
│   └── my/
│       ├── index/
│       └── bookings/
├── components/
│   ├── time-bar/          # 时间条核心组件
│   ├── preset-picker/
│   ├── date-picker/
│   └── weekday-picker/
├── utils/
│   ├── request.js
│   ├── auth.js
│   └── time.js            # slot 与 time 的互转
└── config.js              # BASE_URL 等
```

---

## 8. 管理端设计 — Vue 3

### 8.1 页面结构

| 模块 | 页面 | 路径 |
|---|---|---|
| 登录 | 登录页 | `/login` |
| 仪表盘 | 总览 | `/dashboard` |
| 会议室 | 列表 / 新增 / 编辑 / 授权抽屉 | `/rooms` |
| 授权 | 按用户授权 / 按部门授权（Tab 切换） | `/rooms/:id/permissions` |
| 用户 | 员工列表 / 详情 / 权限汇总 | `/users` |
| 部门 | 部门管理 | `/departments` |
| 预订 | 预订总览（按会议室/按日/按人筛选） | `/bookings` |
| 系统参数 | 规则配置 | `/settings` |
| 个人 | 管理员资料 / 修改密码 | `/profile` |

### 8.2 关键交互

**会议室授权**

- 在会议室列表行点击"授权"打开抽屉，抽屉内两个 Tab：按用户 / 按部门
- **按用户 Tab**：左边搜索框 + 员工列表（带部门过滤），右边已授权列表；穿梭框或批量勾选
- **按部门 Tab**：树形选择器（若使用层级部门），直接勾选整个部门
- 顶部显示"有效可见人数"（= 直接授权用户 + 部门授权中的在职用户并集，去重后总数）

**预订总览**

- 提供两种视图：列表视图（表格）、日历视图（按会议室分组的甘特图样式）
- 支持按 `room_id / user_id / 日期范围 / 状态` 筛选
- 管理员可对任一预订点"强制取消"，弹窗填写 reason

**系统参数**

- 表单展示四项参数，均带默认值提示；修改后需输入当前管理员密码再次确认（防误操作，可选）

### 8.3 技术栈细节

- Vue 3 + Vite + TypeScript
- Element Plus 作为组件库（Form/Table/Dialog/Drawer/Tree/Calendar 覆盖本场景 90% 需求）
- Pinia 管理全局状态（当前管理员、系统参数缓存）
- Vue Router，路由守卫：无 token → `/login`；token 过期 → 清理并跳转
- Axios 封装：统一响应结构解包、业务错误 toast、401 自动登出

### 8.4 目录建议

```
admin-web/
├── src/
│   ├── api/            # 按模块拆分 axios 封装
│   ├── components/     # 通用组件（时间条只读版、授权抽屉等）
│   ├── layouts/
│   ├── pages/
│   │   ├── dashboard/
│   │   ├── rooms/
│   │   ├── users/
│   │   ├── departments/
│   │   ├── bookings/
│   │   └── settings/
│   ├── router/
│   ├── stores/
│   ├── utils/
│   └── App.vue / main.ts
├── vite.config.ts
└── package.json
```

---

## 9. 安全与鉴权

### 9.1 认证

- **小程序**：`wx.login` 获取 code → 后端 `code2session`（需配置 appid/secret）→ 以 openid 查/建 user → 签发 JWT
- **管理端**：用户名 + 密码（bcrypt 存 hash）→ 签发 JWT
- JWT payload 包含：`sub`（用户/管理员 id）、`role`（user/admin）、`exp`
- JWT 过期时间：小程序 7 天；管理端 2 小时（较短，降低泄露风险）

### 9.2 授权

- 所有 `/api/admin/*` 接口通过依赖 `get_current_admin` 校验角色
- 所有预订与可用性查询接口**必须二次校验**会议室授权，不相信前端过滤
- 取消接口校验：预订人本人 或 管理员；否则 403

### 9.3 数据保护

- 密码使用 bcrypt（cost=12）；JWT 密钥使用 ≥ 32 字节随机字符串
- 微信 `AppSecret` 存入环境变量/密钥管理服务，不提交到仓库
- 所有敏感接口日志脱敏：openid 打码、手机号打码
- TLS：线上必须走 HTTPS（小程序强制要求）

### 9.4 防滥用

- 登录接口限流：同 IP 同账号每分钟 5 次
- 预订接口限流：同用户每分钟 30 次（防止脚本抢占）
- 审计日志：所有管理员操作、强制取消、参数变更记入 `operation_log`

---

## 10. 后端项目结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # pydantic-settings 配置
│   ├── db.py                   # SQLAlchemy engine/session
│   ├── deps.py                 # get_db / get_current_user / get_current_admin
│   ├── middlewares.py
│   ├── core/
│   │   ├── security.py         # JWT、密码哈希
│   │   ├── wechat.py           # code2session 封装
│   │   ├── response.py         # 统一返回
│   │   └── exceptions.py
│   ├── models/                 # SQLAlchemy ORM
│   │   ├── user.py
│   │   ├── admin_user.py
│   │   ├── department.py
│   │   ├── room.py
│   │   ├── permission.py
│   │   ├── booking.py
│   │   ├── recurrence.py
│   │   └── system_config.py
│   ├── schemas/                # Pydantic DTO
│   │   └── ...
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── room_service.py
│   │   ├── permission_service.py
│   │   ├── booking_service.py
│   │   ├── recurrence_service.py
│   │   └── config_service.py
│   └── api/
│       ├── v1/
│       │   ├── auth.py
│       │   ├── rooms.py
│       │   ├── bookings.py
│       │   └── admin/
│       │       ├── rooms.py
│       │       ├── users.py
│       │       ├── departments.py
│       │       ├── bookings.py
│       │       ├── permissions.py
│       │       └── settings.py
│       └── router.py
├── alembic/
│   ├── versions/
│   └── env.py
├── tests/
│   ├── conftest.py
│   ├── test_booking.py
│   ├── test_recurrence.py
│   └── test_permission.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml          # 含 mysql + redis + backend
```

### 10.1 关键依赖

```
fastapi[all]>=0.110
uvicorn[standard]>=0.27
SQLAlchemy>=2.0
alembic>=1.13
PyMySQL>=1.1               # 或 aiomysql 如走异步
pydantic>=2.6
pydantic-settings>=2.2
python-jose[cryptography]  # JWT
passlib[bcrypt]            # 密码哈希
httpx>=0.27                # 调微信接口
redis>=5.0                 # 可选缓存/锁
python-dateutil            # 周期日期展开
```

---

## 11. 交付计划与 Claude Code 任务清单

### 11.1 里程碑

| 阶段 | 内容 | 产出 |
|---|---|---|
| **M1** 基础框架 | 后端骨架、数据库建表、Alembic、JWT、基础 `/ping` | backend 可启动，能 `POST /api/auth/admin/login` |
| **M2** 核心域 | room/user/department CRUD、权限模型、授权接口 | 管理端可维护会议室和授权 |
| **M3** 预订 | 单次预订 + 可用性查询 + 冲突检测 + 取消 | 小程序可完成最核心预订流程 |
| **M4** 周期预订 | 周期展开、整批事务、冲突返回 | 周期预订可用 |
| **M5** 管理端 | Vue 管理端全部页面 + 统计 | 管理端交付 |
| **M6** 小程序 UI | 时间条组件、周期 UI、我的预订 | 小程序交付 |
| **M7** 打磨 | 审计日志、限流、监控、部署文档 | 可上线 |

### 11.2 Claude Code 可独立执行的任务清单

#### 后端任务

- [ ] **T-BE-01**：初始化 FastAPI 项目骨架（按 [§10](#10-后端项目结构) 的目录结构），配置 `pydantic-settings`、日志、统一响应
- [ ] **T-BE-02**：编写 SQLAlchemy 模型（按 [§4.2](#42-表结构) 所有表）
- [ ] **T-BE-03**：Alembic 初始化 + 首版迁移 + 默认 `system_config` 数据
- [ ] **T-BE-04**：实现 JWT 工具与依赖注入（`get_current_user` / `get_current_admin`）
- [ ] **T-BE-05**：实现微信 `code2session` 客户端与 `/api/auth/wechat`（带 mock 开关便于开发期测试）
- [ ] **T-BE-06**：实现管理员登录 `/api/auth/admin/login` 与密码哈希
- [ ] **T-BE-07**：实现 `permission_service`：可见会议室并集计算、授权 CRUD
- [ ] **T-BE-08**：实现 `booking_service.create`（含授权、规则、冲突校验，事务 + 行锁）
- [ ] **T-BE-09**：实现 availability 查询接口
- [ ] **T-BE-10**：实现 `recurrence_service.expand_and_create`（含整批冲突检测）
- [ ] **T-BE-11**：实现取消接口（预订实例取消 + 周期整体取消）
- [ ] **T-BE-12**：实现全部管理端接口（rooms/users/depts/bookings/permissions/config/stats）
- [ ] **T-BE-13**：单元测试（冲突检测、周期展开、权限并集、取消提前时限）
- [ ] **T-BE-14**：`Dockerfile` + `docker-compose.yml` + `.env.example`

#### 小程序任务

- [ ] **T-MP-01**：初始化原生小程序项目，配置 `BASE_URL` 与 `request` 封装
- [ ] **T-MP-02**：登录页 + JWT 持久化 + 路由守卫
- [ ] **T-MP-03**：会议室列表页
- [ ] **T-MP-04**：实现 `time-bar` 组件（支持 32 槽位、禁用、选中、预设联动）
- [ ] **T-MP-05**：会议室详情 + 预订创建（预设 + 自定义）
- [ ] **T-MP-06**：周期性预订页
- [ ] **T-MP-07**：我的预订 + 取消
- [ ] **T-MP-08**：个人中心 + 补全真实姓名

#### 管理端任务

- [ ] **T-ADM-01**：初始化 Vue 3 + Vite + Element Plus + Pinia 项目骨架
- [ ] **T-ADM-02**：登录页 + axios 封装 + 路由守卫
- [ ] **T-ADM-03**：Dashboard 总览
- [ ] **T-ADM-04**：会议室管理 + 授权抽屉（按用户/按部门 Tab）
- [ ] **T-ADM-05**：用户与部门管理
- [ ] **T-ADM-06**：预订总览（列表 + 日历视图）
- [ ] **T-ADM-07**：系统参数配置页

### 11.3 给 Claude Code 的启动建议

- 将本文档放入项目根目录作为 `SPEC.md`；为每个任务创建独立分支或独立会话
- 按 M1 → M7 里程碑顺序推进；每个里程碑完成后跑一次端到端 smoke test
- 后端先于前端完成，便于前端按真实接口对接；接口联调前可让 Claude Code 生成一份 OpenAPI 导出的 Postman/Apifox 集合
- 周期性预订与冲突检测是核心难点，**T-BE-08** 和 **T-BE-10** 建议要求配套单元测试；用 sqlite-in-memory 跑测试时注意对 `FOR UPDATE` 的兼容（测试环境可放宽为应用层锁）

### 11.4 建议的 Claude Code 启动提示词模板

```
我需要你实现一个会议室预订系统，完整设计在项目根目录的 SPEC.md 中。

当前任务：T-BE-08（booking_service.create 单次预订）

请：
1. 先阅读 SPEC.md 的 §3.1-3.4（规则）、§4.2.7（booking 表）、§5.1/§5.4（算法）、§6.5（接口契约）
2. 按 §10 的目录结构把代码放到正确位置
3. 严格遵守 §5.4 的校验顺序
4. 事务内使用 SELECT ... FOR UPDATE 锁 room 行
5. 同时编写单元测试覆盖：正常预订、授权失败、超最长时长、超每日上限、时间冲突
6. 完成后给我一份 CHANGELOG，列出新建/修改的文件

实现前如有任何歧义请先提问，不要自行假设。
```

---

## 12. 消息通知

### 12.1 总体方案

使用微信小程序**订阅消息**（`subscribeMessage`）下发三类通知：

| 场景 | 触发时机 | 模板键 `template_key` |
|---|---|---|
| 预订成功 | `POST /api/bookings` 或周期预订成功落库后，事务提交后立即入队 | `booking_success` |
| 即将开始 | 预订 `start_at` 前 15 分钟 | `booking_upcoming` |
| 被管理员取消 | 管理员调 `POST /api/admin/bookings/{id}/cancel` 成功后 | `booking_cancelled` |

> 微信订阅消息的硬性限制：**每订阅一次只能下发一条**。因此前端每次用户进入"预订创建页"时（或提交前）调 `wx.requestSubscribeMessage` 让用户一次性订阅这 3 个模板，后端据此累积 `notify_quota`。这是订阅消息 API 的既定约束，不能绕过。

### 12.2 模板字段设计

> 实际模板 ID 需要在微信公众平台申请后填到 `system_config` 表；下面的字段示意仅做参考，真实字段名以微信控制台生成为准。

**`booking_success`（预订成功通知）**

| 字段 | 示例 |
|---|---|
| thing1（会议室） | `大会议室 A` |
| date2（时间） | `2026-04-20 14:00-15:30` |
| thing3（主题） | `产品评审` |
| thing4（备注） | `如需取消请在开始前 2 小时操作` |

**`booking_upcoming`（会议即将开始）**

| 字段 | 示例 |
|---|---|
| thing1（会议室） | `大会议室 A` |
| time2（开始时间） | `14:00` |
| thing3（主题） | `产品评审` |
| thing4（位置） | `3F 东` |

**`booking_cancelled`（预订被取消）**

| 字段 | 示例 |
|---|---|
| thing1（会议室） | `大会议室 A` |
| date2（原时间） | `2026-04-20 14:00-15:30` |
| thing3（取消原因） | `设备维修` |
| thing4（操作人） | `管理员` |

### 12.3 流程

```
[小程序] 进入预订创建页
   └─ wx.requestSubscribeMessage([T_success, T_upcoming, T_cancelled])
        用户可整体/逐项接受或拒绝
      ▼
   └─ POST /api/notify/subscribe-report  { results: {...} }
      ▼
[后端] notify_quota 表：accept 的模板 quota += 1（封顶 10）
      ▼
[小程序] POST /api/bookings
      ▼
[后端] 预订成功入库 → 触发 "预订成功" 通知
      └─ 检查 notify_quota[booking_success] > 0？
           是 → 扣 1，调微信 sendMessage，写 notify_log
           否 → 写 notify_log (status=3 跳过)，不阻塞主流程
```

### 12.4 "即将开始"的调度

用 **APScheduler + MySQL JobStore**（或纯 DB 轮询）实现：

- 每当预订创建成功，在 `notify_log` 写一条 `scene=upcoming, status=0, planned_at=start_at - 15min` 的待发记录
- 调度器每分钟扫 `SELECT * FROM notify_log WHERE status=0 AND planned_at <= NOW() LIMIT 100`
- 逐条尝试下发：有配额则发，无则置 `status=3`；发送结果回写 `status` 与 `errmsg`
- 预订被取消时把该 booking 未发出的 `upcoming` 记录标记为 `status=3`（跳过）

**幂等保证**：同一 `(booking_id, scene)` 在 `notify_log` 中至多一条非取消状态的记录（由查询 `idx_booking_scene` 配合业务代码保证）。

### 12.5 "被管理员取消"

管理员取消接口成功后，对被取消的每条 booking 同步入队：

- 写 `notify_log(scene=cancelled_by_admin, status=0)`
- 同步或异步（推荐异步，走同一调度器或独立 worker）下发
- 取消原因从 `booking.cancel_reason` 取，操作人从 `cancelled_by` 取

用户自己取消自己的预订**不**下发通知（自己操作的，没必要打扰自己）。

### 12.6 失败与重试

- 微信 API 非临时错误（模板不存在、用户无配额、用户关闭通知）：直接 `status=2` 不重试
- 网络/超时错误：最多重试 3 次，间隔 30s / 2min / 10min
- `notify_log.errmsg` 保留最后一次错误信息，便于排查

### 12.7 关于 openid 与 unionid

当前设计**只用 openid**，不接 unionid：

- 单端（小程序）使用，openid 已经是该小程序下的唯一标识
- `user.unionid` 字段保留在表结构里，为将来多端（公众号 / 网站扫码 / 开放平台）留扩展位
- 下发订阅消息只需要 `touser = openid`，与 unionid 无关

---

## 13. 初始化与部署约定

### 13.1 管理员账号初始化

**方式**：由 Alembic 的首版迁移（`0001_init.py`）在建表后写入；**不**走"后端首次启动时自动建账号"路径。

```python
# alembic/versions/0001_init.py 里的 upgrade() 末尾
from passlib.hash import bcrypt
import os

username = os.environ.get("INIT_ADMIN_USERNAME", "admin")
password = os.environ.get("INIT_ADMIN_PASSWORD", "admin123")
pw_hash  = bcrypt.hash(password)

op.execute(text("""
    INSERT INTO admin_user (username, password_hash, real_name, must_change_password, status)
    VALUES (:username, :pw_hash, '系统管理员', 1, 1)
    ON DUPLICATE KEY UPDATE id=id   -- 幂等：已存在则什么都不做
"""), {"username": username, "pw_hash": pw_hash})
```

要点：

- **幂等**：`ON DUPLICATE KEY UPDATE id=id` 让重复执行迁移不出错、不覆盖已改过的密码
- **强制改密码**：`must_change_password = 1`，管理员首次登录后端必须返回该标志，前端强制跳转改密码页
- **凭据来源**：优先读 `INIT_ADMIN_PASSWORD` 环境变量；未设置时用硬编码默认值 `admin123` 并在后端启动日志里打红色告警提示立即修改

### 13.2 订阅消息模板 ID 配置

模板 ID 在微信公众平台申请通过后，写入 `system_config`：

```sql
INSERT INTO system_config(`key`, value, description) VALUES
 ('wx_tpl_booking_success',   '',  '订阅消息模板ID：预订成功'),
 ('wx_tpl_booking_upcoming',  '',  '订阅消息模板ID：即将开始'),
 ('wx_tpl_booking_cancelled', '',  '订阅消息模板ID：被管理员取消'),
 ('notify_quota_cap',         '10','单用户单模板配额上限（防累积滥用）'),
 ('notify_upcoming_minutes',  '15','提前多少分钟推送"即将开始"');
```

管理端在"系统参数"页提供表单填写这些值；值为空时后端跳过下发并在日志告警（不阻塞预订）。

### 13.3 启动顺序

```
docker compose up -d mysql redis          # 1. 起基础设施
cd backend && alembic upgrade head        # 2. 建表 + 注入默认管理员 + 默认参数
uvicorn app.main:app --reload             # 3. 起 API
# 调度器默认随 FastAPI 启动 (app.on_event("startup") 里初始化 APScheduler)
```

多副本部署时**只允许一个副本跑调度器**：靠环境变量 `RUN_SCHEDULER=true` 开关控制，其他副本设为 false。单机部署默认 true。

### 13.4 任务清单补充

在第 11 章任务清单中追加以下条目：

- [ ] **T-BE-15**：`alembic/versions/0001_init.py` — 建表 + 默认 `system_config` + 默认管理员（带 `must_change_password=1`）
- [ ] **T-BE-16**：管理员改密码接口 `PUT /api/admin/me/password`；首次登录后必须调一次才能继续使用其他接口
- [ ] **T-BE-17**：`notify_service` — 订阅上报、配额管理、模板发送（封装微信 `subscribeMessage.send`）
- [ ] **T-BE-18**：APScheduler 集成 — 扫 `notify_log` 发送 `upcoming`；支持 `RUN_SCHEDULER` 开关
- [ ] **T-BE-19**：在 `booking_service.create` / `recurrence_service.expand_and_create` / 管理员取消接口里接入通知入队（事务提交后再入队，避免"主操作回滚但通知已发"）
- [ ] **T-MP-09**：在预订创建页接入 `wx.requestSubscribeMessage`，把结果 POST 到 `/api/notify/subscribe-report`
- [ ] **T-ADM-08**：系统参数页增加"订阅消息模板 ID"输入项
- [ ] **T-ADM-09**：管理员首次登录后强制跳转改密码页
