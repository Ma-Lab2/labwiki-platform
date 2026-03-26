# GitHub 协作者开发手册

这份手册面向接手本仓库的 GitHub 协作者。目标是让你能快速回答 5 个问题：

- 这个仓库的核心模块有哪些
- 本地怎么启动、从哪里进入系统
- 改某个模块应该先看哪里
- 改完后至少跑哪些测试
- 出问题时先查哪条链路

如果你是部署维护者，先看 [README](../README.md)。如果你是深入修改实现的 coding agent，也应同时参考 [docs/agent/README.md](agent/README.md)。

## 1. 仓库模块总览

当前仓库主要由 3 条产品主线和 1 条运维主线组成：

- `LabAssistant`
  - 私有 Wiki 内的知识助手、Shot 回填、PDF 阅读与 PDF 摄取、聊天历史导出
  - 前端主要在 `images/mediawiki-app/extensions/LabAssistant/`
  - 后端主要在 `assistant_api/app/`
- `LabAuth`
  - 学生自助注册、管理员审核、账户管理后台
  - 主要在 `images/mediawiki-app/extensions/LabAuth/`
- `LabWorkbook`
  - 真实实验 Excel 工作簿、主台账、Shot 页面同步
  - 主要在 `images/mediawiki-app/extensions/LabWorkbook/`
- 运维与验证
  - Compose、Caddy、资源同步、Playwright、contract/smoke
  - 主要在 `compose.yaml`、`ops/caddy/`、`ops/scripts/`

运行时核心服务：

- `mw_public`：公开 wiki
- `mw_private`：私有 wiki
- `assistant_api`：智能助手 API
- `assistant_worker`：后台任务
- `assistant_store`：PostgreSQL + pgvector
- `mariadb`：两个 wiki 的数据库
- `caddy_public` / `caddy_private`：公开/私有入口

默认本地验证入口：

- 私有站：`http://localhost:8443`
- 助手 API 站内代理：`http://localhost:8443/tools/assistant/api`

## 2. 开发前先确认什么

先确认本地基础环境：

```bash
docker --version
docker compose version
node --version
python --version
```

如果只改 `assistant_api` Python 侧，优先用仓库脚本进入专用环境：

```bash
bash ops/scripts/assistant-python.sh --cwd assistant_api -m pytest
```

先确认当前服务是否已经起来：

```bash
docker compose ps
```

最常见的进入点：

- 私有首页：`http://localhost:8443`
- 助手主入口：`http://localhost:8443/index.php/Special:LabAssistant`
- 工作簿入口：`http://localhost:8443/index.php/Special:实验工作簿`

## 3. 改不同模块时先看哪里

### 改 `LabAssistant`

先看：

- `assistant_api/app/main.py`
- `assistant_api/app/schemas.py`
- `assistant_api/app/services/`
- `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`
- `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell.js`

高风险边界：

- 正式写 wiki 仍应走受控预览/提交链
- 改前端后通常要做资源同步，否则容器仍在跑旧资源
- 改 `assistant_api` / `assistant_worker` 后，单纯重启通常不够；如果新增了后端路由、schema 或服务逻辑，必须重建对应容器
- 浏览器侧入口默认通过私有站代理，不直接打容器内 API

### 改 `LabAuth`

先看：

- `images/mediawiki-app/extensions/LabAuth/extension.json`
- `images/mediawiki-app/extensions/LabAuth/includes/`
- `images/mediawiki-app/extensions/LabAuth/modules/`

高风险边界：

- 保持 MediaWiki 原生登录，不重做整套认证内核
- 注册审核和账户日志属于私有站逻辑，不要误接到公开站

### 改 `LabWorkbook`

先看：

- `images/mediawiki-app/extensions/LabWorkbook/includes/`
- `images/mediawiki-app/extensions/LabWorkbook/modules/`
- `images/mediawiki-app/seed/private/workbooks/`
- `ops/scripts/extract_lab_workbooks.py`

高风险边界：

- 工作簿是实验事实主源
- `Shot:` 页面只承载详情与知识整理，不应反过来覆盖工作簿事实层

