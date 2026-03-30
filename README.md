# labwiki-platform

MediaWiki Docker Compose baseline for a research group that needs two separate sites:

- `mw_public`: public-facing website / open wiki
- `mw_private`: internal wiki for SOPs, meeting notes, project pages, and lab knowledge

The stack uses one MariaDB container, two isolated MediaWiki instances, two integrated analysis tools, and two Caddy frontends. The private site is bound to `127.0.0.1:8443` by default in the base Compose file, but the current local lab override serves the private wiki through the canonical entry `http://localhost:8443`.

## For GitHub Collaborators

If you are onboarding to active development rather than only deploying the stack, start with:

- [docs/github-collaborator-handbook.zh-CN.md](docs/github-collaborator-handbook.zh-CN.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

## For Coding Agents

If you are changing implementation details rather than deploying the stack, start with:

- `docs/agent/README.md`
- `docs/agent/system-overview.md`

Those documents provide a maintenance-oriented map of the current modules, runtime boundaries, and validation paths. `README.md` remains the human deployment entrypoint; the `docs/agent/` set is the fast path for coding agents.

## Architecture

Services:

- `mariadb`: single database engine with `labwiki_public` and `labwiki_private`
- `mw_public`: MediaWiki 1.43.6 FPM with idempotent bootstrap
- `mw_private`: MediaWiki 1.43.6 FPM with private-mode hardening
- `rcf_backend`: FastAPI service for RCF stack design and async compute
- `rcf_frontend`: Nginx-served Vue frontend mounted under the private site
- `tps_web`: FastAPI + Vue service for Thomson parabola image analysis, mounted under the private site
- `assistant_store`: PostgreSQL + pgvector for assistant sessions, chunks, and jobs
- `assistant_api`: FastAPI + LangGraph orchestrator for knowledge assistant chat, retrieval, and draft preview
- `assistant_worker`: background worker for wiki indexing jobs and optional Zotero reindex jobs
- `caddy_public`: HTTPS entrypoint for the public wiki
- `caddy_private`: loopback-only HTTPS entrypoint for the private wiki

Persistent paths:

- `state/public/LocalSettings.php`
- `state/private/LocalSettings.php`
- `state/rcf/uploaded_materials/`
- `state/tps/`
- `uploads/public/`
- `uploads/private/`
- `tools-data/tps/images/`
- `tools-data/tps/output/`
- `docs/zotero/` (optional)
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

Important deployment boundary:

- A Linux deployment host does **not** need Codex/Cursor/Claude-style agent skills to run this stack.
- Production deployment only requires the host tools above plus the repo files, secrets, and Docker images.
- MediaWiki, PHP, MariaDB, PostgreSQL/pgvector, Caddy, assistant API, and the tool services all run inside containers.

## Optional Developer / Agent Tools

The following tools are **not** required for production deployment. Install them only if this machine is also used for development, browser regression, or coding-agent workflows.

### Optional local tools

- `python` / `node`
  - Needed for local tests such as `pytest`, `node --test`, and `node --check`
- `playwright-cli`
  - Needed for browser regression scripts under `ops/scripts/playwright-private-*.sh`
- `opencli`
  - Optional only; the assistant capability catalog can expose it as a provider slot, but the system still works without it

### About “skills”

This repository references coding-agent skills in `docs/agent/` and `docs/superpowers/`, but those are maintainer/agent workflow assets, not runtime dependencies for the Linux server.

- If you are only deploying the stack: do **not** install any Codex/Cursor/Claude skill packs on the server just for deployment.
- If you are also using the machine as a coding-agent workstation: the relevant optional tooling is `playwright-cli`, local Python/Node test runtimes, and any agent platform you already use.
- The repository itself does not require a separate “skill installer” step to boot the product.

## Initial Setup

1. Copy environment defaults:

```bash
cp .env.example .env
```

2. Create local state directories:

```bash
mkdir -p secrets state/public state/private state/rcf/uploaded_materials state/tps \
  uploads/public uploads/private backups tools-data/tps/images tools-data/tps/output
touch backups/.gitkeep uploads/public/.gitkeep uploads/private/.gitkeep
touch state/rcf/uploaded_materials/.gitkeep
touch state/tps/.gitkeep tools-data/tps/images/.gitkeep tools-data/tps/output/.gitkeep
```

3. Create secrets files with strong passwords:

```text
secrets/db_root_password.txt
secrets/public_db_password.txt
secrets/private_db_password.txt
secrets/public_admin_password.txt
secrets/private_admin_password.txt
secrets/assistant_db_password.txt
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
bash ops/scripts/playwright-private-pdf-reader-check.sh
```

For local dry runs, opt in to the override file explicitly:

```bash
LABWIKI_LOCAL_OVERRIDE=true docker compose -f compose.yaml -f compose.override.yaml up -d
LABWIKI_LOCAL_OVERRIDE=true bash ops/scripts/smoke-test.sh
```

`compose.override.yaml` is intentionally not used by production scripts unless `LABWIKI_LOCAL_OVERRIDE=true` is set.
In local mode, the public site uses [`ops/caddy/Caddyfile.public.local`](/mnt/c/Songtan/课题组wiki/ops/caddy/Caddyfile.public.local) with `tls internal`, so `https://localhost` does not depend on ACME.

The private site also exposes integrated tool pages:

- `https://localhost:8443/tools/rcf/`
- `https://localhost:8443/tools/tps/`
- `https://localhost:8443/index.php/Special:LabAssistant`
- `https://<PRIVATE_HOST>/tools/rcf/`
- `https://<PRIVATE_HOST>/tools/tps/`
- `https://<PRIVATE_HOST>/index.php/Special:LabAssistant`

`TPS_IMAGE_DIR` controls which host directory is mounted into the TPS tool as its read-only raw image root. By default it falls back to `./tools-data/tps/images`, but on the lab machine it should point at the real experiment image tree, for example:

```bash
TPS_IMAGE_DIR=/mnt/c/path/to/lab-tps-images
```

The assistant can still run in retrieval-only mode without a model key, but the default generation path is now Anthropic SDK with a configurable `base_url`. This lets Claude-format traffic go through a relay such as `gptgod` while keeping the native `/v1/messages` payload shape. When an Anthropic key is configured, the runtime now prefers Claude as the default generation family even if the generic `ASSISTANT_GENERATION_PROVIDER` still points somewhere else for compatibility.

Runtime note: the assistant no longer depends only on a fixed hard-coded retrieval flow. The current core is a controlled agent loop:

- the model chooses the next tool action from a whitelist
- tools cover local search, wiki read/search, OpenAlex, optional web search, tool execution, draft preview, and write preview
- whitelist write operations now run as `prepare_write_preview -> commit_write -> answer`, and still do not allow open-ended arbitrary page edits

The main implementation lives in:

- `assistant_api/app/services/agent_loop.py`
- `assistant_api/app/services/orchestrator.py`
- `assistant_api/app/services/prompts.py`

The private wiki assistant UI now uses:

- `POST /tools/assistant/api/chat/stream` for SSE streaming
- `GET /tools/assistant/api/session/{session_id}` for multi-turn session restore
- `GET /tools/assistant/api/models/catalog` for grouped model selection
- `PATCH /tools/assistant/api/session/{session_id}/model` for session-level generation model switching
- `GET /tools/assistant/api/capabilities` for the unified capability/provider catalog
- `POST /tools/assistant/api/actions/preview` for capability preview calls
- `POST /tools/assistant/api/actions/commit` for capability commit calls

From the student-facing product layer, the primary workflow is now:

- ask normal questions about the current page
- organize the current page into a term page or newcomer-facing knowledge page draft
- turn shot pages or experiment notes into previewable log/record drafts
- confirm previewed writes explicitly instead of letting the assistant write silently

The browser keeps the active `session_id` in local storage and reuses it for follow-up questions. It also stores the last selected model family/model and restores them for new sessions. `GET /session/{session_id}` now returns rich turn history, including `step_stream`, `sources`, `action_trace`, `draft_preview`, `write_preview`, and `write_result`, so the UI can restore the most recent full result panel after refresh. If you change the SSE event contract, model info payloads, or response shape, update both the FastAPI routes and `images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js`.

The current model catalog is grouped and curated rather than exposing the raw relay model list directly. The main supported generation families are:

- GPT: `gpt-5.4`, `gpt-5.4-mini`
- Claude: `claude-sonnet-4-5-20250929-thinking`, `claude-sonnet-4-5-20250929`, `claude-sonnet-4-6-thinking`, `claude-sonnet-4-6`
- Gemini: `gemini-3-flash-preview-thinking`, `gemini-3-flash-preview`, `gemini-3-pro-thinking`, `gemini-3-pro`, `gemini-3.1-pro-preview-thinking`

Session-level generation switching currently changes only the answer-generation model. Embedding, web search, and reindex behavior remain globally configured.

The capability/action layer now unifies local knowledge, native CLI tools, and future OpenCLI/MCP providers behind the same preview/commit contract. In the current local environment:

- `local_knowledge` is available and covers draft/write preview + commit plus existing wiki-centric flows
- `native_cli` is available for current repo-safe CLI wrappers
- `opencli` is discoverable as a provider slot, but remains unavailable until the `opencli` binary is installed locally
- `mcp` is a placeholder provider slot for the next integration phase

For local CLI usage, the repo now ships a small wrapper:

```bash
bash ops/scripts/assistantctl.sh ask "总结这个页面"
bash ops/scripts/assistantctl.sh draft "把当前页整理成词条草案" --context-page Theory:TNSA
bash ops/scripts/assistantctl.sh stream "什么是 TNSA？"
bash ops/scripts/assistantctl.sh session show <session_id>
```

The CLI now defaults to the same local product entrypoint as the private site:

- `http://localhost:8443/tools/assistant/api`

Use `--base-url` only when you intentionally want to target a different assistant endpoint.

Default Claude-through-gptgod settings:

```bash
ASSISTANT_ANTHROPIC_BASE_URL=https://api.gptgod.online
ASSISTANT_ANTHROPIC_API_KEY=...
ASSISTANT_ANTHROPIC_MODEL=claude-sonnet-4-5-20250929-thinking
ASSISTANT_ANTHROPIC_TIMEOUT=180
ASSISTANT_ANTHROPIC_MAX_TOKENS=2048
```

Alternative generation providers are also supported:

```bash
ASSISTANT_GENERATION_PROVIDER=openai
ASSISTANT_OPENAI_BASE_URL=https://api.openai.com/v1
ASSISTANT_OPENAI_API_KEY=...
ASSISTANT_OPENAI_MODEL=gpt-4.1-mini
```

```bash
ASSISTANT_GENERATION_PROVIDER=openai_compatible
ASSISTANT_OPENAI_COMPATIBLE_BASE_URL=https://your-relay.example/v1
ASSISTANT_OPENAI_COMPATIBLE_API_KEY=...
ASSISTANT_OPENAI_COMPATIBLE_MODEL=qwen-max
```

Embeddings are configured independently through an OpenAI-compatible endpoint. This keeps retrieval usable with providers that expose Claude-format chat but OpenAI-format `/v1/embeddings`:

```bash
ASSISTANT_EMBEDDING_BASE_URL=https://api.gptgod.online/v1
ASSISTANT_EMBEDDING_API_KEY=...
ASSISTANT_EMBEDDING_MODEL=text-embedding-3-small
ASSISTANT_EMBEDDING_DIMENSIONS=1536
ASSISTANT_EMBEDDING_TIMEOUT=60
```

If `ASSISTANT_EMBEDDING_MODEL` is left empty, the assistant falls back to keyword retrieval only and skips vector writes during reindexing.

Retrieval now has two explicit knobs:

```bash
ASSISTANT_VECTOR_STORE_BACKEND=pgvector
ASSISTANT_RETRIEVAL_TOKENIZER_MODE=mixed
ASSISTANT_RETRIEVAL_NORMALIZATION_MODE=basic
```

- `ASSISTANT_VECTOR_STORE_BACKEND` is the current vector backend selector. `pgvector` remains the default production path. `qdrant_local` is available as a benchmark/runtime candidate for A/B comparison without changing the fact storage layer.
- `ASSISTANT_RETRIEVAL_TOKENIZER_MODE` controls keyword tokenization. Supported modes are `mixed`, `ascii`, and `cjk`.
- `ASSISTANT_RETRIEVAL_NORMALIZATION_MODE` controls query expansion and domain-term normalization. `basic` is now the default on the expanded lab benchmark; `lab` keeps alias expansion such as `TNSA`, `RCF`, `TPS`, and `Shot` log variants for A/B comparison and targeted tuning.

Web search is configured independently from academic search. OpenAlex stays on as the academic source for literature/compare questions; optional web search adds broader webpages when enabled:

```bash
ASSISTANT_ENABLE_WEB_SEARCH=true
ASSISTANT_WEB_SEARCH_PROVIDER=tavily
ASSISTANT_TAVILY_API_KEY=...
ASSISTANT_CONVERSATION_HISTORY_TURNS=4
```

Or with an OpenAI-compatible responses endpoint:

```bash
ASSISTANT_ENABLE_WEB_SEARCH=true
ASSISTANT_WEB_SEARCH_PROVIDER=openai
ASSISTANT_OPENAI_WEB_SEARCH_MODEL=gpt-4.1-mini
```

Prompt assembly is centralized in `assistant_api/app/services/prompts.py`. That file is the current home for system prompts, task-specific guidance, few-shot examples, and domain keyword packs.

For the current local lab environment, the private wiki uses a single canonical entry:

- use `http://localhost:8443` for browser access, CLI access, and assistant callbacks on the lab machine
- treat `127.0.0.1:8443` and any LAN host as lower-level transport endpoints that must redirect back to `localhost:8443`
- the assistant UI keeps host-scoped local state, so private-site scripts and saved links should stay on `localhost:8443` to avoid split sessions

Some local proxy tools intercept bare `127.0.0.1` HTTP traffic more aggressively than `localhost`. Keep `http://localhost:8443` as the only user-facing private entry and let non-canonical hosts redirect there.

To compare retrieval strategies and tokenizer modes against the current wiki content, run:

```bash
bash ops/scripts/benchmark-assistant-retrieval.sh
```

This benchmarks `keyword`, `vector`, and `hybrid` retrieval across:

- tokenizer modes: `mixed`, `ascii`, `cjk`
- normalization modes: `basic`, `lab`
- vector backends: `pgvector`, `qdrant_local`

using the default case set in `assistant_api/app/benchmarks/retrieval_cases.json`. To keep a report in the repo:

```bash
bash ops/scripts/benchmark-assistant-retrieval.sh --output backups/validation/retrieval-benchmark.json
```

The benchmark report now includes:

- `summary`: aggregate recall/rank per `vector_backend + strategy + tokenizer + normalization`
- `category_summary`: the same metrics broken down by case category such as `theory`, `diagnostic`, `device`, `log`, and `control`
- `leaderboard`: the sorted best-performing combinations
- `misses`: unmatched cases grouped by retrieval configuration

The current reference report is [backups/validation/retrieval-benchmark-v3.json](/mnt/c/songtan/课题组wiki/backups/validation/retrieval-benchmark-v3.json). On the expanded 19-case lab-oriented set:

- `hybrid` remains the best default strategy
- `mixed + basic` currently gives the best average ranking while keeping `recall_at_k = 1.0`
- `pgvector` and `qdrant_local` are effectively tied on this case set, so production should continue to default to `pgvector` until a larger benchmark shows a clear win

To score the assistant from a real student-task perspective rather than only a retrieval perspective, use the student evaluation assets:

- `assistant_api/app/benchmarks/student_eval_cases.json`
- `assistant_api/app/services/student_eval_report.py`
- `ops/scripts/build-assistant-student-eval-report.sh`

The current student evaluation set contains 40 prompts across:

- `concept`
- `page_guidance`
- `current_page`
- `term_structuring`
- `records_logs`
- `tools_workflow`
- `compare_judgment`
- `boundary_failure`

Each item is scored on five 0-2 dimensions:

- `task_completion`
- `lab_context_fit`
- `current_page_use`
- `structure_usability`
- `boundary_honesty`

with two direct penalties:

- `penalty_off_topic`
- `penalty_index_as_answer`

The final score is `sum(dimensions) - penalties`, clamped to `0-10`.

Generate a blank score sheet:

```bash
bash ops/scripts/build-assistant-student-eval-report.sh \
  --template-output backups/validation/student-eval-template.csv
```

After manually scoring the CSV, build the JSON + Markdown report:

```bash
bash ops/scripts/build-assistant-student-eval-report.sh \
  --scores backups/validation/student-eval-scores.csv \
  --json-output backups/validation/student-eval-report.json \
  --markdown-output backups/validation/student-eval-report.md
```

This report is the quality layer on top of contract validation and retrieval benchmarks. Use it to answer:

- can a student directly use the answer
- did the assistant stay grounded in the current page and lab wiki
- which failure tags are frequent enough to justify the next optimization round

For local assistant development and evaluation, do not rely on whichever `python` or `python3` happens to be first on your shell `PATH`. This machine currently has multiple interpreters in play. Use the dedicated conda Python 3.12 entrypoint instead:

```bash
bash ops/scripts/assistant-python.sh --ensure
bash ops/scripts/assistant-python.sh --doctor
```

That script creates or updates the `labwiki-assistant-py312` conda environment from `assistant_api/environment.conda.yml`, installs `assistant_api/requirements.txt`, and then runs local assistant-only Python commands in a stable interpreter.

If you later want to upgrade from `text-embedding-3-small` to `text-embedding-3-large`, note that the vector column dimension changes from `1536` to `3072`. This is not a model-name-only change. You must migrate the `assistant_document_chunks.embedding` column and then rebuild embeddings:

```bash
bash ops/scripts/migrate-assistant-embedding-dimension.sh --dimension 3072 --yes
```

After the schema migration:

```bash
ASSISTANT_EMBEDDING_MODEL=text-embedding-3-large
ASSISTANT_EMBEDDING_DIMENSIONS=3072
docker compose up -d assistant_api assistant_worker
bash ops/scripts/reindex-assistant.sh wiki
```

Zotero is an optional literature source. By default the assistant answers from wiki/Cargo first and expands to OpenAlex when needed. Only enable Zotero if you want local literature snapshots to participate in retrieval:

```bash
ASSISTANT_ENABLE_ZOTERO=true
ASSISTANT_ZOTERO_SNAPSHOT_DIR=/data/zotero
```

When Zotero is enabled, export Zotero JSON / notes / extracted text into `docs/zotero/` and trigger reindexing:

```bash
bash ops/scripts/reindex-assistant.sh wiki
bash ops/scripts/reindex-assistant.sh zotero
```

Recommended validation steps after wiring in your relay key:

```bash
bash ops/scripts/assistant-python.sh -m compileall assistant_api/app
docker compose config
bash ops/scripts/validate-assistant.sh --profile contract
```

Validation profiles:

```bash
bash ops/scripts/validate-assistant.sh --profile contract
bash ops/scripts/validate-assistant.sh --profile chat
bash ops/scripts/validate-assistant.sh --profile full
```

The validation script now auto-selects an available GPT/Gemini generation model for runtime checks, so it can still pass even if the configured Claude relay is temporarily out of credit.

Write a machine-readable report:

```bash
bash ops/scripts/validate-assistant.sh --profile full --report-file backups/validation/manual-full.json
```

Profile behavior:

- `contract`: `/health`, `/plan`, `/tool/execute`, `/draft/preview`, `/admin/stats`, `/admin/index/stats`, `/reindex/zotero`
- `chat`: `contract` + `/chat`, follow-up `/chat` in the same session, `/compare`, `/session/{session_id}`, direct SSE, proxied SSE
- `full`: `chat` + `/reindex/wiki` wait + embedding/index assertions

Useful options:

```bash
bash ops/scripts/validate-assistant.sh --profile full --commit-draft
bash ops/scripts/reindex-assistant.sh wiki --wait --timeout 1200
bash ops/scripts/playwright-private-session-check.sh
bash ops/scripts/playwright-private-shot-fill-check.sh
```

With `ASSISTANT_ENABLE_ZOTERO=false`, `/reindex/zotero` should return a `disabled` status instead of failing. When an embedding model is configured, `full` validation asserts that all wiki chunks have embeddings and that `/admin/index/stats` reports the configured vector dimension.
`--report-file` writes a JSON artifact with profile, status, and per-check results. `update.sh` and `upgrade.sh` now create timestamped reports under `backups/validation/` by default when assistant validation is enabled.

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

Upgrade variants:

```bash
bash ops/scripts/upgrade.sh --yes --assistant-validate-profile contract
bash ops/scripts/upgrade.sh --yes --assistant-validate-profile full
bash ops/scripts/upgrade.sh --yes --skip-assistant-validate
bash ops/scripts/upgrade.sh --yes --assistant-report-file backups/validation/upgrade-manual.json
```

Routine pull + rebuild + restart + smoke test:

```bash
bash ops/scripts/update.sh --yes
```

Update variants:

```bash
bash ops/scripts/update.sh --yes --assistant-validate-profile contract
bash ops/scripts/update.sh --yes --assistant-validate-profile full
bash ops/scripts/update.sh --yes --skip-assistant-validate
bash ops/scripts/update.sh --yes --assistant-report-file backups/validation/update-manual.json
```

## Troubleshooting

- `mariadb` unhealthy: verify `secrets/db_root_password.txt` exists and is readable.
- `mw_*` loops during startup: check `docker compose -f compose.yaml logs mw_public` or `docker compose -f compose.yaml logs mw_private`.
- `tps_web` shows an empty file list: verify `TPS_IMAGE_DIR` points to a readable host directory and that Docker can mount it.
- `LocalSettings.php` missing: verify `state/public` or `state/private` is writable by Docker.
- HTTPS issues on local hosts: trust Caddy’s local CA if needed, or use the production hostnames defined in `.env`.
- `docker` missing inside WSL: enable Docker Desktop WSL integration for this distro before running `smoke-test.sh`, `validate-assistant.sh`, or any compose-based validation.

## Repository Layout

```text
compose.yaml
compose.override.yaml
assistant_api/
images/mediawiki-app/
ops/caddy/
ops/db-init/
ops/scripts/
docs/zotero/
secrets/
state/
uploads/
backups/
```
