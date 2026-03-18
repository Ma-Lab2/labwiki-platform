# Assistant API 接口与数据流设计

本文档用于锁定知识助手 v1 的服务接口、主要数据模型和请求流，作为 `assistant_api` 的实现与后续重构基线。

它与以下文档配套：

- `docs/assistant-architecture-decision.md`
- `docs/langgraph-loop-design.md`

## 1. 服务定位

`assistant_api` 是私有知识助手的统一后端入口，负责：

- 接收来自 `Special:知识助手` 的请求；
- 驱动 LangGraph loop；
- 聚合 Wiki / Cargo / Zotero / 工具结果；
- 生成回答与草稿预览；
- 提供重建索引和管理统计接口。

它不负责：

- 渲染 MediaWiki 页面
- 直接管理用户登录态
- 直接提供独立聊天站前端

## 2. 对外接口

以下接口以当前 `assistant_api/app/main.py` 为准。

### 2.1 `GET /health`

用途：

- 存活检查

返回：

```json
{"status": "ok"}
```

### 2.2 `POST /chat`

用途：

- 主问答入口

请求体：

- `question`
- `mode`
- `detail_level`
- `session_id`
- `context_pages`
- `user_name`

返回体：

- `session_id`
- `turn_id`
- `task_type`
- `answer`
- `step_stream`
- `sources`
- `confidence`
- `unresolved_gaps`
- `suggested_followups`
- `draft_preview`

说明：

- 这是默认入口；
- 后续 LangGraph 落地后，该接口仍保持不变，只替换内部编排实现。

### 2.3 `POST /compare`

用途：

- 强制以“对照模式”进入 loop

行为：

- 与 `/chat` 共用同一编排逻辑；
- 只是把 `mode` 固定为 `compare`。

### 2.4 `POST /plan`

用途：

- 只返回问题分类与计划，不执行完整回答

返回：

- `task_type`
- `planned_sources`
- `needs_external_search`
- `will_generate_draft_preview`

适用场景：

- 前端预览步骤
- 调试 loop 计划
- 管理员查看路由决策

### 2.5 `POST /tool/execute`

用途：

- 统一工具代理入口

请求字段：

- `tool`
- `action`
- `payload`

当前支持：

- `tps`
- `rcf`

约束：

- v1 默认只用于受控工具调用；
- 在知识助手主链中，默认只允许只读动作。

### 2.6 `POST /draft/preview`

用途：

- 把回答整理成 Wiki 草稿预览

请求字段：

- `question`
- `answer`
- `mode`
- `session_id`
- `turn_id`
- `source_titles`

返回：

- `preview_id`
- `title`
- `target_page`
- `content`
- `metadata`

约束：

- 该接口不直接写页；
- 只生成预览并持久化到 `assistant_draft_previews`。

### 2.7 `POST /draft/commit`

用途：

- 用户确认后，真正提交草稿到 Wiki

请求字段：

- `preview_id`

返回：

- `status`
- `page_title`

约束：

- 该接口是唯一允许的草稿写入入口；
- 不允许主 loop 在没有确认的情况下直接调用写入。

### 2.8 `POST /reindex/wiki`

用途：

- 创建 Wiki 重建索引任务

返回：

- `job_id`
- `status`

### 2.9 `POST /reindex/zotero`

用途：

- 创建 Zotero 重建索引任务

返回：

- `job_id`
- `status`

### 2.10 `GET /admin/stats`

用途：

- 管理端查看总体状态

返回：

- `sessions_total`
- `turns_total`
- `chunks_total`
- `pending_jobs`

### 2.11 `GET /session/{session_id}`

用途：

- 查看某个 session 的历史轮次

返回：

- session 基本信息
- turns 列表

适用场景：

- 调试
- 审计
- 管理页查看对话轨迹

## 3. 统一请求与响应模型

当前 `assistant_api/app/schemas.py` 已定义以下核心模型：

### 3.1 `ChatRequest`

- `question`
- `mode`
- `detail_level`
- `session_id`
- `context_pages`
- `user_name`

### 3.2 `ChatResponse`

- `session_id`
- `turn_id`
- `task_type`
- `answer`
- `step_stream`
- `sources`
- `confidence`
- `unresolved_gaps`
- `suggested_followups`
- `draft_preview`

