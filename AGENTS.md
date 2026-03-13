# Repository Guidelines

## Project Structure & Module Organization
This repository is currently plan-first: [`plan.md`](/mnt/c/Songtan/课题组wiki/plan.md) is the source of truth for the MediaWiki deployment design. The planned implementation is a Docker Compose stack with top-level files such as `compose.yaml`, `compose.override.yaml`, `.env.example`, and `README.md`. Keep runtime image code under `images/mediawiki-app/`, operational config under `ops/` (`caddy/`, `db-init/`, `scripts/`), persistent wiki state under `state/` and `uploads/`, and backups under `backups/`. Treat `secrets/` and `state/*/LocalSettings.php` as local-only, never versioned assets.

## Build, Test, and Development Commands
Use Docker Compose as the primary workflow:

- `docker compose config` validates Compose syntax and merged configuration.
- `docker compose build --pull` rebuilds the custom MediaWiki image against the pinned base image.
- `docker compose up -d` starts MariaDB, both wiki containers, and Caddy.
- `docker compose ps` checks service health after startup.
- `docker compose logs mw_public mw_private mariadb` inspects bootstrap and database issues.
- `bash ops/scripts/smoke-test.sh` runs deployment checks once the scripts are scaffolded.

## Coding Style & Naming Conventions
Prefer small, explicit infrastructure files over clever abstractions. Use 2-space indentation in YAML, Caddy, and Markdown lists; use 4 spaces in shell heredocs and embedded config blocks. Bash scripts should start with `#!/usr/bin/env bash` and `set -euo pipefail`. Name scripts with lowercase kebab-case like `smoke-test.sh`; keep Compose service names lowercase with underscores such as `mw_public`. Pin container images to explicit versions and digests, never `latest`.

## Testing Guidelines
This repo is expected to rely on operational tests rather than unit tests. Every infrastructure change should pass `docker compose config`, boot cleanly with `docker compose up -d`, and leave all core services healthy. Add regression checks to `ops/scripts/smoke-test.sh` for idempotent bootstrap, `LocalSettings.php` persistence, and private/public separation.

## Commit & Pull Request Guidelines
No local Git history is available in this directory, so no repository-specific commit convention can be inferred. Use short imperative commit subjects such as `Add Caddy private host config` or `Harden MediaWiki bootstrap script`. PRs should describe the deployment impact, list changed paths, note any secret or state handling implications, and include relevant command output for `docker compose config` and smoke tests.

## Security & Configuration Tips
Do not commit files from `secrets/`, `backups/`, or `state/**/LocalSettings.php`. Keep private wiki exposure limited to loopback or internal routing unless the change explicitly addresses upload and access-control hardening.
