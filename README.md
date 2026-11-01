# 数析 · 数据问答与分析工作台

对话式数据分析（ChatBI）系统：用自然语言提问，系统基于已配置的数据源生成并安全执行 SQL，返回数据、图表、分析和后续问题建议。后端 FastAPI + SQLModel + LangChain，前端 Vue 3 + AntV。

本仓库提供可复现的本地开发栈，运行方式统一走 `docker-local/`。本地密码、密钥和运行数据放在被 Git 忽略的 `private/` 目录；安全边界见 [SECURITY.md](SECURITY.md)。

## 快速开始

前置：本机已安装并启动 Docker（Docker Desktop 或等价运行时）。

```powershell
# 首次使用：复制 private/README.md 中的模板，填写本机随机密码和密钥
# private/sqlbot.local.env 只保存在本机，不要提交到 Git
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml up -d --build
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml ps
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml logs -f app
```

打开 http://127.0.0.1:7200。普通认证模式的初始账号由本地环境配置提供；首次登录后在「系统管理 → AI 模型配置」里添加 OpenAI 兼容的大模型（填服务地址与 API Key，点「获取模型」从服务端拉取可用模型列表），并设为系统默认模型。

不要在 README、提交记录或 issue 中粘贴 API Key、数据库密码、JWT/应用密钥或真实业务数据。

详细说明、端口分配、已知限制和验收基线见 [`docker-local/README.md`](docker-local/README.md)。

前端页面、模型接入与本地单人模式的运行方式见 `docker-local/README.md`；已有运行时的快速更新方式使用 `docker-local/compose.ui.yaml`。

## 目录结构

| 路径 | 内容 |
| --- | --- |
| `backend/` | Python 3.11 / FastAPI 服务：对话流程、SQL 生成与校验、数据源与权限、MCP 服务、Alembic 迁移 |
| `frontend/` | Vue 3 + TypeScript + Vite 前端 |
| `g2-ssr/` | Node.js 图表渲染服务（把图表渲染成 PNG，供 MCP/小助手使用；默认未启用） |
| `docker-local/` | 本地隔离运行的构建与编排文件 |
| `tests/browser/` | Playwright 浏览器复现与回归工具 |
| `docs/` | 面向使用者和维护者的公开说明 |

## 能力概览

- 自然语言问数：关键词抽取 → 术语/SQL 示例召回 → 选表 → 生成 SQL → 校验 → 执行 → 生成图表 → 生成分析
- 多数据源：MySQL、PostgreSQL、Oracle、SQL Server、ClickHouse、Doris、StarRocks、Hive、Excel 等
- 权限：行权限、列权限、按工作空间授权
- 集成：Web 嵌入、弹窗嵌入、MCP 调用
- 知识增强：术语表、SQL 示例库、自定义提示词、向量召回

## 说明

`backend/pyproject.toml` 中的 `sqlbot-xpack` 是闭源的商业扩展包，属于运行时硬依赖（启动即导入，缺失则后端无法启动）。使用前请确认你拥有该依赖的许可和下载权限；本仓库不包含其源码或构建产物。
