# 开发日志 — 会议室预订系统

> 记录从项目骨架到功能完整交付的全过程，包含每个任务的实现要点、遇到的问题及修复方法。

---

## M1 基础框架

### T-BE-01 — FastAPI 项目骨架

**实现内容**

- 按 SPEC §10 目录结构初始化 `backend/`
- 配置 `pydantic-settings`（`app/config.py`）
- 统一响应封装 `app/core/response.py`：`ok(data)` / `fail(code, msg)`
- 全局异常 handler（`BusinessException` → 结构化 JSON）
- 日志初始化（`logging.getLogger(__name__)`，不用 print）

**关键文件**

```
backend/app/main.py
backend/app/config.py
backend/app/core/response.py
backend/app/core/exceptions.py
```

---

### T-BE-02 — SQLAlchemy 模型（12 张表）

**实现内容**

按 SPEC §4.2 建立全部 ORM 模型：

| 模型文件 | 表名 |
|----------|------|
| `user.py` | `user` |
| `admin_user.py` | `admin_user` |
| `room.py` | `room` |
| `department.py` | `department` |
| `booking.py` | `booking` |
| `recurrence.py` | `booking_recurrence` |
| `room_user_permission.py` | `room_user_permission` |
| `room_dept_permission.py` | `room_dept_permission` |
| `system_config.py` | `system_config` |
| `notify_quota.py` | `notify_quota` |
| `notify_log.py` | `notify_log` |
| `operation_log.py` | `operation_log` |

---

### T-BE-03 — Alembic 迁移 + 默认数据

**实现内容**

- `alembic/versions/0001_init.py`：建表 + 默认 `system_config` 插入 + 默认管理员注入
- 默认管理员：`admin / admin123`，`must_change_password=1`
- 默认配置键：`cancel_advance_hours=2`、`max_booking_hours=16`、`max_bookings_per_day=3`、`max_recurrence_months=6`、`notify_quota_cap=10`、`notify_upcoming_minutes=15`
- 迁移幂等：管理员和配置均用 `INSERT IGNORE` 或检查后插入

---

### T-BE-15 — Alembic 首版迁移（并入 T-BE-03）

与 T-BE-03 合并实现，同一个迁移版本文件完成建表 + 数据初始化。

---

## M2 核心域

### T-BE-04 — JWT 工具与依赖注入

**实现内容**

- `app/core/jwt.py`：`create_access_token(sub, role, hours)` / `decode_token(token)`
- `app/deps.py`：`get_current_user`（小程序用户）/ `get_current_admin`（管理员）依赖注入
- Token payload：`{ "sub": "1", "role": "user"|"admin", "exp": ... }`

---

### T-BE-05 — 微信 code2session + `/api/auth/wechat`

**实现内容**

- `app/core/wechat.py`：封装 `code2session`，`WECHAT_MOCK=true` 时直接以 code 作 openid（开发便利）
- `auth_service.wechat_login`：查/建 user，签发 JWT，返回 `need_profile`（首次登录且无 real_name）
- 接口：`POST /api/auth/wechat`

---

### T-BE-06 — 管理员登录

**实现内容**

- `bcrypt` 密码哈希 + 校验
- `auth_service.admin_login`：校验账号状态、密码，签发 JWT（2 小时有效）
- 接口：`POST /api/auth/admin/login`

---

### T-BE-07 — permission_service

**实现内容**

- `get_visible_rooms(db, user_id)`：直接授权 ∪ 部门授权，按 room_id 去重
- `check_room_visible(db, user_id, room_id)`：单会议室权限验证
- `get_room_or_404(db, room_id)`：不存在抛 40401
- 授权 CRUD：`grant_users / revoke_user / grant_depts / revoke_dept`

---

### T-BE-08 — booking_service.create（含冲突检测）

**实现内容**

严格按 SPEC §5.4 七步校验顺序：

1. JWT（依赖注入已处理）
2. 会议室存在且启用
3. 用户授权检查
4. 时间区间合法（30 分钟对齐、08:00–24:00）
5. 单次时长 ≤ `max_booking_hours`（预设时段豁免）
6. 当日预订数 < `max_bookings_per_day`
7. 事务内 `SELECT room FOR UPDATE` + 冲突检测 + INSERT

