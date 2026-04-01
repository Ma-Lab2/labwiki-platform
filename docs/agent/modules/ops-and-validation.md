# Ops And Validation Guide

## What This Module Owns

本手册覆盖：

- Docker Compose 编排
- 本地 override / 校园内网模式
- Caddy 配置
- backup / restore / update / upgrade
- smoke / assistant validation / report artifacts

## Key Entry Points

### Compose

- `compose.yaml`
  - 生产和默认真相源
- `compose.override.yaml`
  - 本地/内网模式差异
  - 只有设置 `LABWIKI_LOCAL_OVERRIDE=true` 时，运维脚本才会显式带上它

### Reverse proxy

- `ops/caddy/Caddyfile.public`
- `ops/caddy/Caddyfile.private`
- `ops/caddy/Caddyfile.public.local`
- `ops/caddy/Caddyfile.private.local`

### Ops scripts

- `ops/scripts/backup.sh`
- `ops/scripts/restore.sh`
- `ops/scripts/update.sh`
- `ops/scripts/upgrade.sh`
- `ops/scripts/smoke-test.sh`
- `ops/scripts/validate-assistant.sh`
- `ops/scripts/reindex-assistant.sh`
- `ops/scripts/migrate-assistant-embedding-dimension.sh`

## Current Operational Model

### Default deployment

- 公开站：`caddy_public` 暴露 `80/443`
- 私有站：`caddy_private` 默认绑定 `127.0.0.1:8443`
- assistant 和工具都在私有站路径下反代

### Local / campus-network mode

`compose.override.yaml` 当前会覆盖：

- `MW_SERVER`
- `ASSISTANT_WIKI_URL`
- CORS origin
- `caddy_public` / `caddy_private` 的本地 Caddyfile
- `PRIVATE_BIND_IP=0.0.0.0`

这套模式主要服务于 `Windows + WSL2 + Docker Desktop` 的实验室内网部署。

## Validation Layers

### Layer 1: smoke

- 脚本：`ops/scripts/smoke-test.sh`
- 目的：确认主要服务可达
- 当前会验证：
  - public / private wiki
  - assistant API
  - RCF UI / API
  - TPS UI / API

### Layer 2: assistant contract/chat/full

- 脚本：`ops/scripts/validate-assistant.sh`
- profile:
  - `contract`
  - `chat`
  - `full`

`full` 会额外做：

- `/reindex/wiki` 排队与轮询
- `/admin/jobs/{job_id}` 状态检查
- `/admin/index/stats` 向量维度和 wiki chunk embedding 断言

### Layer 3: update/upgrade integrated validation

- `ops/scripts/update.sh`
- `ops/scripts/upgrade.sh`

两者当前都支持：

- `--assistant-validate-profile none|contract|chat|full`
- `--assistant-report-file <path>`

如果启用 assistant 验证，默认会在 `backups/validation/` 下生成时间戳 JSON 报告。

## Non-Negotiable Constraints

- 生产脚本不要隐式吃 `compose.override.yaml`；必须通过 `LABWIKI_LOCAL_OVERRIDE=true` 显式启用。
- 任何涉及 assistant embedding 维度的改动都要同步考虑迁移脚本和 reindex。
- 验证脚本是当前主要回归手段；改脚本行为时要保持 `smoke -> validate-assistant -> update/upgrade` 这条链一致。
- `backups/`, `state/`, `uploads/`, `secrets/` 都属于高敏感或持久化目录，运维改动不能假设可随意清空。

## Common Change Scenarios

### 改服务环境变量或端口

先改：

- `compose.yaml`
- 如果是本地差异，再改 `compose.override.yaml`

然后验证：

- `docker compose config`
- `bash ops/scripts/smoke-test.sh`

### 改内网访问模式

先改：

- `compose.override.yaml`
- `ops/caddy/Caddyfile.*.local`

必要时再处理：

- Windows 端口转发
- Windows 防火墙

### 改验证链路

先改：

- `ops/scripts/smoke-test.sh`
- `ops/scripts/validate-assistant.sh`
- 必要时 `update.sh` / `upgrade.sh`

然后验证：

- `bash -n` 对应脚本
- 实际跑一轮 `smoke-test.sh`
- 实际跑一轮 `validate-assistant.sh`

## Minimum Validation

```bash
docker compose config
bash ops/scripts/smoke-test.sh
bash ops/scripts/validate-assistant.sh --profile contract
```

如果改的是 reindex、embedding 或验证脚本：

```bash
bash ops/scripts/validate-assistant.sh --profile full
```

如果改的是升级/更新路径：

```bash
bash ops/scripts/update.sh --help
bash ops/scripts/upgrade.sh --help
```

## Deployment Transfer Rule

当目标 Linux 服务器已经 `git pull` 了相同仓库版本时，不要再制作或传输整仓代码包。默认策略是：

- 在目标机本地准备 `.env`
- 在目标机本地准备 `secrets/*.txt`
- 重新构建并启动 Compose 服务

assistant 运行数据默认不迁移。只有在明确需要保留私有 wiki 学生账号、审批记录、私有页面内容时，才使用 `ops/deploy-bundle/linux-lab/` 下的私有 wiki 安全迁移脚本，而且只迁 `labwiki_private` 与 `uploads/private`。

