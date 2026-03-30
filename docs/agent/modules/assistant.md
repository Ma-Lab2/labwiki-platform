# Assistant Module Guide

## What This Module Owns

`assistant` 模块负责：

- 问题规划与问答
- 多轮 session 上下文与流式 SSE 输出
- 站内检索与外部 OpenAlex 扩展
- 可选网页搜索扩展
- 草稿预览与提交
- wiki / zotero reindex
- prompt registry、few-shot 和领域关键词注入
- session、turn、job、draft preview、audit 的持久化

如果当前问题集中在“助手怎么理解编辑操作、什么时候出操作卡、为什么会把解释文本写进页面”，先补读：

- `docs/agent/modules/assistant-editing-semantics.md`

对应运行服务：

- `assistant_api`
- `assistant_worker`
- `assistant_store`

## Key Entry Points

### API entry

- `assistant_api/app/main.py`
  - 定义 `/chat`, `/chat/stream`, `/compare`, `/plan`, `/models/catalog`, `/capabilities`, `/actions/*`, `/tool/execute`, `/draft/*`, `/reindex/*`, `/admin/*`, `/session/{session_id}`, `/session/{session_id}/model`

### Core orchestration

- `assistant_api/app/services/orchestrator.py`
  - API 级编排、会话持久化、响应组装、SSE 事件输出
- `assistant_api/app/services/agent_loop.py`
  - 当前受控 agent loop 的核心执行器
  - 负责模型决策下一步动作、统一工具注册、工具执行、写预览/草稿预览挂接
- `assistant_api/app/services/search.py`
  - 本地 chunk 检索，当前支持关键词 + embedding 混合召回
- `assistant_api/app/services/llm.py`
  - provider facade，负责 generation / embedding / web search 三类 provider
  - generation provider 现在按请求或 session 动态解析，不再只依赖进程启动时的单一模型
  - 当 Anthropic key 存在时，默认 generation family 优先落到 Claude
- `assistant_api/app/services/model_catalog.py`
  - gptgod 模型目录分组、family/provider 推断、同族 fallback 规则、Claude-first 默认选择
- `assistant_api/app/services/capabilities.py`
  - 统一 capability/provider catalog
  - 统一 preview / commit 调度，当前承接 local knowledge、native CLI 和 future OpenCLI/MCP provider slot
- `assistant_api/app/services/prompts.py`
  - system prompt、任务 prompt、few-shot、领域关键词拼装
- `assistant_api/app/services/drafts.py`
  - 草稿预览生成
- `assistant_api/app/services/reindex.py`
  - wiki/zotero 索引重建

### External clients

- `assistant_api/app/clients/wiki.py`
  - MediaWiki 登录与编辑
- `assistant_api/app/clients/openalex.py`
  - 外部学术检索
- `assistant_api/app/clients/tools.py`
  - 受控调用 TPS / RCF
- `assistant_api/app/providers/`
  - generation / embedding / web search provider 抽象与具体实现

### Persistence

- `assistant_api/app/models.py`
  - SQLAlchemy 模型
- `assistant_api/app/db.py`
  - 初始化和 session 管理
- `assistant_api/postgres/init/01-extensions.sql`
  - pgvector 扩展初始化

### Worker

- `assistant_api/app/worker.py`
  - 轮询 `pending` job，执行 `reindex_wiki` / `reindex_zotero`

### CLI entry

- `assistant_api/app/assistantctl.py`
  - 本地 CLI 客户端，当前主打学生语义命令：`ask`、`draft`、`stream`、`session show`、`confirm`
  - 默认 base URL 走 `http://localhost:8443/tools/assistant/api`，与本机私有站前门保持一致
- `ops/scripts/assistantctl.sh`
  - 通过项目专用 Python 3.12 环境运行 `assistantctl`

## Current Runtime Contracts

### Assistant API

当前稳定接口在 `assistant_api/app/main.py`：

- `GET /health`
- `POST /chat`
- `POST /chat/stream`
- `POST /compare`
- `POST /plan`
- `GET /models/catalog`
- `GET /capabilities`
- `POST /actions/preview`
- `POST /actions/commit`
- `POST /tool/execute`
- `POST /draft/preview`
- `POST /draft/commit`
- `POST /write/preview`
- `POST /write/commit`
- `POST /reindex/wiki`
- `POST /reindex/zotero`
- `GET /admin/jobs/{job_id}`
- `GET /admin/stats`
- `GET /admin/index/stats`
- `GET /session/{session_id}`
- `PATCH /session/{session_id}/model`

### Model and retrieval config