### 改运维与验证

先看：

- `compose.yaml`
- `compose.override.yaml`
- `ops/caddy/`
- `ops/scripts/smoke-test.sh`
- `ops/scripts/validate-assistant.sh`
- `ops/scripts/check_mediawiki_resource_sync.py`
- `ops/scripts/sync-mediawiki-runtime-resources.sh`

## 4. 标准开发流程

推荐顺序：

1. 先看对应模块入口和最近相关脚本
2. 改代码
3. 跑该模块最小测试
4. 如果改了 MediaWiki 前端资源，执行资源同步
5. 跑对应浏览器回归
6. 最后再跑通用 smoke / contract

### 改了 MediaWiki 前端资源后

先检查运行态资源是否漂移：

```bash
python ops/scripts/check_mediawiki_resource_sync.py --service mw_private --json
```

如果结果不是 `status: ok`，先同步：

```bash
bash ops/scripts/sync-mediawiki-runtime-resources.sh --service mw_private
```

再重新检查一次。

这是当前仓库里最容易踩坑的地方：仓库代码变了，但 `mw_private` 容器里仍是旧扩展文件，浏览器回归会因此得出假结论。

### 改了 `assistant_api` / `assistant_worker` 后

这类改动不受 `sync-mediawiki-runtime-resources.sh` 管理。尤其是：

- 新增或修改 FastAPI 路由
- 调整 Pydantic schema
- 修改 `assistant_api/app/services/` 的后端流程
- 修改 worker 任务逻辑

都应该直接重建容器：

```bash
docker compose up -d --build assistant_api assistant_worker
```

重建后先做最小健康检查：

```bash
curl --noproxy '*' -fsS 'http://localhost:8443/tools/assistant/api/health'
```

如果是新增后端接口，建议再进容器确认运行态路由是否真的存在，而不是只看仓库源码。

## 5. 最小测试矩阵

以下是当前协作者最常用的验证矩阵。不要一上来就全量跑，优先按改动范围选。

### 基线检查

```bash
docker compose config
docker compose ps
python ops/scripts/check_mediawiki_resource_sync.py --service mw_private --json
```

### Python / assistant_api

```bash
bash ops/scripts/assistant-python.sh --cwd assistant_api -m pytest
```

### 前端模块

按改动范围跑 `node --test` 和 `node --check`。常见入口包括：

```bash
node --test images/mediawiki-app/extensions/LabAssistant/tests/*.test.js
node --test images/mediawiki-app/extensions/LabAuth/tests/*.test.js
node --test images/mediawiki-app/extensions/LabWorkbook/tests/*.test.js
node --check images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js
```

### 通用运维与契约

```bash
bash ops/scripts/smoke-test.sh
bash ops/scripts/validate-assistant.sh --profile contract
```

### 浏览器回归

按改动范围选择：

```bash
bash ops/scripts/playwright-private-session-check.sh
bash ops/scripts/playwright-private-shot-fill-check.sh
bash ops/scripts/playwright-private-pdf-reader-check.sh
bash ops/scripts/playwright-private-pdf-ingest-check.sh
bash ops/scripts/playwright-private-auth-check.sh
bash ops/scripts/playwright-private-labworkbook-check.sh
```

业务对应关系：

- 助手主链 / 插件壳 / 会话恢复：`playwright-private-session-check.sh`
- Shot 学生回填链：`playwright-private-shot-fill-check.sh`
- 文献导读 PDF 阅读：`playwright-private-pdf-reader-check.sh`
- PDF 摄取写草稿 / Control：`playwright-private-pdf-ingest-check.sh`
- 学生注册与管理员后台：`playwright-private-auth-check.sh`
- 实验工作簿：`playwright-private-labworkbook-check.sh`

浏览器验证产物默认写到：

- `backups/validation/<script-name>-<timestamp>/`

PR 里优先引用其中的 `report.md`。

## 6. 常见开发场景应该怎么测

### 场景 A：只改 `assistant_api`

至少跑：

