# System Overview For Coding Agents

## Purpose

这个仓库当前是一个研究组知识平台，核心是：

- `mw_public`：公开 wiki
- `mw_private`：私有 wiki
- `assistant_api` / `assistant_worker`：私有知识助手
- `rcf_web` / `pytps_web`：挂载在私有站下的实验工具

主入口不是独立聊天站，而是私有 wiki 内的 `Special:LabAssistant`。

## Runtime Topology

### Main services

- `mariadb`
  - 承载 `labwiki_public` 和 `labwiki_private`
- `assistant_store`
  - PostgreSQL + pgvector，承载 assistant session、chunk、job、draft preview
- `mw_public`, `mw_private`
  - 共享同一个自定义 MediaWiki 镜像
- `assistant_api`
  - FastAPI，同步暴露 `/chat`、`/plan`、`/draft/*`、`/reindex/*`、`/admin/*`
- `assistant_worker`
  - 轮询 `pending` job，执行 wiki/zotero reindex
- `rcf_backend`, `rcf_frontend`
  - RCF 工具的后端与前端
- `tps_web`
  - TPS 工具的 FastAPI + 静态前端
- `caddy_public`, `caddy_private`
  - 对外入口和路径代理

### Private-site path routing

私有站的核心路由在 `ops/caddy/Caddyfile.private`：

- `/tools/assistant/api/*` -> `assistant_api:8000`
- `/tools/tps/*` -> `tps_web:8000`
- `/tools/rcf/*` -> `rcf_frontend:80`
- 其它路径 -> `mw_private:9000`

本地/内网模式会被 `ops/caddy/Caddyfile.private.local` 覆盖。

## Source Of Truth By Concern

| 关注点 | 首选真相源 |
| --- | --- |
| 服务编排、环境变量、端口、卷挂载 | `compose.yaml` |
| 本地/校园内网差异 | `compose.override.yaml` |
| MediaWiki 启动时如何生成/修正 `LocalSettings.php` | `images/mediawiki-app/entrypoint/bootstrap-instance.sh` |
| assistant 路由和接口形状 | `assistant_api/app/main.py`, `assistant_api/app/schemas.py` |
| assistant 后台任务 | `assistant_api/app/worker.py`, `assistant_api/app/services/reindex.py` |
| 工具代理白名单 | `assistant_api/app/clients/tools.py` |
| 运维脚本与验证链路 | `ops/scripts/*.sh` |

## Architectural Constraints

- 公开站和私有站必须继续分离；不要把权限逻辑重新收敛为单 wiki。
- 私有站对 assistant 的写入必须保留“预览 -> commit”两段式。
- Assistant 的状态和检索层继续使用 PostgreSQL，不回写到 MariaDB。
- `bootstrap-instance.sh` 是 MediaWiki 运行时配置的中心；直接改 `state/private/LocalSettings.php` 只会造成下次启动漂移。
- `assistant_worker` 只处理 job 队列，不直接提供 API。

## Typical Task Routing

### 改 assistant 问答行为

先看：

- `assistant_api/app/services/orchestrator.py`
- `assistant_api/app/services/search.py`
- `assistant_api/app/services/llm.py`

### 改私有 wiki 页面入口或扩展挂载

先看：

- `images/mediawiki-app/entrypoint/bootstrap-instance.sh`
- `images/mediawiki-app/extensions/LabAssistant/extension.json`

### 改工具挂载路径或站内代理

先看：

- `ops/caddy/Caddyfile.private`
- `assistant_api/app/clients/tools.py`
- `tools/rcf-web/backend/main.py`
- `tools/pytps-web/backend/main.py`

### 改部署、更新、升级、验证

先看：

- `compose.yaml`
- `compose.override.yaml`
- `ops/scripts/update.sh`
- `ops/scripts/upgrade.sh`
- `ops/scripts/validate-assistant.sh`

## Minimum Validation Matrix

| 改动类型 | 最少验证 |
| --- | --- |
| compose / caddy / 容器入口 | `docker compose config`, `bash ops/scripts/smoke-test.sh` |
| assistant API / worker / 检索 / draft | `bash ops/scripts/validate-assistant.sh --profile contract` |
| assistant reindex / embedding / job | `bash ops/scripts/validate-assistant.sh --profile full` |
| MediaWiki 启动脚本 / 种子内容 / 扩展 | `bash ops/scripts/smoke-test.sh`，必要时看 `docker compose logs mw_private mw_public` |
| 工具代理或工具接口 | `bash ops/scripts/smoke-test.sh`，再跑 assistant contract 验证 |
