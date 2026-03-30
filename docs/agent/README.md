# Coding Agent Maintenance Guide

本目录面向接手本仓库的 coding agent 和维护工程师。目标不是重复产品背景，而是快速回答：

- 这个仓库的核心服务有哪些
- 改某类需求时应该先看哪里
- 哪些边界不能破坏
- 改完应该跑哪些验证

先读顺序：

1. `docs/agent/system-overview.md`
2. 对应模块手册
3. 需要设计背景时，再回看 `docs/assistant-architecture-decision.md` 和 `docs/assistant-api-design.md`

## Fast Routing

| 任务类型 | 先读文档 |
| --- | --- |
| 改 assistant API、检索、模型配置、reindex、草稿提交 | `docs/agent/modules/assistant.md` |
| 改知识助手的页面编辑、区块写入、操作卡、源码 handoff | `docs/agent/modules/assistant-editing-semantics.md` |
| 改 MediaWiki 启动、私有站行为、扩展入口、种子内容 | `docs/agent/modules/mediawiki.md` |
| 改 RCF/TPS 工具接入、代理路径、只读动作边界 | `docs/agent/modules/tools.md` |
| 改 compose、Caddy、更新/升级脚本、验证脚本、内网部署 | `docs/agent/modules/ops-and-validation.md` |

## Current System Map

| 层 | 主要服务/目录 | 作用 |
| --- | --- | --- |
| 入口与反代 | `caddy_public`, `caddy_private`, `ops/caddy/` | 暴露公开站、私有站和工具代理路径 |
| Wiki 主体 | `mw_public`, `mw_private`, `images/mediawiki-app/` | 运行两个 MediaWiki 站点，并通过启动脚本固化配置 |
| 智能助手 | `assistant_api`, `assistant_worker`, `assistant_store`, `assistant_api/app/` | 问答、草稿预览、索引、任务状态、审计 |
| 工具服务 | `tools/rcf-web/`, `tools/pytps-web/` | 私有站挂载的实验工具 |
| 运维与验证 | `ops/scripts/` | backup / restore / update / upgrade / smoke / validation / reindex |

## High-Risk Rules

- `state/**/LocalSettings.php` 是运行时持久化产物，默认不要手工改；优先改 `bootstrap-instance.sh` 或环境变量。
- `compose.override.yaml` 只用于本地/内网模式，生产脚本默认不会自动加载，除非设置 `LABWIKI_LOCAL_OVERRIDE=true`。
- `assistant_document_chunks.embedding` 维度必须与 `ASSISTANT_EMBEDDING_DIMENSIONS` 一致；换 embedding 模型不一定只是改变量名。
- `/draft/commit` 是 assistant 唯一允许写 wiki 草稿的入口；主问答链路不应绕过它直接写页。
- `assistant` 对工具的调用默认是受控只读；如果开放写操作，需要同时修改 `assistant_api` 客户端限制和工具服务本身的安全边界。

## Change Checklist

改动前先确认：

- 这次修改属于哪个模块
- 有没有涉及 `compose.yaml`、环境变量或反向代理路径
- 有没有涉及持久化状态目录或数据库维度

改动后至少执行：

- `docker compose config`
- 对应模块手册里的最小验证命令
- 如果改了运维链路，执行 `bash ops/scripts/smoke-test.sh`
- 如果改了 assistant 链路，执行 `bash ops/scripts/validate-assistant.sh --profile contract`

## Related Docs

- 仓库规则：`AGENTS.md`
- 部署入口：`README.md`
- 助手架构决策：`docs/assistant-architecture-decision.md`
- 助手 API 设计：`docs/assistant-api-design.md`
- 助手编辑语义：`docs/agent/modules/assistant-editing-semantics.md`
- LangGraph loop 设计：`docs/langgraph-loop-design.md`