```bash
bash ops/scripts/assistant-python.sh --cwd assistant_api -m pytest
docker compose up -d --build assistant_api assistant_worker
bash ops/scripts/validate-assistant.sh --profile contract
```

如果改动影响 Shot/PDF 工作流，再加对应 Playwright。

### 场景 B：只改 MediaWiki 前端 UI

至少跑：

```bash
node --test <对应测试>
node --check <对应入口文件>
python ops/scripts/check_mediawiki_resource_sync.py --service mw_private --json
bash ops/scripts/sync-mediawiki-runtime-resources.sh --service mw_private
bash ops/scripts/playwright-private-session-check.sh
```

如果是专项链路页面，再补专项脚本。

### 场景 C：改工作簿

至少跑：

```bash
node --test images/mediawiki-app/extensions/LabWorkbook/tests/*.test.js
bash ops/scripts/playwright-private-labworkbook-check.sh
```

### 场景 D：改账户后台

至少跑：

```bash
node --test images/mediawiki-app/extensions/LabAuth/tests/*.test.js
bash ops/scripts/playwright-private-auth-check.sh
```

### 场景 E：改 compose / 代理 / 启动链

至少跑：

```bash
docker compose config
bash ops/scripts/smoke-test.sh
bash ops/scripts/validate-assistant.sh --profile contract
```

必要时再跑受影响的浏览器回归。

## 7. 常见问题排查

### 1. 浏览器页面和仓库代码不一致

先查：

```bash
python ops/scripts/check_mediawiki_resource_sync.py --service mw_private --json
```

如果是 `drift`，先同步运行态资源，再重试浏览器脚本。

如果你刚刚同步并重启了 `mw_private`，而私有站首页突然开始返回 `502`，先重启一次 `caddy_private` 再测：

```bash
docker compose restart caddy_private
```

这是当前本地环境里一个真实出现过的恢复动作。

### 2. Playwright 脚本一开始就失败

先查：

```bash
docker info
docker compose ps
```

当前 Playwright 脚本普遍依赖：

- Docker engine 可达
- `mw_private` / `caddy_private` 正常运行
- `secrets/private_admin_password.txt` 存在

很多脚本会把这类问题明确报成 `environment unavailable`，这类错误先按环境问题处理，不要直接判成功能 bug。

### 3. 助手上传/聊天链能通，但页面仍报旧行为

通常是以下两类之一：

- `mw_private` 里前端扩展文件没同步
- ResourceLoader 仍在吃旧资源版本

先做资源同步，再重新打开页面。

### 4. 不确定该跑哪条脚本

最保守选择：

```bash
bash ops/scripts/playwright-private-session-check.sh
```

这是当前私有站助手主链的通用浏览器验证。

如果你改的是 PDF 摄取正式写回链，直接跑：

```bash
bash ops/scripts/playwright-private-pdf-ingest-check.sh
```

这条脚本会覆盖：

- PDF 上传
- 建议归档区域评审
- 草稿预览与草稿提交
- `Control:` 正式写入预览
- `Control:控制与运行总览` 入口更新

## 8. GitHub 协作要求

提交信息保持短、直接、祈使句，例如：

- `Add collaborator handbook entrypoint`
- `Harden shot fill playwright report`

PR 描述建议至少包含：

- 改动目标
- 影响路径
- 是否涉及容器重启/资源同步
- 实跑验证命令
- 浏览器回归报告路径

不要提交这些内容：

- `secrets/`
- `backups/` 下临时报告
- `state/**/LocalSettings.php`
- 明显属于本地缓存或敏感数据的文件

## 9. 推荐阅读顺序

第一次接手仓库，建议按这个顺序读：

1. [README](../README.md)
2. 本手册
3. [docs/agent/README.md](agent/README.md)
4. [docs/agent/system-overview.md](agent/system-overview.md)
5. 对应模块手册：
   - [assistant](agent/modules/assistant.md)
   - [mediawiki](agent/modules/mediawiki.md)
   - [ops-and-validation](agent/modules/ops-and-validation.md)

这套顺序更适合 GitHub 协作者：先知道怎么跑、怎么测，再深入模块内部。