主配置在 `compose.yaml` 的 `assistant_api` / `assistant_worker` 环境变量。注意 generation 默认值仍来自环境变量，但运行时会被 session 级选择覆盖；当 Anthropic key 存在时，默认 generation family 会优先切到 Claude：

- Generation provider:
  - `ASSISTANT_GENERATION_PROVIDER`
- Anthropic generation:
  - `ASSISTANT_ANTHROPIC_BASE_URL`
  - `ASSISTANT_ANTHROPIC_API_KEY`
  - `ASSISTANT_ANTHROPIC_MODEL`
- OpenAI generation:
  - `ASSISTANT_OPENAI_BASE_URL`
  - `ASSISTANT_OPENAI_API_KEY`
  - `ASSISTANT_OPENAI_MODEL`
- OpenAI-compatible / domestic generation:
  - `ASSISTANT_OPENAI_COMPATIBLE_BASE_URL`
  - `ASSISTANT_OPENAI_COMPATIBLE_API_KEY`
  - `ASSISTANT_OPENAI_COMPATIBLE_MODEL`
- Embedding:
  - `ASSISTANT_EMBEDDING_BASE_URL`
  - `ASSISTANT_EMBEDDING_API_KEY`
  - `ASSISTANT_EMBEDDING_MODEL`
  - `ASSISTANT_EMBEDDING_DIMENSIONS`
- Web search:
  - `ASSISTANT_ENABLE_WEB_SEARCH`
  - `ASSISTANT_WEB_SEARCH_PROVIDER`
  - `ASSISTANT_OPENAI_WEB_SEARCH_MODEL`
  - `ASSISTANT_TAVILY_API_KEY`
- Wiki access:
  - `ASSISTANT_WIKI_URL`
  - `ASSISTANT_WIKI_USER`
  - `ASSISTANT_WIKI_PASSWORD_FILE`
- Tool access:
  - `ASSISTANT_TPS_BASE_URL`
  - `ASSISTANT_RCF_BASE_URL`
- Multi-turn history:
  - `ASSISTANT_CONVERSATION_HISTORY_TURNS`

### Frontend bridge

- MediaWiki assistant UI:
  - `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`
  - `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.css`
  - `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell.js`
  - `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.pdf-reader-utils.js`
- Special page entry:
  - `images/mediawiki-app/extensions/LabAssistant/includes/SpecialLabAssistant.php`
- Reverse proxy path:
  - `ops/caddy/Caddyfile.private`
  - `ops/caddy/Caddyfile.private.local`

当前网页前端通过 `/tools/assistant/api/chat/stream` 消费 SSE，使用 localStorage 保存 `session_id`，再通过 `/session/{session_id}` 恢复当前会话。
当前网页前端还会通过 `/tools/assistant/api/models/catalog` 加载分组模型目录，并用 `/tools/assistant/api/session/{session_id}/model` 持久化当前会话的 generation model。
`/session/{session_id}` 现在不只返回问题摘要，而是返回每轮 turn 的 `step_stream`、`sources`、`action_trace`、`draft_preview`、`write_preview`、`write_result` 和 `model_info`，供前端恢复最近一次完整结果面板。
当前 capability/action 层也已经暴露给外部入口：网页端和 CLI 都可以通过 `/capabilities` 查看 provider/capability 目录，再通过 `/actions/preview` 和 `/actions/commit` 走统一 preview/commit 语义。
当前文献导读页已经接入两条 PDF 阅读链：
- 正式 Wiki PDF：`Template:文献导读` 渲染 `.labassistant-pdf-reader-source`，由 `ext.labassistant.shell.js` 挂载页内阅读器
- 助手临时 PDF：附件 chip 里的“阅读”动作打开浮动阅读器，内容流走 `/tools/assistant/api/attachments/{attachment_id}/content`
当前抽屉版网页体验按“普通学生整理助手”优化：
- 默认围绕当前页整理词条、知识页、shot 和周实验日志草稿
- 显式 `问答/草稿` 模式按钮不再作为主路径
- `action_trace` / 工具痕迹在抽屉版默认弱化，更多保留给高级页
当前本地部署对私有站只保留一个用户入口：
- `http://localhost:8443` 作为本机浏览器与 CLI 的唯一 canonical 入口
- `http://127.0.0.1:8443` 与其他非 canonical host 应视为 transport-level 端点，并重定向回 `localhost`
assistant 前端仍按 host 作用域隔离本地会话状态，因此私有站相关脚本、书签和回归检查都应固定使用 `localhost:8443`。

## Non-Negotiable Constraints

