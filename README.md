# 会议室预订系统

微信小程序 + Vue 管理端 + FastAPI/MySQL 后端。

> 设计规格：见 [`SPEC.md`](./SPEC.md)
> Claude Code 工作约定：见 [`CLAUDE.md`](./CLAUDE.md)

## 快速启动

### 1. 准备环境变量

```bash
cp .env.example .env
# 至少修改：MYSQL_ROOT_PASSWORD、MYSQL_PASSWORD、REDIS_PASSWORD、JWT_SECRET
# 生成 JWT_SECRET：python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 2. 起基础设施

```bash
# 只起 MySQL 和 Redis，后端本地跑（推荐开发期）
docker compose up -d mysql redis
```

### 3. 起后端

**本地运行**（开发时用，便于断点调试）：

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

访问 <http://localhost:8000/docs> 查看 OpenAPI 文档。

**或者容器里跑**：

```bash
docker compose up -d backend
docker compose logs -f backend
```

### 4. 起管理端（Vue）

```bash
cd admin-web
npm install
npm run dev
```

默认 <http://localhost:5173>，登录用 `.env` 里的 `INIT_ADMIN_USERNAME / INIT_ADMIN_PASSWORD`（默认 `admin / admin123`）。

### 5. 小程序

用微信开发者工具打开 `MeetingGo/` 目录。在 `MeetingGo/config.js` 里把 `BASE_URL` 指向后端地址（本地开发时需要配置"不校验合法域名"）。

## 目录结构

```
meeting-room/
├── SPEC.md                 # 设计规格（权威）
├── CLAUDE.md               # Claude Code 工作约定
├── README.md               # 本文件
├── docker-compose.yml
├── .env.example
├── .gitignore
├── backend/                # FastAPI 后端
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── MeetingGo/              # 微信原生小程序
└── admin-web/              # Vue 3 管理端
```

## 常用命令

```bash
# 停止所有服务
docker compose down

# 重置数据库（会丢失所有数据！）
docker compose down -v && docker compose up -d mysql redis

# 进入 MySQL
docker compose exec mysql mysql -u meeting -p meeting

# 看后端日志
docker compose logs -f backend

# 跑后端测试
cd backend && pytest -v
```

## 开发流程

1. 在 `SPEC.md` 第 11 章找到待办任务（如 `T-BE-08`）
2. 使用 `CLAUDE.md §1.2` 末尾的提示词模板启动 Claude Code 会话
3. 每完成一个任务，在 `CLAUDE.md §7` 勾掉对应复选框

## 上线前检查清单

- [ ] 修改默认管理员密码
- [ ] 轮转 `JWT_SECRET`、数据库密码、Redis 密码
- [ ] `WECHAT_MOCK=false` 并填入真实 AppID/AppSecret
- [ ] 配置 HTTPS（小程序强制要求）
- [ ] 从 `docker-compose.yml` 的 backend 服务里移除源码卷挂载和 `--reload`
- [ ] 数据库开启定期备份
