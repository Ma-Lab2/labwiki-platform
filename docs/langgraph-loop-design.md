# LangGraph Loop 设计说明

本文档用于锁定知识助手 v1 的单主智能体 loop 结构，作为 `assistant_api` 后续从手写编排迁移到 `LangGraph` 的实现基线。

## 1. 设计目标

该 loop 只解决 v1 必需能力：

1. 理解用户问题与上下文；
2. 决定优先查站内还是文献；
3. 聚合证据并生成带来源回答；
4. 在需要时生成草稿预览；
5. 所有写入动作都经过显式确认。

本 loop 不承担：

- 多智能体协作
- 自动发布正式页面
- 无上限自主检索
- 长期个性化记忆

## 2. 总体流程

固定主流程如下：

```text
intake
  -> classify
  -> plan
  -> retrieve_local
  -> retrieve_tools (可选)
  -> retrieve_external (按需循环)
  -> synthesize
  -> verify
  -> draft_preview (按需)
  -> commit_gate (人工确认)
  -> finalize
```

其中：

- `retrieve_external` 不是默认必走，只在文献/对照类问题且本地证据不足时触发；
- `draft_preview` 只有在 `mode=draft` 或任务被识别为条目生成时触发；
- `commit_gate` 不由模型自动通过，必须由用户确认。

## 3. 统一状态模型

LangGraph 的 state 统一固定为以下字段：

- `session_id`
- `turn_id`
- `user_name`
- `question`
- `mode`
- `detail_level`
- `context_pages`
- `task_type`
- `planned_sources`
- `steps`
- `evidence`
- `external_attempts`
- `tool_calls`
- `unresolved_gaps`
- `confidence`
- `answer`
- `draft_preview`
- `pending_write_action`
- `stop_reason`

字段约束：

- `steps` 用于前端步骤流展示；
- `evidence` 中每项都至少包含 `source_type / source_id / title / snippet / url`；
- `pending_write_action` 只在草稿确认阶段出现；
- `stop_reason` 必须显式记录，不允许“无原因结束”。

## 4. 节点定义

### 4.1 intake

输入：

- 用户问题
- 当前页面
- 用户名
- 模式
- 解释层级

输出：

- 初始化 session / turn
- 记录第一条步骤流

### 4.2 classify

职责：

- 判定任务类型：`concept / compare / literature / learning_path / tool_workflow / draft`

输出：

- `task_type`
- 分类说明写入 `steps`

### 4.3 plan

职责：

- 根据 `task_type` 生成检索计划

固定规则：

- 默认优先级：`cargo -> wiki`
- `compare / literature`：追加 `zotero / pdf / external`
- `tool_workflow`：追加 `tools`
- `draft`：仍先走检索，再决定是否进入草稿预览

输出：

- `planned_sources`
- `needs_external_search`

### 4.4 retrieve_local

职责：

- 读取当前上下文页
- 查询 Cargo
- 查询 Wiki chunk / 页面索引

输出：

- 把本地证据写入 `evidence`
- 更新 `steps`

约束：

- 这是默认必经节点；
- 本节点只允许只读操作。

### 4.5 retrieve_tools

触发条件：

- `task_type == tool_workflow`

职责：

- 读取 TPS / RCF 等受控工具的只读结果或健康状态

约束：

- 只允许 `read_only` 工具动作；
- 不允许改工具配置、不允许删数据、不允许触发破坏性执行。

输出：

- 工具返回信息写入 `evidence`
- 记录到 `tool_calls`

### 4.6 retrieve_external

触发条件：

- 当前问题属于 `compare / literature`
- 本地证据仍不足
- `external_attempts < loop_max_external`

职责：

- 查询外部学术源、Zotero 快照、PDF 索引

停止规则：

- 连续一次外部扩搜没有新增有效证据，则停止继续扩搜；
- 总扩搜次数不超过 `loop_max_external`；
- 不允许无限 while loop。

### 4.7 synthesize

职责：

- 用当前 `evidence` 生成回答

要求：