- 当前 assistant 不再是单一固定工作流，而是“受控 agent loop + 白名单工具”。
- generation model 允许 session 级切换，但 embedding model 和 web search provider 仍是全局配置；不要假设切换 generation 会影响 reindex 或 embedding。
- 允许模型决定下一步调用哪个工具，但不允许它发明新工具、跳过提交确认或直接写入任意页面。
- `/draft/commit` 是唯一允许真正写入 wiki 草稿的 assistant API 路径。
- `/write/commit` 只能提交已经生成的写操作预览，不能接受自由文本直接写入。
- `draft_prefix` 必须持续限制草稿写入范围，不能让任意页面标题被提交。
- `ASSISTANT_EMBEDDING_DIMENSIONS` 必须和数据库向量列一致；切换到新维度前必须先迁移再 reindex。
- `ASSISTANT_ENABLE_ZOTERO=false` 时，`/reindex/zotero` 应返回 `disabled`，而不是抛异常。
- OpenAlex 学术检索不应被 `ASSISTANT_ENABLE_WEB_SEARCH` 一起关掉；网页搜索只是补充源，不是外部检索总开关。
- `POST /chat/stream` 的 SSE 事件名必须保持稳定：`session_started`、`step`、`token`、`sources`、`action_trace`、`draft_preview`、`write_preview`、`write_result`、`done`、`error`。
- `ChatResponse.model_info` 和 `/session/{session_id}` 的 `model_info` 是当前前端模型恢复逻辑的依赖字段；改名或改结构时必须同步 JS。
- `action_trace`、`write_preview`、`write_result` 不只是 `/chat` 返回字段，也是当前 session 恢复和前端历史回放的一部分；如果只改运行态不改 `/session/{session_id}`，刷新后行为会回退。
- 抽屉版主体验默认面向普通学生；不要把 provider/capability/工具栏重新推回前台。
- `/capabilities`、`/actions/preview`、`/actions/commit` 是当前统一 capability 协议的外部入口；扩新工具时优先加 provider/capability，不要再平行长出新的特例路由。
- OpenCLI 当前在本地环境里只是 provider slot；如果机器上没装 `opencli`，目录里应表现为 `available=false`，不要伪装成已接通。
- 外部 provider 的写动作必须先 preview 再 commit；不要让 OpenCLI/MCP/native CLI 绕过 approval 语义直接 side effect。
- 私有站本机入口如果出现 host/cookie/redirect 异常，先修浏览器入口与 Caddy/MediaWiki host 协调，再怀疑 assistant session 恢复或浏览器缓存。
- `assistant_api/app/clients/tools.py` 当前只允许受控只读动作；新增动作前要同时评估工具侧安全边界。
- 当前向量检索通过 `assistant_api/app/services/vector_store.py` 走后端抽象；不要再把 pgvector SQL 直接塞回 agent loop 或 UI 逻辑里。
- 当前已实现两个向量后端名字：`pgvector` 和 `qdrant_local`。生产默认仍是 `pgvector`；`qdrant_local` 主要用于 benchmark 和候选对比。
- `assistant_api/app/services/retrieval_benchmark.py` 的输出现在不只是逐行结果，还包含 `summary`、`category_summary`、`leaderboard` 和 `misses`；新增 benchmark 结论时优先更新 case 集和报告，不要只凭感觉改默认策略。
- 学生视角综合评测现在单独走：
  - `assistant_api/app/benchmarks/student_eval_cases.json`
  - `assistant_api/app/services/student_eval_report.py`
  - `ops/scripts/build-assistant-student-eval-report.sh`
- PDF 阅读模块现在有独立浏览器回归：
  - `ops/scripts/playwright-private-pdf-reader-check.sh`
  - 覆盖文献导读页空状态、正式 PDF 内嵌阅读器、助手临时 PDF 浮动阅读器，以及“发送摘录到助手”
- 这套评测不是自动问答回放器，而是“人工打分 + 自动聚合报告”：
  - case 集定义学生真实问题和期望行为
  - CSV 打分表记录五维评分、惩罚项、失败标签和优化建议
  - 汇总脚本输出 JSON/Markdown 报告，用于统计高频失败模式和下一轮优化优先级

## Common Change Scenarios

### 改问答路由或回答结构

先改：

- `assistant_api/app/services/orchestrator.py`
- `assistant_api/app/services/agent_loop.py`
- `assistant_api/app/services/prompts.py`
- 如涉及模型切换或 fallback，再改：
  - `assistant_api/app/services/model_catalog.py`
  - `assistant_api/app/services/llm.py`
- 如涉及统一 capability/action 行为，再改：
  - `assistant_api/app/services/capabilities.py`
  - `assistant_api/app/assistantctl.py`
