# 测试说明文档

## 概述

本项目包含三个独立的测试套件，覆盖后端 API、管理端 Web、小程序模拟器三个维度。

---

## 套件一：小程序 HTTP 流测试

**文件**: `tests/miniapp_flow_test.py`  
**性质**: 黑盒接口测试，模拟小程序各页面向后端发起的 HTTP 请求序列  
**运行时间**: ~90 秒  
**用例数**: 59 个

### 设计思路

每个测试函数对应小程序的一个页面，按页面生命周期顺序发请求，包含正常路径与错误路径。

```
test_launch_page      → POST /auth/wechat, GET /rooms(invalid token)
test_room_list_page   → GET /rooms (keyword filter)
test_room_detail_page → GET /rooms/{id}/availability
test_booking_create_page → POST /notify/subscribe-report, GET /notify/quota,
                           POST /bookings (preset/custom/conflict/invalid)
test_recurrence_page  → POST /bookings/recurrence (WEEKLY/DAILY/MONTHLY/conflict)
test_my_bookings_page → GET /config/public, GET /bookings, POST /bookings/{id}/cancel
test_profile_page     → PUT /users/me, need_profile flow
test_edge_cases       → daily limit, rate limit, unauthenticated, no-permission
```

### 防冲突机制

使用运行时随机偏移 `_OFFSET ∈ [500, 900]` 天，加上每次创建唯一命名的测试房间（`TestRoom-MP-{OFFSET}`），避免跨次运行产生数据冲突。

### 运行方式

```bash
cd backend
python ../tests/miniapp_flow_test.py
```

**前置条件**：
- Docker 后端在 `http://localhost:8001`
- `WECHAT_MOCK=true`（后端将 wx.login code 直接当 openid）

---

## 套件二：管理端浏览器测试

**文件**: `C:\Temp\browser_test.py`（Playwright + Chromium）  
**性质**: 端到端 UI 测试，真实浏览器驱动  
**运行时间**: ~60 秒  
**用例数**: 12 个

### 覆盖流程

1. 登录页渲染
2. `must_change_password=1` 强制跳转 `/profile`
3. 3-input 密码修改表单提交
4. 新密码重新登录 → `/dashboard`
5. Dashboard 统计卡片验证
6. 会议室页：列表 + 授权抽屉
7. 预订管理页数据展示
8. 系统参数配置页
9. 部门/用户页渲染
10. 探针：错误密码停留登录页
11. 探针：未认证访问重定向 /login
12. 探针：登录限流触发 429

### 运行方式

```bash
# 先启动 Vite dev server (proxy → localhost:8001)
cd admin-web && npm run dev

# 运行测试（需 playwright chromium）
$env:PYTHONIOENCODING = "utf-8"
python C:\Temp\browser_test.py
```

---

## 套件三：小程序模拟器测试

**文件**: `tests/miniapp_simulator_test.js`  
**性质**: 通过微信开发者工具官方自动化 API 驱动真实手机模拟器  
**运行时间**: ~60 秒  
**用例数**: 22 个

### 架构

```
Node.js ──WebSocket──> 微信开发者工具 (port 9420)
                           │
                      手机模拟器
                           │
                    wx.login / wx.request
                           │
                    localhost:8001 (后端)
```

### Token 预注入

由于模拟器运行在微信沙箱中，`wx.request` 需域名白名单。测试通过两步解决：
1. `project.private.config.json` 设置 `"urlCheck": false`（跳过域名校验）
2. Node 侧直接调后端获取 JWT，通过 `mp.evaluate()` 注入 `wx.setStorageSync('token', ...)`，使页面认为已登录

### 核心验证

- **launch**: `wx.login()` 返回真实 code → 后端 WECHAT_MOCK 处理 → JWT 签发
- **tab pages**: `switchTab` 导航成功，页面 data 键名与 JS 源码一致
- **detail pages**: `reLaunch` 导航，页面 data 含预期字段（takenSlots, mode, frequency 等）
- **network probe**: 模拟器内 `wx.request` 可达 localhost:8001

### 运行方式

```bash
# 1. 确认微信开发者工具已登录
cli.bat islogin

# 2. 编译并启动模拟器
cli.bat auto-preview --project E:\ccode\meeting-room\MeetingGo --auto-port 9420

# 3. 启用自动化端口
cli.bat auto --project E:\ccode\meeting-room\MeetingGo --auto-port 9420

# 4. 运行测试
cd tests && node miniapp_simulator_test.js
```

---

## 已知限制

| 限制 | 说明 |
|---|---|
| `navigateTo` 非 tabBar 页面 | DevTools 自动化模式下 navigateTo 无响应，改用 reLaunch 绕过 |
| 限流 in-memory | 单实例有效，多副本部署需改 Redis 实现 |
| 小程序真机测试 | 需真实 AppID 发布版本，WECHAT_MOCK 不适用 |
| 订阅消息通知 | 需在微信平台申请模板 ID 并填入 system_config |
