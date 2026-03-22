# Tools Module Guide

## What This Module Owns

当前工具模块指两套挂载到私有 wiki 下的实验工具：

- `tools/rcf-web/`
- `tools/pytps-web/`

它们都不是独立公网产品，而是通过私有站路径代理暴露给实验室用户和 assistant。

## Key Entry Points

### Private-site proxy layer

- `ops/caddy/Caddyfile.private`
- `ops/caddy/Caddyfile.private.local`

当前路径：

- `/tools/rcf/*` -> `rcf_frontend`
- `/tools/tps/*` -> `tps_web`

### RCF

- `tools/rcf-web/backend/main.py`
  - FastAPI 入口
  - 健康检查：`/api/v1/health`
  - 主要路由统一挂在 `/api/v1`
- `tools/rcf-web/frontend/`
  - Vue/Vite 前端
- `tools/rcf-web/nginx/default.conf`
  - 生产静态托管和反代入口

RCF 持久化目录：

- `state/rcf/uploaded_materials/`

### TPS

- `tools/pytps-web/backend/main.py`
  - FastAPI 入口
  - 健康检查：`/api/health`
  - 如果 `frontend/dist` 存在，会直接静态挂载 `/`
- `tools/pytps-web/frontend/`
  - Vite 前端

TPS 持久化/挂载目录：

- `state/tps/`
- `${TPS_IMAGE_DIR:-./tools-data/tps/images}` -> `/data/images`
- `tools-data/tps/output/`

## Assistant Integration Boundary

assistant 不直接 import 这两个工具的内部逻辑，而是通过 HTTP 调用，入口在：

- `assistant_api/app/clients/tools.py`

当前只允许受控动作：

- TPS: `health`, `browse`, `list`, `solve`, `batch`, `compare`
- RCF: `health`, `energy-scan`, `linear-design`, `validate-stack`

如果要新增动作，至少要同步更新：

1. 工具服务自身路由
2. `assistant_api/app/clients/tools.py`
3. assistant 相关验证

## Non-Negotiable Constraints

- 工具对 assistant 默认应保持只读或受控计算语义，不要让 agent 获得任意文件系统写权限。
- 工具的对外路径是私有站路径的一部分；改服务内部端口或前缀时，必须同步改 Caddy 和 assistant client。
- `TPS_IMAGE_DIR` 可能指向实验室真实数据目录；任何批量操作都要假设该目录不可写。

## Common Change Scenarios

### 改工具 API

先改：

- 对应 `backend/main.py` 及其路由模块

再同步：

- `assistant_api/app/clients/tools.py`
- 必要时前端调用路径

### 改工具挂载路径

先改：

- `ops/caddy/Caddyfile.private`
- `ops/caddy/Caddyfile.private.local`

然后同步：

- MediaWiki 页面中的入口链接
- assistant 的工具调用基地址或前端入口文案

### 改工具卷挂载或数据目录

先改：

- `compose.yaml`
- 必要时 `.env` / `compose.override.yaml`

## Minimum Validation

```bash
bash ops/scripts/smoke-test.sh
bash ops/scripts/validate-assistant.sh --profile contract
```

需要直接验证服务时：

```bash
docker compose logs rcf_backend rcf_frontend tps_web --tail=100
```

## Failure Triage

- RCF 页面空白：先看 `rcf_frontend` 是否健康，再看 nginx 配置和 `/api/v1/health`
- TPS 页面正常但 assistant 调不通：先看 `assistant_api/app/clients/tools.py` 的 action 和 base URL
- 本地能开、局域网别人打不开：先查 `compose.override.yaml`、Windows 端口转发和防火墙