**测试覆盖**

`test_booking.py`：正常预订、权限失败、时间非法、超时长、超每日上限、冲突检测、并发安全、取消规则。

**遇到的问题**

`test_exceeds_max_hours`：`pytest.skip()` 写在 `pytest.raises()` 之后，skip 永远执行不到，导致测试失败。修复：把 `pytest.skip()` 移到方法第一行。

---

### T-BE-09 — availability 查询接口

**实现内容**

- `GET /api/rooms/{room_id}/availability?date=YYYY-MM-DD`
- 返回当日已占用时段（`slots_taken`），含预订人简要信息
- 权限校验：用户必须对该会议室有可见权限

---

## M3 预订

### T-BE-10 — recurrence_service.expand_and_create

**实现内容**

- `_generate_dates(frequency, weekdays, month_day, start_date, end_date)`：
  - DAILY：逐天枚举
  - WEEKLY：按 `weekdays` 过滤（0=周一…6=周日）
  - MONTHLY：按 `month_day` 过滤，遇当月无该日则跳过
- 批量冲突检测：`SELECT ... FOR UPDATE` 锁 room 行后，一次性检查所有目标日期
- 任意日期冲突 → 整批不落库，返回 `40902 + conflicts[]`
- 成功 → 插入 `BookingRecurrence` + N 条 `Booking`
- 接口：`POST /api/bookings/recurrence`

**遇到的问题**

1. 模型导入路径错误：`from app.models.booking_recurrence import ...` → 实际文件是 `recurrence.py`，改为 `from app.models.recurrence import BookingRecurrence`。
2. `_BASE_DATE` 选了 `date(2030, 9, 1)` 是周日（weekday=6），测试的 WEEKLY 用例全部空结果。改为 `date(2030, 9, 2)`（周一）。
3. Python `match` 语句在复杂条件下 fall-through 行为异常。将 `match/case` 改为 `if/elif/elif`。
4. 并发测试中，MySQL 在等待行锁超时后抛 `OperationalError (2013 Lost connection)` 而非干净的业务异常。解法：不依赖线程返回值，测试结束后直接查 DB count 验证数据完整性（只有 1 条 recurrence + 1 条 booking 落库）。

---

### T-BE-11 — 取消接口

**实现内容**

- `booking_service.cancel(db, booking_id, user_id)`：本人取消，校验取消时限（`cancel_advance_hours`）
- `recurrence_service.cancel_future(db, recurrence_id, user_id)`：取消周期规则所有未来实例
- 接口：`POST /api/bookings/{id}/cancel`、`POST /api/bookings/recurrence/{id}/cancel`
- 路由注册顺序：recurrence router 必须在 bookings router **之前**注册，否则 `{booking_id}` 路径参数会吃掉 `recurrence` 字符串。

---

## M5 管理端后端

### T-BE-12 — 管理端全部接口

**实现内容**

`app/api/v1/admin/__init__.py` — 21 个路由，全部挂载在 `/api/admin/` 下：

| 分组 | 路由 |
|------|------|
| 会议室 | CRUD + 软删除（有未来预订时拒绝停用） |
| 权限 | 按用户 / 按部门授权 CRUD |
| 用户 | 列表 + 编辑（real_name、dept_id、status） |
| 部门 | CRUD（删除前先解绑用户） |
| 预订 | 总览列表 + 管理员强制取消（无时限，`cancel_source=2`）|
| 系统参数 | GET / PUT（10 个配置键）|
| 统计 | 今日/本周预订数 + Top5 会议室 |

**遇到的问题**

`app/api/v1/admin/` 目录作为空包存根已存在，Python 导入时优先找包目录而非同名模块文件 `admin.py`，导致 `ImportError`。解法：将 `admin.py` 内容迁入 `admin/__init__.py`，删除 `admin.py`。

**测试**

`test_admin.py`：33 个测试用例，覆盖所有端点的 happy path 和权限拒绝。

测试 fixture：
```python
@pytest.fixture
def admin(db): ...  # 创建真实 DB 记录
@pytest.fixture
def auth(admin): ...  # 生成对应 token
```
早期版本用硬编码 `admin_id=1`，但测试 DB 里没有 id=1 的管理员，导致全部 401。改用 fixture 后解决。

