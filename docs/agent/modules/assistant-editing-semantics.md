# Assistant Editing Semantics Guide

## Purpose

这份文档只覆盖知识助手的“编辑类操作语义”。

重点回答 4 个问题：

- 助手现在能理解哪些编辑操作
- 之前为什么会把操作话术、解释文本写进页面
- 现在的保护规则是什么
- 改这条链路时应该验证什么

## Scope

当前编辑语义只对受控写入链路生效，不是任意页面自由编辑。

当前稳定覆盖：

- 托管页区块编辑
  - `append`
  - `delete`
  - `replace`
  - `rewrite`
- 草稿预览与提交
- 源码编辑 handoff
- result fill / PageForms fill 的统一操作卡展示

当前不做：

- 任意普通页整页自由写入
- 不经预览直接提交
- 模型自行决定绕过白名单和确认步骤

## Current Mental Model

正确理解这条链路时，不要把它当成“模型直接帮用户写 wiki 页面”。

当前结构是两层：

1. 模型负责理解用户意图
   - 用户到底想新增、删除、替换还是重写
   - 想改哪个页面、哪个区块
   - 想写进去的正文应该是什么

2. 程序负责限制和执行
   - 页面是否在白名单内
   - 区块是否在白名单内
   - 动作是否允许
   - 是否必须先 preview
   - 最终是生成操作卡、源码 handoff，还是 commit

这条边界不能打破。否则最常见的问题就是：模型的解释、证据边界、建议稿一起进入最终正文。

## Supported Operation Kinds

统一操作卡当前对外暴露的 `kind` 语义包括：

- `managed_section_edit`
- `structured_write`
- `draft_page`
- `shot_result_fill`

其中托管页区块编辑是目前最重要的稳定路径。

## Managed Page Section Editing

### White-list boundary

托管页区块编辑只允许命中 `MANAGED_PAGE_SECTION_CONFIG` 里的页面和区块。

当前已接通的页面包括：

- `Shot:Shot日志入口`
- `Shot:周实验日志`
- `Shot:表单新建`
- `Meeting:会议入口`
- `FAQ:常见问题入口`
- `Project:项目总览`

每个页面只允许改自己的白名单区块。

### Operation semantics

托管页区块编辑当前按 4 类动作理解：

- `append`
  - 例：`给使用规则加一条：...`
- `delete`
  - 例：`把刚加的这条使用规则删掉：...`
- `replace`
  - 例：`把使用规则里“旧规则”这条规则改成更正式的写法：新规则`
- `rewrite`
  - 整段重写区块正文

### Why append/delete/replace are handled differently

这 3 类动作不能共用同一套“直接相信模型正文”的逻辑。

- `append`
  - 允许从用户问题里提取新增行
  - 若模型回答里也有候选正文，只能拿清洗后的规则句

- `delete`
  - 不信任模型解释稿
  - 只从当前区块现有条目里删掉目标行

- `replace`
  - 必须同时识别：
    - 旧规则
    - 新规则
  - 只替换命中的那一行
  - 未命中旧规则时必须失败，不能猜

## Why This Broke Before

之前的 bug 主要有 3 类。

### 1. Instruction text leaked into page content

用户会说：

- `编辑一下使用规则区域：加入一条规则：...`

如果后端直接把整句当正文，就会把：

- `编辑一下`
- `加入一条规则`

一起写进页面。

### 2. Explanation text leaked into page content

模型经常会返回：

- `可以，建议这样写`
- `证据边界`
- 代码块里的整段示例

如果直接拿模型整段回答做区块替换，这些文本就会污染页面。

### 3. Replace semantics were missing

之前只稳定支持 `append` 和 `delete`。

当用户说：

- `把这条规则改成更正式的写法`

系统要么退化成整段替换，要么根本不知道该替哪一行。

## Current Protection Rules

### Rule 1: White-list first

任何写入前必须先命中：

- 托管页
- 托管区块
- 允许的操作类型

### Rule 2: Preview first

所有编辑类动作都先生成统一操作卡：

- 目标页面
- 区块
- 操作类型
- 规范化后的预览正文

然后才允许：

- `代我编辑这个模块`
- `确认提交`

### Rule 3: Strip instruction phrases

