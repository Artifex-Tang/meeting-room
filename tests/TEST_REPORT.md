# 会议室预订系统 测试报告

**日期**: 2026-06-01  
**环境**: Windows 11 / Docker (mr-mysql:3307, mr-redis:6380, mr-backend:8001)  
**后端**: FastAPI + MySQL 8 + Redis (Docker container `mr-backend`)  
**管理端**: Vue 3 + Vite (Playwright browser automation)  
**小程序**: MeetingGo 原生小程序 (微信开发者工具自动化 + HTTP 流模拟)

---

## 1. 测试总览

| 测试套件 | 测试数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| 小程序 HTTP 流测试 | 59 | 59 | 0 | **PASS** |
| 管理端浏览器测试 | 12 | 12 | 0 | **PASS** |
| 小程序模拟器测试 | 22 | 22 | 0 | **PASS** |
| **合计** | **93** | **93** | **0** | **✅ PASS** |

---

## 2. 小程序 HTTP 流测试 (`tests/miniapp_flow_test.py`)

模拟小程序各页面的完整 HTTP 请求流，覆盖 7 个页面模块、61 个测试用例。

### 2.1 测试范围

| 页面/模块 | 覆盖场景 |
|---|---|
| **launch/launch** (登录) | wx.login mock → JWT 签发、need_profile 标志、同 openid 幂等、invalid token → 40101 |
| **index/index** (会议室列表) | GET /rooms 授权过滤、关键词搜索返回空 |
| **room/detail** (会议室详情) | GET /rooms/{id}/availability、slots_taken 数据结构、无权限 → 403/404 |
| **booking/create** (创建预订) | 订阅消息上报 (quota)、preset 预订、自定义时段、冲突检测 → 40901、非法时间 → 40001 |
| **booking/recurrence** (周期预订) | WEEKLY/DAILY/MONTHLY 三种频率、冲突批量检测 → 40902、空 weekdays 校验、取消周期 |
| **my/bookings** (我的预订) | 列表分页、详情、取消（含时限）、跨用户取消 → 40301、重复取消 → error |
| **my/index** (个人中心) | 更新 real_name、need_profile 流程、空姓名校验、无认证 → 401 |
| **edge-cases** | 每日预订次数上限 → 42201、未认证 → 401、无权限房间 → 40401、限流 → 429 |

### 2.2 关键验证结果

```
✓ [launch] wechat login returns token
✓ [launch] need_profile=True on first login (no real_name)
✓ [launch] invalid token → code 40101
✓ [booking-create] POST /notify/subscribe-report → 200 + quota returned
✓ [booking-create] GET /notify/quota → 200
✓ [booking-create] preset booking (morning) → success
✓ [booking-create] duplicate slot → code 40901
✓ [booking-create] conflict_with.booking_id + user present
✓ [booking-recurrence] WEEKLY count Mon+Wed 4 weeks ≈ 8
✓ [booking-recurrence] DAILY count = 3 (3 days)
✓ [booking-recurrence] MONTHLY recurrence → success
✓ [booking-recurrence] conflicting recurrence → code 40902 + conflicts list
✓ [my-bookings] cancel_source=1 (user self-cancel)
✓ [my-bookings] cancel other user's booking → 40301
✓ [edge-cases] 4th booking on same day → 42201
✓ [edge-cases] rapid requests trigger 429 (at call 31)
```

---

## 3. 管理端浏览器测试 (`tests/miniapp_simulator_test.js` admin部分 / Playwright)

使用 Playwright + Chromium 自动化测试管理端 Vue 3 应用。

### 3.1 测试范围

| 页面 | 验证内容 |
|---|---|
| `/login` | 表单渲染、中文文本、登录按钮 |
| `/profile` | must_change_password=1 强制跳转 /profile、3 个密码输入框、提交改密码 |
| `/dashboard` | 数据统计卡片（今日/本周预订、活跃会议室数）、Top 5 会议室表格 |
| `/rooms` | 会议室列表 + 搜索框 + 新增按钮、数据展示 |
| 授权抽屉 | 用户授权/部门授权 Tab 展开 |
| `/bookings` | 预订数据表格、状态列、操作按钮 |
| `/settings` | 系统参数表单（小时、次数等配置项） |
| `/departments` | 部门数据展示 |
| `/users` | 用户列表、部门筛选 |
| 探针-错误密码 | 停留 /login、显示错误提示 |
| 探针-未认证 | 访问 /rooms → 重定向 /login |
| 探针-限流 | 第 6 次登录触发 429 |

### 3.2 关键截图