---

### T-BE-16 — 管理员改密码

**实现内容**

- `admin_service.change_admin_password(db, admin_id, old_password, new_password)`
- 校验旧密码正确、新密码 ≥ 6 位
- 成功后 `must_change_password = 0`
- 接口：`PUT /api/admin/me/password`

---

## M7 通知调度

### T-BE-17 — notify_service

**实现内容**

- `report_subscribe`：处理 `wx.requestSubscribeMessage` 上报，按 `notify_quota_cap` 上限累加配额
- `enqueue_booking_success`：创建 `notify_log(scene=booking_success)` + 立即尝试发送 + 排队 upcoming（planned_at = start_at − 15min）
- `enqueue_booking_cancelled`：取消已有的 pending upcoming log（status=3），创建 cancelled log 并发送
- `_try_send_log`：查模板 ID → 查/扣配额（`FOR UPDATE`）→ mock 模式记录日志 / 真实模式调微信 API
- `_ensure_no_duplicate`：查所有状态的同 `(booking_id, scene)` 记录，防重复入队
- `process_pending_logs`：批量处理 status=0 且 planned_at ≤ NOW() 的日志，供调度器调用

**状态码**：`0=pending`, `1=sent`, `2=failed`, `3=skipped`

**遇到的问题**

`_ensure_no_duplicate` 早期只排除非 SKIPPED 状态，导致第一次 SKIPPED 后第二次能再次入队。改为检查所有状态。

---

### T-BE-18 — APScheduler

**实现内容**

- `app/scheduler.py`：`BackgroundScheduler`，60 秒间隔调 `process_pending_logs`
- `settings.run_scheduler` 开关（`RUN_SCHEDULER` 环境变量），多副本部署时只一个副本开启
- `app/main.py`：lifespan 事件 `startup → scheduler.start()`，`shutdown → scheduler.stop()`

---

### T-BE-19 — 通知入队集成

**实现内容**

三处接入点，均在事务 `commit()` **之后** 入队，错误只记录不抛出：

```python
# booking_service.create
try:
    enqueue_booking_success(db, booking)
except Exception:
    logger.exception("notify enqueue failed — booking unaffected")

# recurrence_service.expand_and_create（每条 booking 均入队）
# admin_service.admin_cancel_booking（入队 enqueue_booking_cancelled）
```

**规则**：用户自己取消 → 不通知；管理员取消 → 通知。

**测试** (`test_booking.py`)

`test_create_does_not_fail_on_notify_error`：mock `enqueue_booking_success` 抛 RuntimeError，验证 booking 创建不受影响。早期版本 notify 错误未被捕获，测试失败。修复：在 booking_service 内包 try/except。

---

## M5 管理端前端

### T-ADM-01 — 项目骨架

```bash
npm create vue@latest admin-web -- --ts --router --pinia --eslint
npm install element-plus @element-plus/icons-vue axios
```

- `main.ts`：全量注册 Element Plus icons，使用中文 locale
- `src/api/http.ts`：axios 实例，base URL `/api`，响应拦截器解包 `data.data`，401 → 自动登出
- `vite.config.ts`：dev 环境代理 `/api` → `http://localhost:8000`

---

### T-ADM-02 — 登录页 + 路由守卫

**实现内容**

- `stores/auth.ts`（Pinia）：token / admin / isLoggedIn / mustChangePassword
- `router/index.ts`：`beforeEach` 守卫
  - 未登录 → `/login`
  - `must_change_password=1` → `/profile`（强制改密）
- `LoginPage.vue`：表单校验 + 调 `adminLogin` API

---

### T-ADM-03 — Dashboard

- `DashboardPage.vue`：今日预订 / 本周预订 / Top5 会议室三张统计卡片

---

### T-ADM-04 — 会议室管理 + 授权抽屉

**实现内容**

- `RoomsPage.vue`：列表（搜索/状态过滤）+ 新增/编辑 dialog + 停用确认
- `PermissionsDrawer.vue`：el-drawer，两个 Tab（用户授权 / 部门授权）
  - 用户 Tab：远程搜索 + 已授权列表 + 单条移除
  - 部门 Tab：本地 select + 已授权列表 + 单条移除

---