- 回答必须显式带证据边界；
- 不能把通用外部知识说成“本组共识”；
- 如果证据不足，优先返回缺口，而不是编造完整判断。

输出：

- `answer`

### 4.8 verify

职责：

- 检查证据覆盖、来源多样性、缺口、置信度

输出：

- `unresolved_gaps`
- `confidence`
- `stop_reason`

固定停止条件：

1. `confidence >= threshold` 且没有关键缺口；
2. 达到 `loop_max_steps`；
3. 外部扩搜无新增证据；
4. 任务转入 `draft_preview`；
5. 需要人工确认。

### 4.9 draft_preview

触发条件：

- `mode == draft` 或任务类型为 `draft`

职责：

- 基于 `answer + sources` 生成 Wiki 草稿预览

输出：

- `draft_preview`
- `pending_write_action`

约束：

- 这里只生成预览，不写入 Wiki。

### 4.10 commit_gate

职责：

- 等待用户确认是否提交草稿

固定策略：

- 未确认：结束本轮并返回预览
- 已确认：调用写入接口，写到草稿空间

约束：

- 该节点不允许由模型自动通过；
- 必须由前端或 API 显式传入确认动作。

### 4.11 finalize

职责：

- 输出标准 `ChatResponse`

固定输出：

- `answer`
- `step_stream`
- `sources`
- `confidence`
- `unresolved_gaps`
- `suggested_followups`
- `draft_preview`

## 5. 工具调用策略

工具分 3 类：

### 5.1 read_only

- Cargo 查询
- Wiki 页面读取
- Zotero / PDF 检索
- OpenAlex / 外部学术源
- TPS / RCF 状态或结果读取

这类工具允许 loop 自动调用。

### 5.2 draft_only

- 草稿预览生成
- 模板字段预填

这类工具允许自动执行，但不能直接写回 Wiki。

### 5.3 write_action

- 提交草稿页
- 触发重建索引
- 未来可能的工具缓存刷新

这类工具必须经过 `commit_gate`。

## 6. 失败与降级规则

### 6.1 检索失败

- 本地检索失败：仍返回问题分类和缺口说明
- 外部检索失败：记录为步骤流错误，但不让整轮崩溃

### 6.2 模型失败

- 主模型失败：切一次降级模型
- 降级模型仍失败：返回结构化错误和已有证据，不继续无限重试

### 6.3 工具失败

- 工具调用失败写入 `tool_calls`
- 回答中显式说明工具不可用
- 不因为单工具失败终止整轮

## 7. 与现有 assistant_api 的映射

当前 `assistant_api/app/services/orchestrator.py` 中已有的逻辑可直接映射到未来节点：

- `classify_question()` -> `classify`
- `build_plan()` -> `plan`
- `search_chunks()` + `wiki.search_pages()` -> `retrieve_local`
- `tools.tps_execute()` / `tools.rcf_execute()` -> `retrieve_tools`
- `openalex.search()` -> `retrieve_external`
- `llm.answer_from_evidence()` -> `synthesize`
- `_gaps_for_answer()` + `_confidence_for_answer()` -> `verify`
- `create_draft_preview()` -> `draft_preview`

因此，后续迁移应优先做“把现有函数包成节点”，而不是推倒重写。

## 8. 实现时必须守住的约束

1. loop 必须有硬上限；
2. 任何写入动作都必须经过人工确认；
3. 回答必须显式输出缺口与证据边界；
4. 工具层默认只读；
5. 当前页面上下文优先于泛化外部知识；
6. 站内结构化实体优先于自由文本；
7. 前端步骤流必须能映射到实际节点，而不是虚假进度文案。

## 9. 最小验收场景

1. 问一个概念问题，只走 `local retrieval`，不触发外部扩搜；
2. 问一个文献对照问题，在本地不足时触发一次外部扩搜；
3. 问一个 TPS/RCF 工具问题，能够读取工具结果但不改配置；
4. 问一个草稿生成问题，能返回预览但不会自动写页；
5. 用户确认后，草稿才真正进入 Wiki 草稿空间；
6. 任意失败场景下，步骤流中都能看到失败点和停止原因。