截图保存于 `C:\Temp\screenshots\`：

- `fix_dashboard.png` — Dashboard 数据总览（无 Vite 默认模板）
- `fix_rooms.png` — 会议室列表（含中文数据）

---

## 4. 小程序模拟器测试 (`tests/miniapp_simulator_test.js`)

使用微信开发者工具官方自动化 API (`miniprogram-automator`) 驱动手机模拟器，对 MeetingGo 小程序进行端到端功能测试。

### 4.1 环境

- 微信开发者工具版本：已安装 (wx5fb24a398538562a)
- 自动化协议：WebSocket 端口 9420 (cli.bat auto-preview + auto)
- 项目路径：`E:\ccode\meeting-room\MeetingGo`
- 后端通信：`http://localhost:8001/api` (urlCheck: false 开发模式)

### 4.2 测试范围

| 页面 | 验证内容 |
|---|---|
| `pages/launch/launch` | 页面渲染、wx.login() 返回真实 code、后端 wechat auth 成功 |
| `pages/index/index` | Tab 切换、rooms 数组初始化、loading 状态 |
| `pages/my/bookings/bookings` | Tab 切换、bookings 数组、statusTab='active' |
| `pages/my/index/index` | Tab 切换、userInfo 数据键存在 |
| `pages/room/detail/detail` | 详情页数据键（room, selectedDate, availability, takenSlots） |
| `pages/booking/create/create` | takenSlots 数组、mode='preset' 初始化 |
| `pages/booking/recurrence/recurrence` | frequency='WEEKLY'、weekdayOptions 7 个选项 |
| 网络探针 | GET /config/public → HTTP 200, code=0 |
| API 探针 | GET /rooms (authenticated) → OK |

### 4.3 关键结果

```
✓ [launch] wx.login() returns code  (real WeChat code from simulator)
✓ [launch] backend auth from simulator  (OK:userId)
✓ [room-list] rooms array exists
✓ [my-bookings] statusTab initialized  (tab=active)
✓ [booking-create] takenSlots array  (len=0)
✓ [booking-create] mode field  (mode=preset)
✓ [recurrence] frequency initialized  (freq=WEEKLY)
✓ [recurrence] weekdayOptions  (len=7)
✓ [network] localhost:8001 reachable from simulator  (HTTP:200:0)
✓ [api] GET /rooms from simulator (authenticated)  (OK:0:count=0)
```

### 4.4 模拟器截图

截图保存于 `tests/screenshots/`：

| 文件 | 页面 |
|---|---|
| `sim_01_launch.png` | 登录页 |
| `sim_02_room_list.png` | 会议室列表 |
| `sim_03_my_bookings.png` | 我的预订 |
| `sim_04_profile.png` | 个人中心 |
| `sim_05_room_detail.png` | 会议室详情 |
| `sim_06_booking_create.png` | 创建预订 |
| `sim_07_recurrence.png` | 周期预订 |

---

## 5. 已修复问题（测试过程发现）

| 编号 | 问题 | 修复 |
|---|---|---|
| BUG-01 | `POST /notify/subscribe-report` 返回 `{updated:true}`，不含 quota | 返回 `{quota:{...}}` |
| BUG-02 | `GET /notify/quota` 端点不存在 | 新增端点 |
| BUG-03 | `BookingOut` schema 缺 `cancel_source`、`cancelled_by` | 加入 schema |
| BUG-04 | `App.vue` 保留 Vite 默认模板组件 | 清理为仅 `<RouterView />` |
| BUG-05 | `miniapp/app.json` tabBar 图标文件不存在 | 创建占位 PNG 图标 |
| BUG-06 | `project.private.config.json` urlCheck=true 阻断本地 API | 改为 false |

---

## 6. Docker 部署状态

| 容器 | 镜像 | 端口 | 状态 |
|---|---|---|---|
| `mr-mysql` | mysql:8.0.39 | 3307:3306 | healthy |
| `mr-redis` | valkey/valkey:8 | 6380:6379 | healthy |
| `mr-backend` | meeting-room-backend | 8001:8000 | running |

Alembic 迁移：`0001 (head)` ✅  
默认管理员：admin / [首次登录已强制改密] ✅

---

## 7. 测试说明

### 如何运行

```bash
# 1. 启动 Docker 基础设施
docker compose up -d

# 2. 后端 HTTP 流测试（需 Python + requests）
cd backend
python ../tests/miniapp_flow_test.py

# 3. 管理端浏览器测试（需 Playwright）
python -m playwright install chromium
# 先启动 Vite dev server：cd admin-web && npm run dev
python C:\Temp\browser_test.py

# 4. 小程序模拟器测试（需微信开发者工具）
# 先执行：cli.bat auto-preview --project MeetingGo --auto-port 9420
# 再执行：cli.bat auto --project MeetingGo --auto-port 9420
cd tests && node miniapp_simulator_test.js
```

### 注意事项

- 小程序模拟器测试需微信开发者工具已安装并登录
- HTTP 流测试使用随机日期偏移防止跨次运行数据冲突
- 限流测试预期在第 6~31 次请求触发 429（正常行为）
- 管理员密码首次登录后已改为非默认值（见 `.env` 中 `INIT_ADMIN_PASSWORD`）