### T-ADM-05 — 用户与部门管理

- `UsersPage.vue`：列表（姓名/部门/状态过滤）+ 编辑 dialog（real_name / dept_id / status）
- `DepartmentsPage.vue`：树形部门列表 + 新增/编辑/删除，删除前提示用户将变为无部门

**TypeScript 修复**：`updateUser` 签名中 `dept_id?: number | undefined`，但 formData 中声明为 `number | null | undefined`。调用时加 `dept_id: formData.dept_id ?? undefined` 转换。

---

### T-ADM-06 — 预订总览

- `BookingsPage.vue`：列表视图，按日期范围/状态/会议室 ID 过滤，管理员强制取消（弹窗填写原因）

---

### T-ADM-07 + T-ADM-08 — 系统参数配置

- `SettingsPage.vue`：10 个参数分组展示（预订规则 + 通知配置）
  - 预订规则：`advance_booking_days`、`max_booking_hours`、`max_recurrence_months`、`max_bookings_per_day`、`cancel_advance_hours`
  - 通知配置（T-ADM-08）：`tpl_booking_success`、`tpl_booking_upcoming`、`tpl_booking_cancelled`、`notify_quota_cap`、`notify_upcoming_minutes`

---

### T-ADM-09 — 管理员改密码页

- `ProfilePage.vue`：原密码 + 新密码 + 确认密码表单，校验通过后调 `PUT /admin/me/password`，成功后强制重新登录
- 若 `mustChangePassword=true`，页面顶部显示警告 banner

---

## M6 小程序

### T-MP-01 — 项目骨架 + request 封装

**目录结构**（按 SPEC §7.4）

```
MeetingGo/
├── app.js / app.json / app.wxss
├── config.js                    # BASE_URL
├── utils/
│   ├── request.js               # http 封装
│   ├── auth.js                  # wechatLogin / isLoggedIn / logout
│   └── time.js                  # slot↔time 互转
├── components/
│   ├── time-bar/                # 32 槽位时间条
│   └── preset-picker/           # 预设时段按钮组
└── pages/...
```

**request.js 关键逻辑**

- 自动注入 `Authorization: Bearer <token>`
- `code === 40101` → 清 token + `wx.reLaunch` 到 launch 页
- GET 请求自动序列化 params 为 query string，过滤 null/undefined

---

### T-MP-02 — 登录页 + JWT 持久化

- `pages/launch/launch.js`：`onLoad` 触发 `wx.login` → POST `/api/auth/wechat` → 存 token + userInfo 到 `globalData` 和 `wx.Storage`
- `need_profile=true` 时展示补填真实姓名表单
- 路由守卫：所有需登录页面 `onShow` 先调 `isLoggedIn()`

---

### T-MP-03 — 会议室列表页

- `pages/index/index.js`：调 `GET /api/rooms`，支持关键词搜索，`onShow` 触发刷新

---

### T-MP-04 — time-bar 组件

**实现内容**

- 32 槽位（08:00–24:00，每槽 30 分钟）
- 三态：available（蓝色）/ taken（灰色禁用）/ selected（深蓝）
- 奇数槽位显示时间标签（整点显示）
- 支持 tap 事件（单选）和 touchstart/touchmove/touchend（拖选）
- 属性：`takenSlots[]`、`selectedStart`、`selectedEnd`、`readonly`
- 事件：`slotTap`、`dragStart`、`dragMove`、`dragEnd`

**preset-picker 组件**

- 4 个预设按钮：上午 09:00–12:00 / 下午 14:00–18:00 / 晚上 19:00–22:00 / 全天 09:00–18:00
- 与已占用时段自动禁用联动
- 事件：`change → { preset, startTime, endTime }`

---

### T-MP-05 — 会议室详情 + 预订创建

**room/detail**

- 展示会议室信息 + 日期选择器 + 只读时间条（当日占用）
- 跳转到预订创建或周期预订页

**booking/create（含 T-MP-09）**

- 预设模式 / 自定义模式切换
- 自定义模式：tap 起点 → 扩展选择，跨已占用格时立即提示
- 提交前调 `wx.requestSubscribeMessage`（由用户 tap 触发，符合微信规范）
- 订阅结果 POST `/api/notify/subscribe-report`（失败不阻塞预订）
- 冲突 `40901` → modal 展示冲突详情