- 必要时同步 `assistant_api/app/schemas.py`
- 如果改流式行为，还要同步：
  - `assistant_api/app/main.py`
  - `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`

然后验证：

- `bash ops/scripts/validate-assistant.sh --profile chat`
- `bash ops/scripts/assistantctl.sh tools list`

### 改 embedding / reindex 逻辑

先改：

- `assistant_api/app/services/reindex.py`
- `assistant_api/app/services/llm.py`
- `assistant_api/app/services/search.py`
- `assistant_api/app/services/vector_store.py`
- `assistant_api/app/services/retrieval_benchmark.py`
- 必要时同步 `assistant_api/app/models.py`
- 如果要比较不同 tokenization / normalization / strategy / vector backend：
  - `assistant_api/app/benchmarks/retrieval_cases.json`
  - `ops/scripts/benchmark-assistant-retrieval.sh`
  - `assistant_api/app/services/retrieval_benchmark.py`

然后验证：

- `bash ops/scripts/validate-assistant.sh --profile full`

### 改工具调用能力

先改：

- `assistant_api/app/services/agent_loop.py`
- `assistant_api/app/clients/tools.py`
- 相关工具服务路由

然后验证：

- `bash ops/scripts/smoke-test.sh`
- `bash ops/scripts/validate-assistant.sh --profile contract`

## Minimum Validation

本地 assistant 开发、单测、报告生成统一走专用 conda Python 3.12 环境，不要混用宿主机上的 Linuxbrew `python3`、conda base `python` 或系统 Python。先执行：

```bash
bash ops/scripts/assistant-python.sh --ensure
bash ops/scripts/assistant-python.sh --doctor
```

然后再跑本地验证：

```bash
bash ops/scripts/assistant-python.sh -m compileall assistant_api/app
bash ops/scripts/assistant-python.sh --cwd assistant_api -m unittest discover -s tests -v
bash ops/scripts/validate-assistant.sh --profile contract
```

涉及多轮对话、SSE、session 恢复时：

```bash
bash ops/scripts/validate-assistant.sh --profile chat
```

涉及 reindex、embedding、job 状态时：

```bash
bash ops/scripts/validate-assistant.sh --profile full
```

如果需要单独重建索引：

```bash
bash ops/scripts/reindex-assistant.sh wiki --wait --timeout 1200
bash ops/scripts/reindex-assistant.sh zotero --wait --timeout 1200
bash ops/scripts/benchmark-assistant-retrieval.sh --output backups/validation/retrieval-benchmark.json
bash ops/scripts/build-assistant-student-eval-report.sh --template-output backups/validation/student-eval-template.csv
bash ops/scripts/build-assistant-student-eval-report.sh --scores backups/validation/student-eval-scores.csv --json-output backups/validation/student-eval-report.json --markdown-output backups/validation/student-eval-report.md
bash ops/scripts/playwright-private-session-check.sh
bash ops/scripts/playwright-private-shot-fill-check.sh
```

当前参考报告：

- `backups/validation/retrieval-benchmark-v2.json`

学生评测的固定评分字段：

- 五维：`task_completion`、`lab_context_fit`、`current_page_use`、`structure_usability`、`boundary_honesty`
- 惩罚：`penalty_off_topic`、`penalty_index_as_answer`
- 高频失败标签优先用这些枚举，不要临时造词：
  - `ignored_current_page`
  - `answered_retrieval_instead_of_task`
  - `too_generic`
  - `wrong_task_type`
  - `bad_structure`
  - `missing_write_preview`
  - `unsafe_write_assumption`
  - `insufficient_grounding`
  - `overexplained_process`
  - `wrong_source_priority`

当前已验证的经验结论：

- 当前扩展到 19 条 case 后，`mixed + basic + hybrid` 的平均排序最好
- 默认主链路继续使用 `hybrid`
- `pgvector` 与 `qdrant_local` 在当前扩展 case 集上基本打平，因此生产默认先不切换后端

## Failure Triage

- `/chat` 500：先看 `assistant_api/app/main.py` 是否捕获到下游异常，再看 `docker compose logs assistant_api`
- SSE 页面无输出：先测 `POST /chat/stream`，再测 `http://caddy_private/tools/assistant/api/chat/stream`，最后看 `ext.labassistant.ui.js`
- job 卡住：看 `docker compose logs assistant_worker`，再查 `/admin/jobs/{job_id}`
- 向量写不进去：优先检查 `ASSISTANT_EMBEDDING_DIMENSIONS` 与库表维度是否一致
- 草稿提交失败：优先看 `ASSISTANT_WIKI_URL`、wiki 登录信息、草稿前缀和私有站可达性
