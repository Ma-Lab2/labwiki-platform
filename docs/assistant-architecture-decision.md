# MediaWiki 知识库智能助手技术架构决策

本文档用于锁定 v1 的核心技术路线，避免后续在“产品壳、RAG、Agent、工具接入”之间反复摇摆。

## 1. 目标系统边界

v1 不是通用聊天站，也不是多智能体自治系统。
v1 的本质是一个嵌入 `private wiki` 的领域知识助手，负责四件事：

1. 读取并检索站内知识；
2. 联动 Zotero / PDF / 术语表等外部知识源；
3. 以可追溯证据回答问题；
4. 把结果生成到 Wiki 草稿，而不是自动发布正式内容。

## 2. 最终技术分层

### 2.1 MediaWiki 入口层

- 技术：`PHP + MediaWiki Extension`
- 作用：
  - 提供 `Special:知识助手`
  - 感知当前用户、页面、权限
  - 提供草稿写回入口
- 不承担：
  - 多步编排
  - 检索聚合
  - 模型调用

### 2.2 智能编排层

- 技术：`Python + FastAPI + LangGraph`
- 作用：
  - 问题分类
  - 多源检索编排
  - 工具调用
  - loop 状态管理
  - stop / retry / human gate
  - 草稿预览生成
- 这是本项目的主逻辑层。

### 2.3 检索与状态层

- 技术：`PostgreSQL + pgvector`
- 作用：
  - chunk、embedding、检索缓存
  - session state
  - tool trace
  - 审计日志
- 不复用 MediaWiki 的 MariaDB 做这一层。

### 2.4 工具与知识源层

- Wiki 页面与 Cargo 字段
- Zotero 快照 / PDF / 笔记
- 术语表与模板
- 后续可接 TPS / RCF / 代码仓库

## 3. 为什么主编排选 LangGraph

`LangGraph` 是 v1 的主智能体架构参考，原因如下：

- 它适合**有状态 agent loop**，而不是单轮 prompt orchestration。
- 它天然适合把流程拆成节点：`classify -> retrieve -> synthesize -> verify -> commit gate`。
- 它支持**中断、恢复、重试、人工确认**，这正是本项目“草稿先预览、人工后提交”的核心要求。
- 它比纯 prompt chain 更适合审计和可视化步骤流。

本项目需要的是**单主智能体 + 可控工具流 + 写入闸门**，LangGraph 正好匹配。

## 4. 为什么不把这些项目当主骨架

### 4.1 beaver-zotero

- 可借：side-panel、阅读上下文、引用体验、library-first 检索
- 不借：后端主架构
- 原因：其开源部分主要是 `TypeScript + React` 插件端，README 明确说明后端与文件处理不开放

结论：它是**产品形态参考**，不是主 Agent 架构参考。

### 4.2 paper-qa

- 可借：文献证据链、引用式回答、文献优先问答
- 不借：完整系统架构

结论：它是**文献问答内核参考**，不是完整产品或编排框架。

### 4.3 zotero-mcp

- 可借：把 Zotero 抽象成工具层接口
- 不借：产品壳与主流程

结论：它是**工具接入参考**。

### 4.4 Dify

- 优点：产品化快、工作流 UI 完整、适合原型
- 问题：
  - 更偏平台型产品，而不是深度贴合 MediaWiki 的私有知识助手
  - loop 可控性、细粒度写入闸门、研究语境下的定制度不如自建编排层

结论：可借鉴产品化经验，但不作为 v1 主骨架。

### 4.5 Open WebUI

- 优点：聊天 UI、知识库、模型接入成熟
- 问题：
  - 更像独立 AI 入口站
  - 不适合成为 MediaWiki 内嵌、强知识结构耦合的主壳

结论：可参考 UI 模块化方式，不作为主架构。

### 4.6 AutoGen / CrewAI

- 优点：适合多角色协作和多 agent 实验
- 问题：
  - 对本项目 v1 偏重
  - 会过早引入多 agent 协调复杂度
  - 不利于先把“单主智能体 + 证据链 + 草稿闸门”做稳

结论：v1 不采用多智能体框架。

## 5. v1 的固定实现结论

### 5.1 语言与框架

- `PHP`：MediaWiki 扩展入口
- `Python`：assistant API / worker / LangGraph loop / retrieval
- `PostgreSQL + pgvector`：检索与状态
- `JavaScript`：MVP 的 MediaWiki 内嵌交互
- `TypeScript + React`：只在后续需要重前端 side-panel 时再引入

### 5.2 产品入口

- 默认入口：`private wiki` 内的 `Special:知识助手`
- 不单独起一个面向用户的聊天站作为主入口

### 5.3 写入策略

- 助手只生成草稿预览
- 用户确认后才写入 `Draft:` 或约定草稿空间
- v1 不允许自动发布正式页面

### 5.4 检索优先级

1. Cargo 结构化实体
2. 当前页面与相关 Wiki chunk
3. Zotero / PDF chunk
4. 外部学术源
5. 受控工具结果

## 6. 推荐实施顺序

1. `Cargo + Page Forms + 结构化模板`
2. `assistant_api + Postgres/pgvector`
3. `LangGraph loop + 检索器`
4. `Special:知识助手`
5. `草稿预览 / 提交闸门`
6. `Zotero / TPS / RCF` 等工具接入

当前 loop 的详细设计基线见：`docs/langgraph-loop-design.md`。
当前 API 与数据流设计基线见：`docs/assistant-api-design.md`。

## 7. 一句话决策

本项目 v1 采用：

> `MediaWiki(PHP)` 作为知识入口与沉淀层，`Python + LangGraph` 作为主智能体编排层，`Postgres + pgvector` 作为检索与状态层；`beaver-zotero` 只借产品体验，不作为后端架构骨架。
