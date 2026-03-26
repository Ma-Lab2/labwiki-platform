# Contributing

协作者开发入口请先读：

- [GitHub 协作者开发手册（中文）](docs/github-collaborator-handbook.zh-CN.md)
- [README](README.md)

提交 PR 前至少补这些信息：

- 本次改动影响的模块，例如 `LabAssistant`、`LabAuth`、`LabWorkbook`、`assistant_api`、`ops/scripts`
- 实际运行过的验证命令
- 是否需要 `sync-mediawiki-runtime-resources.sh`、容器重启或 `docker compose up -d --build assistant_api assistant_worker`
- 如果改了浏览器链路，附对应 `backups/validation/.../report.md` 路径

请不要提交：

- `secrets/`
- `state/**/LocalSettings.php`
- `backups/` 下的临时验证产物
- 本地运行时生成的敏感或大体积文件
