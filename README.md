# labwiki-platform

MediaWiki Docker Compose baseline for a research group that needs two separate sites:

- `mw_public`: public-facing website / open wiki
- `mw_private`: internal wiki for SOPs, meeting notes, project pages, and lab knowledge

The stack uses one MariaDB container, two isolated MediaWiki instances, and two Caddy frontends. The private site is bound to `127.0.0.1:8443` by default and is not intended for direct public exposure.

## Architecture

Services:

- `mariadb`: single database engine with `labwiki_public` and `labwiki_private`
- `mw_public`: MediaWiki 1.43.6 FPM with idempotent bootstrap
- `mw_private`: MediaWiki 1.43.6 FPM with private-mode hardening
- `caddy_public`: HTTPS entrypoint for the public wiki
- `caddy_private`: loopback-only HTTPS entrypoint for the private wiki

Persistent paths:

- `state/public/LocalSettings.php`
- `state/private/LocalSettings.php`
- `uploads/public/`
- `uploads/private/`
- `backups/`

## Why Two Wikis

This repository intentionally avoids a single mixed-permission wiki. MediaWiki page access and uploaded file access are not the same control plane. Separate public/private instances reduce long-term security and maintenance risk.

Important: disabling anonymous `read` in the private wiki restricts wiki pages only. It does not automatically protect uploaded files from direct-link access if that site is exposed broadly.

## Prerequisites

- Ubuntu or similar Linux host
- Docker Engine
- Docker Compose plugin
- DNS records for `PUBLIC_HOST` and, if used, `PRIVATE_HOST`

Docker is not bundled by this repository. Install Docker first, then verify:

```bash
docker --version
docker compose version
```

## Initial Setup

1. Copy environment defaults:

```bash
cp .env.example .env
```

2. Create local state directories:

```bash
mkdir -p secrets state/public state/private uploads/public uploads/private backups
touch backups/.gitkeep uploads/public/.gitkeep uploads/private/.gitkeep
```

3. Create secrets files with strong passwords:

```text
secrets/db_root_password.txt
secrets/public_db_password.txt
secrets/private_db_password.txt
secrets/public_admin_password.txt
secrets/private_admin_password.txt
```

4. Build and start:

```bash
docker compose -f compose.yaml build --pull
docker compose -f compose.yaml up -d
```

5. Validate:

```bash
docker compose -f compose.yaml ps
bash ops/scripts/smoke-test.sh
```

For local dry runs, opt in to the override file explicitly:

```bash
LABWIKI_LOCAL_OVERRIDE=true docker compose -f compose.yaml -f compose.override.yaml up -d
LABWIKI_LOCAL_OVERRIDE=true bash ops/scripts/smoke-test.sh
```

`compose.override.yaml` is intentionally not used by production scripts unless `LABWIKI_LOCAL_OVERRIDE=true` is set.

## Backup, Restore, Upgrade

Create a backup:

```bash
bash ops/scripts/backup.sh
```

Restore from backup:

```bash
bash ops/scripts/restore.sh --sql backups/2026-03-13_12-00-00_db.sql --archive backups/2026-03-13_12-00-00_state_uploads.tar.gz --force
```

Upgrade after updating the pinned base image tag or digest in `images/mediawiki-app/Dockerfile`:

```bash
bash ops/scripts/upgrade.sh --yes
```

For more reproducible builds, prefetch the pinned VisualEditor source into the repository before `docker compose build`:

```bash
bash ops/scripts/fetch-visualeditor.sh
```

If `vendor/VisualEditor/` is populated, the Docker build uses that local copy instead of cloning from Gerrit.

## Troubleshooting

- `mariadb` unhealthy: verify `secrets/db_root_password.txt` exists and is readable.
- `mw_*` loops during startup: check `docker compose -f compose.yaml logs mw_public` or `docker compose -f compose.yaml logs mw_private`.
- `LocalSettings.php` missing: verify `state/public` or `state/private` is writable by Docker.
- HTTPS issues on local hosts: trust Caddy’s local CA if needed, or use the production hostnames defined in `.env`.

## Repository Layout

```text
compose.yaml
compose.override.yaml
images/mediawiki-app/
ops/caddy/
ops/db-init/
ops/scripts/
secrets/
state/
uploads/
backups/
```