### 3.3 `PlanResponse`

- `task_type`
- `planned_sources`
- `needs_external_search`
- `will_generate_draft_preview`

### 3.4 `DraftPreviewPayload`

- `preview_id`
- `title`
- `target_page`
- `content`
- `metadata`

## 4. 存储模型

当前 `assistant_api/app/models.py` 已实现以下表：

### 4.1 `assistant_sessions`

作用：

- 存会话级上下文

关键字段：

- `id`
- `user_name`
- `current_page`
- `last_stage`
- `step_count`
- `confidence`

### 4.2 `assistant_turns`

作用：

- 存每轮问答记录

关键字段：

- `session_id`
- `question`
- `mode`
- `detail_level`
- `task_type`
- `answer`
- `step_stream`
- `sources`
- `unresolved_gaps`
- `suggested_followups`
- `confidence`
- `status`

### 4.3 `assistant_documents`

作用：

- 存源文档级元信息

支持来源：

- `wiki`
- `cargo`
- `zotero`
- 其他文档源

### 4.4 `assistant_document_chunks`

作用：

- 存分块文本和 embedding

关键字段：

- `document_id`
- `chunk_index`
- `heading`
- `content`
- `snippet`
- `embedding`

### 4.5 `assistant_draft_previews`

作用：

- 持久化草稿预览

关键字段：

- `session_id`
- `turn_id`
- `title`
- `target_page`
- `content`
- `metadata_json`

### 4.6 `assistant_jobs`

作用：

- 管理重建索引等后台任务

### 4.7 `assistant_audit_logs`

作用：

- 审计关键动作

v1 建议至少记录：

- tool execute
- draft preview
- draft commit
- reindex trigger

## 5. 核心数据流

### 5.1 问答主链

```text
Special:知识助手
  -> POST /chat
  -> assistant_api
  -> loop 读取 Wiki/Cargo/Zotero/工具
  -> 返回 answer + step_stream + sources
```

### 5.2 草稿链

```text
问答完成
  -> POST /draft/preview
  -> 保存 preview 到 assistant_draft_previews
  -> 前端展示预览
  -> 用户确认
  -> POST /draft/commit
  -> MediaWiki edit API 写入 Draft 页面
```

### 5.3 重建索引链

```text
管理员触发 /reindex/wiki 或 /reindex/zotero
  -> 创建 assistant_jobs 记录
  -> worker 消费任务
  -> 更新 documents / chunks / embeddings
```

## 6. 与 LangGraph loop 的映射

接口不直接暴露 LangGraph 节点，但必须保持以下语义一致：

- `/chat`：完整 loop
- `/plan`：执行到 `plan` 节点后返回
- `/draft/preview`：对应 `draft_preview`
- `/draft/commit`：对应 `commit_gate` 之后的显式写入
- `/tool/execute`：受控工具代理

因此，后续切换到 LangGraph 时，对外接口保持稳定，只替换内部节点执行方式。

## 7. 错误处理原则

### 7.1 Chat 类接口

- 如果主流程异常，返回 `HTTP 500`
- 但在 loop 内部应优先把错误转成步骤流中的失败节点，而不是整轮崩溃

### 7.2 Tool 接口

- 不支持的工具：`400`
- 工具执行异常：`500`

### 7.3 Draft 接口

- `preview_id` 不存在：`404`
- Wiki 写入失败：`500`

## 8. 实现约束

1. `/draft/commit` 必须是唯一写页入口；
2. `/tool/execute` 不允许默认暴露破坏性动作；
3. `/chat` 的响应必须始终带 `step_stream`；
4. 审计日志必须覆盖有副作用动作；
5. session 与 turn 必须可追溯；
6. 前端不应自己拼接 Wiki 写入逻辑，必须走 API。

## 9. 最小验收场景

1. 前端发起 `/chat`，能拿到回答、步骤流、来源和置信度；
2. `/plan` 能返回任务分类和计划来源；
3. `/draft/preview` 返回可展示的草稿预览；
4. `/draft/commit` 能把预览写入 Wiki 草稿页；
5. `/reindex/wiki` 和 `/reindex/zotero` 能创建 job；
6. `/session/{id}` 能回看完整历史；
7. 任一失败请求都不会绕过写入闸门。
