# MediaWiki Module Guide

## What This Module Owns

这个模块负责双 wiki 的镜像、启动、运行时配置和基础内容种子：

- `mw_public`
- `mw_private`
- `images/mediawiki-app/`

两个站共用同一镜像，但通过环境变量和启动脚本区分公开/私有行为。

## Key Entry Points

### Image and runtime bootstrap

- `images/mediawiki-app/Dockerfile`
  - 构建 MediaWiki 运行镜像和 Caddy 运行镜像
- `images/mediawiki-app/entrypoint/bootstrap-instance.sh`
  - 运行时检查环境变量
  - 安装或升级 MediaWiki
  - 以 managed blocks 的方式维护 `LocalSettings.php`
  - 导入种子页面和私有站图片
  - 重建私有站 Cargo 表

### Extension and UI entry

- `images/mediawiki-app/extensions/LabAssistant/extension.json`
  - 定义 `Special:LabAssistant`
  - 定义 `Special:LabAssistantAdmin`
  - 定义前端 ResourceModules

### Seed content

- `images/mediawiki-app/seed/public-manifest.tsv`
- `images/mediawiki-app/seed/private-manifest.tsv`
- `images/mediawiki-app/seed/private-cargo-manifest.tsv`

这些 manifest 决定初始页面和私有站 Cargo 相关内容的导入范围。

## Runtime Behavior

### Public vs private

`compose.yaml` 通过环境变量区分：

- `mw_public`
  - `MW_PRIVATE_MODE=false`
  - `MW_SERVER=https://${PUBLIC_HOST}`
- `mw_private`
  - `MW_PRIVATE_MODE=true`
  - 额外挂 `MW_ASSISTANT_API_BASE`
  - 额外挂 `MW_ASSISTANT_DRAFT_PREFIX`

### Private wiki hardening

`bootstrap-instance.sh` 在私有站模式下会写入：

- 禁止匿名读写
- 加载 `LabAssistant` 扩展
- 注入 assistant API base 和 draft prefix

### Managed LocalSettings

`bootstrap-instance.sh` 通过 `upsert_managed_block()` 写入：

- `LABWIKI_COMMON`
- `LABWIKI_EDITOR_EXTENSIONS_V3`
- `LABWIKI_THEME_V1`
- `LABWIKI_RUNTIME_OVERRIDES_V5`
- 私有站额外的 `PRIVATE_WIKI_HARDENING_V2`

这意味着：

- 优先改启动脚本和环境变量
- 不要把手工补丁直接打在 `state/public/LocalSettings.php` 或 `state/private/LocalSettings.php`

## Non-Negotiable Constraints

- 双 wiki 分离是架构前提，不要把公开/私有权限逻辑合并回单实例。
- `LocalSettings.php` 是持久化产物，但其受管部分应视为由 `bootstrap-instance.sh` 生成。
- 私有站 assistant 入口依赖 `LabAssistant` 扩展和 `MW_ASSISTANT_*` 环境变量；改其中一边要同步验证另一边。
- 私有站 Cargo 表重建只在 bootstrap 中做一次性流程，依赖 marker 文件；不要随意删除 marker 除非你明确要重跑初始化。

## Common Change Scenarios

### 改 wiki 默认配置

先改：

- `images/mediawiki-app/entrypoint/bootstrap-instance.sh`

不要先改：

- `state/**/LocalSettings.php`

### 改私有站 assistant 入口

先改：

- `images/mediawiki-app/extensions/LabAssistant/extension.json`
- 必要时对应的 `includes/` 或 `modules/` 目录
- 如果 API base 或 draft prefix 变了，再同步 `bootstrap-instance.sh`

### 改默认页面或种子知识

先改：

- `images/mediawiki-app/seed/`
- 对应 manifest `.tsv`

### 改主题或站点前端资源

先改：

- `images/mediawiki-app/theme/base.css`
- `images/mediawiki-app/theme/public.css`
- `images/mediawiki-app/theme/private.css`
- 对应 logo/js

## Minimum Validation

```bash
docker compose config
bash ops/scripts/smoke-test.sh
docker compose logs mw_public mw_private --tail=100
```

如果改了私有 assistant 入口，再补：

```bash
bash ops/scripts/validate-assistant.sh --profile contract
```

## Failure Triage

- `LocalSettings.php` 没生成：先看 `bootstrap-instance.sh` 所需环境变量和 secrets 文件
- 私有站打不开 assistant：先查 `LabAssistant` 是否被加载，再查 `/tools/assistant/api` 代理路径
- 种子页没导入：先看 manifest 和 marker 逻辑，再看 `docker compose logs mw_private`
