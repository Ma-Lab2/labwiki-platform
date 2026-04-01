# Linux 实验室部署包

这个目录是给 Ubuntu 22.04 / Debian 类 Linux 服务器准备的最小部署入口。

它解决两类部署场景：

1. 新服务器冷启动：使用 `package.sh` 生成完整部署包。
2. 服务器已经 `pull` 仓库：不要再复制代码树，优先使用现成仓库并手工准备 `.env`、`secrets/*.txt`，必要时只迁私有 wiki 安全数据。

## 为什么之前学生记录没有传过去

学生账号、审批状态、wiki 页面内容、私有站运行数据不在 Git 里，而在运行态持久化层里：

- MariaDB：私有/公开 wiki 数据库
- `state/` 和 `uploads/`
- 可选：`assistant_store` PostgreSQL 会话/检索数据库

只做 `git pull` 或只复制代码目录，不会带这些内容。

当前仓库内现成的 wiki 运行数据备份脚本是：

- `ops/scripts/backup.sh`
- `ops/scripts/restore.sh`

这个部署包额外补了一层：

- `backup-runtime-data.sh`
- `restore-runtime-data.sh`

它们会在 `ops/scripts/backup.sh` / `restore.sh` 基础上，连同 `assistant_store` 一起处理。

## 目录说明

- `.env.lab.example`：实验室服务器用的环境变量模板
- `create-secrets.sh`：初始化 `secrets/*.txt`
- `preflight-check.sh`：部署前检查 Docker、Compose、secrets、配置
- `deploy.sh`：构建并启动 `compose.yaml`，随后跑健康检查
- `backup-runtime-data.sh`：导出运行数据
- `restore-runtime-data.sh`：恢复运行数据
- `package.sh`：生成可拷走部署包；可选带 `runtime-data/`


## 推荐默认策略

如果实验室服务器那边已经 `git pull` 了仓库，不推荐继续传完整部署包，也不推荐默认恢复 assistant 运行数据。

默认只做下面三件事：

- 在目标机填写 `.env`
- 在目标机生成或补齐 `secrets/*.txt`
- 重新 `docker compose -f compose.yaml build --pull && docker compose -f compose.yaml up -d`

assistant 相关运行数据，例如：

- assistant 数据库
- assistant 上传附件
- 向量索引/缓存

默认不迁移，目标机按当前环境重新建立。这样更适合环境、模型、embedding 配置已经变化的机器。

如果确实需要把旧学生账号、审批记录、私有 wiki 页面一起迁过去，优先使用安全模式：

- `backup-private-wiki-safe-data.sh`
- `restore-private-wiki-safe-data.sh`
- `package-private-wiki-safe-data.sh`

这条路径只迁：

- `labwiki_private`
- `uploads/private`

不会迁：

- assistant 数据库
- assistant 附件
- `.env`
- `secrets/*.txt`

## Linux 宿主机要求

宿主机必须安装：

- `git`
- `docker`
- `docker compose`
- `bash`
- `tar`
- `curl`

生产 Linux 服务器不需要额外安装：

- MediaWiki
- PHP
- MariaDB
- PostgreSQL
- Caddy

## 最小使用流程

### 1. 在当前仓库生成部署包

```bash
bash ops/deploy-bundle/linux-lab/package.sh --include-runtime-data
```

生成物默认在：

```text
backups/deploy-bundles/
```

其中 `runtime-data/` 会包含之前的学生记录、wiki 页面内容和 assistant 会话库导出。

### 2. 把打包结果拷到实验室 Linux 服务器

把生成出的 `labwiki-linux-lab-<timestamp>.tar.gz` 拷过去并解压。

### 3. 在服务器上准备环境

进入解压后的仓库根目录：

```bash
cp ops/deploy-bundle/linux-lab/.env.lab.example .env
bash ops/deploy-bundle/linux-lab/create-secrets.sh
bash ops/deploy-bundle/linux-lab/preflight-check.sh
```

### 4. 启动服务

```bash
bash ops/deploy-bundle/linux-lab/deploy.sh
```

它会执行：

- `docker compose -f compose.yaml config`
- `docker compose -f compose.yaml build --pull`
- `docker compose -f compose.yaml up -d`
- `bash ops/scripts/smoke-test.sh`

### 5. 如果要把旧学生记录/旧页面内容一起恢复

```bash
bash ops/deploy-bundle/linux-lab/restore-runtime-data.sh \
  --runtime-dir runtime-data \
  --force
```

## 备注

- `compose.yaml` 是正式 Linux 部署入口；不要默认混用 `compose.override.yaml`
- `secrets/`、`state/**/LocalSettings.php`、`backups/` 都不要提交回 Git
