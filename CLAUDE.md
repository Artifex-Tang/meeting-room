# CLAUDE.md

> 本文件是 Claude Code 在本仓库工作的"常驻守则"。每次开启新会话时，Claude Code 都应先读本文件，再读 `SPEC.md` 的相关章节。

---

## 0. 你正在做什么

这是一个会议室预订系统，包含三个工程：

- `backend/` — Python 3.11 + FastAPI + MySQL 8 + Redis（可选）+ APScheduler（订阅消息调度）
- `miniapp/` — 微信原生小程序（员工端）
- `admin-web/` — Vue 3 + Vite + Element Plus（管理端）

完整需求、数据库、接口、算法、消息通知、初始化约定写在仓库根目录的 `SPEC.md`。**它是唯一权威来源**，与本文件冲突时以 SPEC.md 为准。

---

## 1. 工作流程（开启任务前必读）

### 1.1 每个任务的标准流程

1. **读取任务编号**：用户会给出任务编号（如 `T-BE-08`）。先在 `SPEC.md` 第 11 章 / 13.4 节找到该任务，并读取任务条目中引用的所有章节
2. **确认歧义**：如果 SPEC.md 对某处描述不清、或你判断有多种合理实现，**先问，不要猜**。具体见 §2
3. **列计划**：在实际写代码前，用 2–5 句话说明你打算改哪些文件、为什么这么分层，等我确认后再动手
4. **实现**：按 `SPEC.md §10` 规定的目录结构放代码，不要自创目录
5. **测试**：后端任务默认配套 pytest 单元测试；前端任务至少要 `npm run build` 能过
6. **交付**：任务完成时给一段 CHANGELOG，列出新增/修改/删除的文件，并说明如何本地验证

### 1.2 不要做的事

- **不要改 `SPEC.md`**，除非用户明确要求。发现规格问题，先在回复里指出并建议改法，让用户决定
- **不要跳过校验顺序**。`SPEC.md §5.4` 定义了预订校验的 7 步顺序，这是业务安全边界，不能乱序或合并
- **不要省略事务**。所有写入路径（预订创建、周期展开、取消）必须在事务内完成，冲突检测必须持有 `room` 行锁
- **通知入队必须在事务提交后**。预订事务回滚但通知已发会造成"用户收到了不存在的预订通知"，典型脏写。入队点必须放 `session.commit()` 之后
- **通知失败不得阻塞主流程**。`notify_service` 的错误只记录到 `notify_log.errmsg`，不抛出影响预订/取消接口的返回
- **不要自作主张加依赖**。需要新增 pip/npm 包时，先在回复里说明理由，等确认
- **不要为了通过测试而弱化约束**。测试失败说明代码或测试有问题，不要用 `if TESTING` 绕过事务/锁
- **不要碰生产数据**。本地只用 `docker compose up` 起的 MySQL
- **多副本部署感知**：涉及调度器（APScheduler）的代码必须读 `RUN_SCHEDULER` 环境变量，为 false 时不启动调度线程

---

## 2. 遇到歧义时怎么问

在动手前，用下面的格式提问：

```
我在实现 T-BE-XX 时遇到以下不明确的地方：

1. [问题一]：SPEC §X.Y 中描述了 A，但没有说明 B 情况下如何处理。
   我倾向于 [方案甲]，理由是 ...
   另一种合理做法是 [方案乙]，理由是 ...
   请确认选哪个。

2. [问题二]：...

在得到回复前我不会开始写代码。
```

**什么算"值得问"**：涉及业务规则、数据一致性、权限边界的都问。命名、文件拆分、注释风格这类可以自己决定，出错也容易改回来。

---

## 3. 代码规范

### 3.1 Python（后端）

- Python 3.11，类型注解 **必写**（函数参数与返回值）
- 格式化：`black` 默认配置（行宽 88）；`ruff` 做 lint
- 包管理：`requirements.txt`（固定大版本），不用 poetry
- 日志：用 `logging.getLogger(__name__)`，不要 `print`
- 异常：业务错误抛 `BusinessException(code, message, data=None)`；不可预期错误让它向上冒，由全局 handler 捕获

### 3.2 SQL & ORM

- 所有表、字段名 **小写 + 下划线**
- 查询优先用 SQLAlchemy ORM；涉及 `FOR UPDATE`、复杂 JOIN、批量 INSERT 时允许用 `text()` 或 Core
- 写入路径必须显式 `begin()` 开启事务；不要依赖 autocommit
- 任何用户输入拼到 SQL 里之前必须参数化，**零例外**

### 3.3 FastAPI 约定

- 一个 resource 一个 router 文件，放在 `app/api/v1/` 下
- 路由签名只做「参数校验 + 调 service + 包装响应」，业务逻辑都在 service 层
- Service 层只收 DTO（Pydantic 或 dataclass），不收 Request 对象
- 所有响应走 `app/core/response.py` 的 `ok(data)` / `fail(code, message, data)`

### 3.4 Vue（管理端）

- Vue 3 `<script setup>` + TypeScript
- 组件命名：PascalCase（文件名与组件名一致）
- API 调用都封装在 `src/api/<module>.ts`，组件里不直接 `axios.xxx`
- 业务状态用 Pinia store；瞬时状态（表单、弹窗开关）用组件内 `ref`
- **路由守卫**：如果当前管理员 `must_change_password=1`，拦截一切非"改密码"路由，强制跳转 `/profile/change-password`

