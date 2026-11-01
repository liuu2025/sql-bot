# 数析本地运行（docker-local）

> 本目录提供完整环境构建及复用现有运行时的本地快速更新。
> 所有资源统一 `sqlbot-local-` 前缀，避免本机多个数析开发栈相互冲突。

## 启动 / 停止

```powershell
# 先按 private/README.md 创建 private/sqlbot.local.env
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml up -d --build   # 首次构建并启动
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml ps
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml logs -f app
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml stop       # 停止，保留数据
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml down       # 删容器与网络，保留数据卷
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml down -v    # 连数据卷一起删
```

应用和数据库使用 `restart: unless-stopped`，Docker 引擎启动后会自动恢复运行；若此前手动停止过，需再次启动。此策略不负责启动 Docker Desktop 本身。

## 端口（既定 7200-7299 区间）

| 宿主端口 | 容器端口 | 用途 |
| --- | --- | --- |
| 7200 | 8000 | Web UI + REST API |
| 7201 | 8001 | MCP server（`GET /mcp` SSE + `POST /mcp/messages/`） |
| — | 5432 | 系统库 PG，仅容器网络内可见（不对外暴露） |
| 7202 | 3000 | 预留：g2-ssr（MCP/小助手图表转 PNG），**当前未启用** |
| 7203 | — | 预留：演示业务库，**加进本 compose，不另起栈** |

## 使用方式

本地 Compose 已启用单人模式：浏览器打开 http://127.0.0.1:7200 会自动建立内部会话并进入工作台，不需要输入账号密码。数据库中的固定内部账号和工作区归属仍保留，用于兼容现有数据与接口。自动会话默认有效 60 分钟，页面重新加载会重新建立；模式关闭后带本地标记的令牌立即失效。固定账号必须为启用的内置管理员且关联有效工作区，异常时不会自动创建或重置账号。

该模式只适合本机或可信局域网。能够访问服务的人都可以使用同一内部管理员能力；主导航保留智能问数、数据源、模型设置，表/字段问数范围在数据源内配置，多用户权限分配及退出、改密入口隐藏。数据、工作区归属和 SQL 校验仍沿用现有实现，不新增迁移。

**不要把 7200 端口映射到公网，也不要经反向代理或隧道公开。** 服务端只按实际连接地址校验本机/私网来源，不信任转发头；Docker NAT 或代理可能把公网访问转换成私网来源，因此地址校验不能替代网络隔离。浏览器只允许同源建立本地会话，禁止跨站请求。

恢复普通登录：把 `compose.yaml` 中 `SQLBOT_LOCAL_SINGLE_USER_MODE` 改为 `"false"`，从仓库根运行 `npm --prefix frontend run build`，再运行下方 Compose 更新命令。带本地模式标记的会话会被拒绝；原普通登录会话按原规则保留。如需撤销全部既有令牌，还需在 `private/sqlbot.local.env` 中更换 `SQLBOT_SECRET_KEY` 并重建应用容器。数据库和数据卷保持不变。

### 普通登录（未启用单人模式时）

浏览器打开 http://127.0.0.1:7200，使用本机私有环境中配置的管理员账号和密码。不要把登录凭据写入仓库或文档。

**注意：登录接口不接受明文**。`/api/v1/login/access-token` 是 OAuth2 表单 + 凭据 RSA 加密：
- 公钥：`GET /api/v1/system/config/key`（免鉴权）
- 加密方式：**RSA PKCS#1 v1.5**（不是 OAEP；xpack 的 `encryptOAEP` 那条路会返回 `Incorrect decryption.`）
- 表单字段：`username` / `password`，值为 Base64(RSA(明文))
- 拿到 token 后请求头 `X-SQLBOT-TOKEN: Bearer <token>`

因此无法用 curl 直接登录，脚本化调用需先按上述方式加密。

## 复用已有运行时快速更新

当本机已存在 `sqlbot-local-app:dev`，且 Python 依赖没有变化时，从仓库根目录运行：

```powershell
npm --prefix frontend install
npm --prefix frontend run build -- --mode local-single-user
docker compose -f docker-local/compose.yaml -f docker-local/compose.ui.yaml up -d --build app
```

`Dockerfile.runtime` 基于已有运行时复制业务源码与构建后的页面，新镜像为 `shuxi-workbench:local`。这样无需重复下载 Python 大型依赖和嵌入模型。前端构建产物必须先生成。依赖发生变化或新机器首次启动时，先使用原 `Dockerfile` 完整构建。

业务代码继续位于 `/opt/sqlbot/app`，前端位于 `/opt/sqlbot/frontend/dist`；系统库、上传目录、日志、图片目录和数据卷保持原路径。只更新应用容器，不删除数据卷。

## 环境要点 / 已知限制

- **Excel/CSV 数据**：上传后物化到此编排中已运行的 PostgreSQL，Windows 无需安装数据库。导入和查询统一沿用 `SQLBOT_DB_URL`；设置该地址时不会回退到独立 `POSTGRES_*` 默认值。数据保存在 `sqlbot-local-pgdata` 卷，停止容器后仍保留。
- **网络**：本机 Docker 默认地址池被其他项目 30+ 网络占满（`all predefined address pools have been fully subnetted`），故 `sqlbot-local` 显式使用 `10.72.0.0/24`。不要删别人的网络来"修"这个问题。
- **依赖漂移**：实测 `sqlglot 30.25.0`（pyproject 下限 `>=28.6.0`）、`torch 2.14.1+cpu`、`sqlbot-xpack 0.0.5.41`。SQL 校验依赖 sqlglot AST 行为，出现"误判/漏判"先怀疑版本。
- **嵌入模型**：`shibing624/text2vec-base-chinese` 已在构建期落到镜像内 `/opt/sqlbot/models/embedding/...`（约 1.9GB，含 HF 缓存副本）。删除该目录会导致 `HuggingFaceEmbeddings` 拿本地路径当仓库名去远端下载而失败。
- **未配大模型**：默认模型未设置时提问会报错（`model_factory.py:157`）。需在主导航「模型设置」添加 OpenAI 兼容端点。
- **单进程**：`CACHE_TYPE=memory` + `uvicorn --workers 1`（内存缓存不支持多进程）。
- **MCP 断连噪音**：MCP 客户端突然断开时日志会出现 `starlette ... AssertionError`（`BaseHTTPMiddleware` 包裹 SSE 的上游设计），不影响主服务。

## 验收基线（2026-10-28 实测）

- alembic 迁移全量执行，public schema 31 张表；`pgvector 0.8.7` 已启用
- `admin` 用户存在（id=1, oid=1, status=1）
- `GET /` → 200，前端 assets → 200，`/xpack_static/license-generator.umd.js` → 200
- `EmbeddingModelCache.get_model().embed_query(...)` → dim=768
- 加密登录 → JWT；`GET /api/v1/chat/list` → `{"code":0,"data":[]}`
- `GET :7201/mcp` → `event: endpoint` + `session_id`
- 容器内存：app ≈ 0.9GiB，pg ≈ 46MiB（Docker VM 7.6GiB）