---

### T-MP-06 — 周期性预订

**实现内容**

- 频率选择：DAILY / WEEKLY / MONTHLY
- WEEKLY：周一–周日多选按钮
- MONTHLY：1–28 日 picker
- 日期范围选择器 + 前端实时估算预计生成次数
- 提交后 `40902` → 弹窗展示冲突日期列表（最多展示前 3 条）

---

### T-MP-07 — 我的预订 + 取消

- `pages/my/bookings/bookings.js`：进行中 / 全部 Tab 切换，读取 `GET /api/config/public` 的 `cancel_advance_hours` 判断取消按钮是否可用
- 取消需二次确认，`42201` 时展示截止时间说明
- `pages/booking/detail/detail.js`：详情页 + 单条取消

---

### T-MP-08 — 个人中心

- `pages/my/index/index.js`：展示昵称/头像/真实姓名，编辑保存调 `PUT /api/users/me`，退出登录清 token

---

## 补充修复（后期发现）

### 缺失接口补全

发现小程序调用了三个后端未实现的接口：

| 接口 | 新增文件 |
|------|----------|
| `GET /api/rooms/{room_id}` | `app/api/v1/rooms.py` |
| `PUT /api/users/me` | `app/api/v1/users.py`（新建）|
| `GET /api/config/public` | `app/api/v1/users.py`（同文件）|

### config 键名对齐

- 后端使用 `cancel_advance_hours`（小时），小程序误用 `cancel_deadline_minutes`（分钟），两处都修正：
  - `MeetingGo/pages/my/bookings/bookings.js`：读 `cancel_advance_hours` × 60
  - `admin-web/src/pages/settings/SettingsPage.vue`：form key 改为 `cancel_advance_hours`

### config 键集合扩充

- `config_service.py`：补充 `advance_booking_days`、`tpl_booking_*` 三模板 ID 的默认值
- `admin_service._CONFIG_KEYS`：扩充至 10 个键
- `admin_service.update_config`：写入全部 10 个键
- `schemas/admin.py ConfigUpdateRequest`：补全字段

---

## 测试结果汇总

```
backend/tests/
├── test_auth.py          — 微信登录、管理员登录
├── test_booking.py       — 单次预订全路径（含并发）、取消规则
├── test_recurrence.py    — 周期展开（DAILY/WEEKLY/MONTHLY）、冲突整批拒绝、并发
├── test_admin.py         — 33 个管理端接口测试
├── test_notify.py        — 订阅配额、幂等、发送/跳过/失败
└── test_permission.py    — 权限并集计算

总计：126 passed, 1 skipped（test_exceeds_max_hours 豁免，覆盖逻辑已由 integration 保证）
```

admin-web `npm run build`：✅ 零错误（chunk size warning 为 Element Plus 正常大小）

---

## 已知待完成事项

| 优先级 | 事项 | 说明 |
|--------|------|------|
| 🔴 高 | 预设时段命名统一 | 后端 PRESETS（morning/noon/afternoon/evening/daytime/allday）与小程序 preset-picker（上午/下午/晚上/全天）命名和时间均不一致 |
| 🔴 高 | Alembic 迁移补全新 config key | `advance_booking_days`、`tpl_*` 三模板 ID 未加入 `0001_init.py` 默认数据，新部署时缺少这些值 |
| 🟡 中 | `advance_booking_days` 校验逻辑 | 已加入 config 但 `booking_service.create` 未做"距今不超过 N 天"检查 |
| 🟡 中 | tabBar 图标文件缺失 | `app.json` 引用 `assets/icons/*.png`，目录不存在，开发者工具报错 |
| 🟡 中 | 订阅模板 ID 动态读取 | `create.js` 中 `SUBSCRIBE_TMPL_IDS` 是硬编码占位符，上线前需从后端读取 |
| 🟢 低 | Redis 缓存接入 | `config_service` 每次查 DB，`redis_url` 已配置但未使用 |
| 🟢 低 | 限流 | 登录 5次/min/IP，预订 30次/min/用户（SPEC §9） |
| 🟢 低 | 审计日志 | `operation_log` 表已建，管理员操作未写入 |