### 3.5 小程序

- 原生小程序，不引 Taro/uni-app
- 统一用 `utils/request.js` 发请求，不要散落的 `wx.request`
- 页面不做业务计算，复杂逻辑挪到 `utils/` 或 `services/`
- 避免 `setData` 大对象；时间条组件要注意 `setData` 批量合并
- **订阅消息**：`wx.requestSubscribeMessage` 只能由用户点击事件触发，不要放在 `onLoad` 里；订阅后必须立刻 POST `/api/notify/subscribe-report`

---

## 4. 测试

### 4.1 后端测试

- 工具：`pytest` + `pytest-asyncio`（如走异步）
- 测试库：默认用独立的 MySQL test schema（`meeting_test`），**不要用 SQLite 替代**——因为本系统依赖 `FOR UPDATE` 行锁的真实行为
- 对每个 service 至少覆盖：happy path、授权失败、规则违反、并发冲突（用 threading 或 asyncio 模拟）
- 时间相关的逻辑（取消时限、"即将开始"调度、JWT 过期）用 `freezegun` 冻结时间
- 任务交付时附一句"本任务跑通了哪些 test case"

### 4.2 冲突检测专项

`booking_service.create` 与 `recurrence_service.expand_and_create` 必须有如下并发测试：

```python
def test_two_users_book_same_slot_only_one_wins():
    # 两个线程同时预订同一会议室同一时段，只能一个成功，另一个拿到 40901
    ...
```

这是核心安全性保证，不能只测串行路径。

### 4.3 通知服务测试

- mock 掉微信 `subscribeMessage.send` API（不要真的发）
- 覆盖：配额充足时发送成功、配额为 0 时跳过、发送失败重试、同一 `(booking_id, scene)` 幂等
- 管理员取消 → 通知入队；用户自己取消 → 不入队

---

## 5. Git 提交

- 一个任务一个 commit，消息格式：`[T-BE-08] booking: 实现单次预订与冲突检测`
- 不要把 `.env`、`__pycache__`、`node_modules`、`dist` 提交进去（已在 `.gitignore`）
- 如果一个任务改动超过 15 个文件，先停下来汇报，大概率是任务拆得太大

---

## 6. 目录与启动

```
meeting-room/
├── SPEC.md               # 设计规格（权威文档）
├── CLAUDE.md             # 本文件
├── README.md
├── docker-compose.yml    # MySQL + Redis + backend
├── .env.example          # 环境变量模板
├── .gitignore
├── backend/
├── miniapp/
└── admin-web/
```

**本地启动**（完整流程详见 README）：

```bash
cp .env.example .env
docker compose up -d mysql redis        # 起基础设施
cd backend && pip install -r requirements.txt
alembic upgrade head                     # 建表 + 注入默认管理员 + 默认参数
uvicorn app.main:app --reload            # 起后端（APScheduler 随之启动）
```

默认管理员 `admin / admin123`（见 `.env`），**首次登录系统强制要求改密码**。

---

## 7. 当前进度

> 每完成一个里程碑，在这里追加一行（格式：`- [YYYY-MM-DD] M1 完成 — 说明`）。

- [x] M1 基础框架 — 2026-04-18 完成（T-BE-01/02/03/15：FastAPI骨架、12张ORM模型、Alembic迁移、默认管理员注入）
- [x] M2 核心域 — 2026-06-01 完成（T-BE-04/05/06/07/16：JWT/deps、微信登录、管理员登录、权限CRUD、改密码接口）
- [x] M3 预订 — 2026-06-01 完成（T-BE-08/09/11：booking_service.create含锁+冲突、availability查询、用户取消）
- [x] M4 周期预订 — 2026-06-01 完成（T-BE-10：recurrence_service.expand_and_create、整批冲突检测、周期取消）
- [x] M5 管理端 — 2026-06-01 完成（T-ADM-01~09：Vue3全页面构建通过，权限抽屉、改密码强制流程）
- [x] M6 小程序 — 2026-06-01 完成（T-MP-01~09：8页全实现，time-bar组件、预设/自定义预订、订阅消息上报）
- [x] M7 打磨 — 2026-06-01 完成（T-BE-13/14/17/18/19：单元测试、Docker、通知服务+调度器、限流、审计日志）

---

## 8. 关键决策留痕

> 实现过程中如果偏离了 SPEC.md 或做了影响面广的权衡，记在这里，不要只留在 commit message 里。

- 微信登录：**仅绑定 openid**，不接 unionid（`user.unionid` 字段保留做将来多端扩展）
- 消息通知：**订阅消息**（三模板：预订成功 / 即将开始 / 被管理员取消），前端每次进预订页触发订阅；配额与幂等由 `notify_quota` + `notify_log` 管理
- 管理员账号：**Alembic 首版迁移注入**（幂等），`must_change_password=1` 强制首登改密
- 调度器：APScheduler + DB 轮询，多副本部署靠 `RUN_SCHEDULER` 开关避免重复发送
- 限流：in-memory 计数器（`app/core/rate_limit.py`）；登录 5次/min/IP+账号，预订 30次/min/用户；单实例足够，多实例部署需换 Redis 实现
- 审计日志：`admin_service.write_op_log()` 写 `operation_log`；所有管理员写操作（room/user/dept/perm/booking/config/password）均已接入；失败只记录日志不影响主流程