写入正文前必须清洗掉操作话术，例如：

- `编辑一下`
- `加入一条规则`
- `加一条`
- `新增一条`
- `删掉这条`

### Rule 4: Strip meta/explanation text

写入正文前必须过滤：

- `可以，建议...`
- `证据边界`
- `可执行的删除后内容应为`
- Markdown 代码块残片
- 其他解释性 UI 文案

### Rule 5: Delete does not trust model prose

删除类请求只对当前区块现有行做差集删除。

即使模型回答里带了解释稿，也不能拿那段解释稿做最终区块正文。

### Rule 6: Replace requires explicit old content

替换类请求必须显式指出旧规则，并且旧规则必须能在当前区块里命中。

如果用户只说：

- `把这条规则改得更正式`

但没有指出是哪条规则，就必须失败或要求更明确的输入，不能自动猜。

## Unified Operation Payloads

当前前后端已经把历史分散的：

- `write_preview`
- `draft_preview`
- `result_fill`
- `write_result`

统一派生成：

- `operation_preview`
- `operation_result`

实际代码：

- `assistant_api/app/services/operation_payloads.py`
- `assistant_api/app/schemas.py`
- `assistant_api/app/services/orchestrator.py`
- `assistant_api/app/main.py`
- `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`

前端应优先消费统一操作卡，而不是重新分叉回旧字段判断。

## Source Edit Handoff

`代我编辑这个模块` 的真实行为不是自动保存。

它只做两件事：

1. 把规范化后的区块正文写入 handoff 存储
2. 打开当前页 `action=edit`

然后由编辑器侧逻辑只替换目标区块正文。

最后是否保存，仍由用户决定。

这条边界不能放松。否则就会把“生成预览”和“直接改 wiki”混成同一步。

## Regression Cases We Must Keep

每次改编辑语义时，至少要覆盖下面 4 类回归。

### 1. Append

示例：

- `编辑一下使用规则区域：加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置`

预期：

- 预览里不能保留 `加入一条规则：`
- 编辑器里也只能看到清洗后的最终规则句

### 2. Formal append

示例：

- `给使用规则加一条：每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径。`

预期：

- 作为新增规则行进入预览

### 3. Delete

示例：

- `把刚加的这条使用规则删掉：每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径。`

预期：

- 只删除目标行
- 不把“删除说明”写进区块

### 4. Replace

示例：

- `把使用规则里“打靶后立刻创建或补全页面”这条规则改成更正式的写法：打靶后应立刻创建或补全页面。`

预期：

- 只替换目标规则
- 不保留旧措辞
- 不把“改成更正式的写法”写进正文

## Files to Inspect When This Breaks

后端优先看：

- `assistant_api/app/services/write_actions.py`
- `assistant_api/app/services/operation_payloads.py`
- `assistant_api/app/services/orchestrator.py`
- `assistant_api/app/schemas.py`

前端优先看：

- `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`
- `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell.js`
- `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.editor-utils.js`

浏览器回归脚本：

- `ops/scripts/playwright-private-assistant-operation-check.sh`

静态断言：

- `ops/tests/test_mediawiki_resource_sync.py`

后端单测：

- `assistant_api/tests/test_write_actions.py`
- `assistant_api/tests/test_orchestrator.py`
- `assistant_api/tests/test_operation_payloads.py`

## Minimum Validation Commands

改这条链路后至少跑：

```bash
cd assistant_api && python -m pytest tests/test_write_actions.py tests/test_orchestrator.py tests/test_agent_loop.py -q
python -m pytest ops/tests/test_mediawiki_resource_sync.py -q
bash ops/scripts/playwright-private-assistant-operation-check.sh
```

如果只改前端操作卡展示，仍至少要跑：

```bash
node --check images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js
python -m pytest ops/tests/test_mediawiki_resource_sync.py -q
```

## Non-Negotiable Constraints

- 不允许跳过 preview 直接提交
- 不允许任意页面整页自由写入
- 不允许模型解释稿直接成为区块正文
- `delete` 不能信任模型 prose
- `replace` 不能在未命中旧规则时猜测替换目标
- `代我编辑这个模块` 只允许进入编辑态并填好区块，不允许自动保存
