# START_HERE.md

> 如果你是 Claude Code，第一次打开这个仓库，请按下面顺序读文件。
> 如果你是人类开发者，直接看 `README.md` 就行。

## 阅读顺序

1. **`CLAUDE.md`** — 本仓库的工作约定（代码规范、测试要求、"不要做的事"）
2. **`SPEC.md`** — 设计规格，共 13 章。首次浏览读 §1–§3 + §11 任务清单即可，做到哪个任务再深读对应章节
3. **`README.md`** — 本地启动与常用命令

## 当前仓库状态

只有文档和基础设施配置，**尚无任何代码**。所有后端/前端代码都是待实现状态。

已有的文件：

```
meeting-room/
├── SPEC.md                  ← 设计规格（权威）
├── CLAUDE.md                ← 工作约定
├── README.md                ← 启动说明
├── START_HERE.md            ← 本文件
├── docker-compose.yml       ← MySQL + Redis + backend
├── .env.example
├── .gitignore
└── backend/
    ├── Dockerfile
    └── requirements.txt
```

## 第一个任务

按 `SPEC.md §11.2` 的顺序，第一个任务是 **T-BE-01**：初始化 FastAPI 项目骨架。

推荐把前 4 个基础任务打包做掉（都是地基、耦合紧），做完后应该能本地 `uvicorn app.main:app --reload` 起起来并访问 `/docs`：

- **T-BE-01** — FastAPI 骨架（目录见 SPEC §10）
- **T-BE-02** — SQLAlchemy 模型（所有表见 SPEC §4.2）
- **T-BE-03** — Alembic 初始化 + 首版迁移
- **T-BE-15** — 迁移里注入默认管理员（见 SPEC §13.1）

## 开工提示词（给用户的参考）

用户可以把下面这段发给你：

```
请按 CLAUDE.md §1.1 的流程，实现 T-BE-01 到 T-BE-03 + T-BE-15 这 4 个任务，
目标是本地能 `docker compose up -d mysql redis` + `alembic upgrade head` +
`uvicorn app.main:app --reload` 成功启动，并且 /docs 能打开。

开工前先列实施计划等我确认，不要直接开写。
```

## 进度追踪

每完成一个任务，在 `CLAUDE.md §7` 勾掉对应复选框；做了影响面广的决策，记到 `CLAUDE.md §8`。
