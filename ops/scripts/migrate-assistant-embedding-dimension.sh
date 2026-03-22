#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

TARGET_DIM=""
RUN_REINDEX="false"
SKIP_BACKUP="false"
YES="false"

usage() {
  cat <<'EOF'
Usage: bash ops/scripts/migrate-assistant-embedding-dimension.sh --dimension <n> [options]

Options:
  --dimension <n>  Target embedding dimension, for example 1536 or 3072
  --reindex        Queue /reindex/wiki after schema migration
  --skip-backup    Do not create a pg_dump backup of assistant_store
  --yes            Skip confirmation prompts
  --help           Show this help text

Environment:
  LABWIKI_LOCAL_OVERRIDE=true
    Include compose.override.yaml in docker compose commands.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dimension)
      TARGET_DIM="${2:-}"
      shift
      ;;
    --reindex)
      RUN_REINDEX="true"
      ;;
    --skip-backup)
      SKIP_BACKUP="true"
      ;;
    --yes)
      YES="true"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ -z "${TARGET_DIM}" ]] || [[ ! "${TARGET_DIM}" =~ ^[0-9]+$ ]]; then
  echo "--dimension must be a positive integer." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is not available." >&2
  exit 1
fi

db_name="${ASSISTANT_DB_NAME:-labassistant}"
db_user="${ASSISTANT_DB_USER:-labassistant}"

current_type="$("${compose_cmd[@]}" exec -T assistant_store sh -lc \
  "PGPASSWORD=\"\$(cat /run/secrets/assistant_db_password)\" psql -U '${db_user}' -d '${db_name}' -tAc \"SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a JOIN pg_class c ON a.attrelid = c.oid WHERE c.relname = 'assistant_document_chunks' AND a.attname = 'embedding';\"")"
current_type="$(echo "${current_type}" | tr -d '[:space:]')"
current_dim="${current_type#vector(}"
current_dim="${current_dim%)}"

if [[ "${current_dim}" == "${TARGET_DIM}" ]]; then
  echo "assistant_document_chunks.embedding is already vector(${TARGET_DIM})."
  exit 0
fi

if [[ "${YES}" != "true" ]]; then
  echo "Current embedding column: ${current_type:-unknown}"
  echo "Target embedding column: vector(${TARGET_DIM})"
  echo "This migration drops and recreates assistant_document_chunks.embedding."
  echo "Existing embeddings will be deleted and must be rebuilt."
  read -r -p "Continue [y/N]: " reply
  if [[ ! "${reply}" =~ ^[Yy]$ ]]; then
    echo "Migration cancelled."
    exit 1
  fi
fi

backup_file=""
if [[ "${SKIP_BACKUP}" != "true" ]]; then
  mkdir -p backups
  stamp="$(date +%F_%H-%M-%S)"
  backup_file="backups/${stamp}_assistant_store.sql"
  echo "[step] Backup assistant_store -> ${backup_file}"
  "${compose_cmd[@]}" exec -T assistant_store sh -lc \
    "PGPASSWORD=\"\$(cat /run/secrets/assistant_db_password)\" pg_dump -U '${db_user}' -d '${db_name}'" \
    > "${backup_file}"
fi

restore_cmd="No assistant_store backup was created."
if [[ -n "${backup_file}" ]]; then
  restore_cmd="cat ${backup_file} | ${compose_cmd[*]} exec -T assistant_store sh -lc 'PGPASSWORD=\"\$(cat /run/secrets/assistant_db_password)\" psql -U ${db_user} -d ${db_name}'"
fi

echo "[step] Stop assistant services"
"${compose_cmd[@]}" stop assistant_api assistant_worker >/dev/null

echo "[step] Migrate assistant_document_chunks.embedding -> vector(${TARGET_DIM})"
"${compose_cmd[@]}" exec -T assistant_store sh -lc \
  "PGPASSWORD=\"\$(cat /run/secrets/assistant_db_password)\" psql -v ON_ERROR_STOP=1 -U '${db_user}' -d '${db_name}' <<'SQL'
ALTER TABLE assistant_document_chunks
  DROP COLUMN IF EXISTS embedding;
ALTER TABLE assistant_document_chunks
  ADD COLUMN embedding vector(${TARGET_DIM});
SQL"

echo "[step] Restart assistant services"
"${compose_cmd[@]}" up -d assistant_api assistant_worker >/dev/null

if [[ "${RUN_REINDEX}" == "true" ]]; then
  echo "[step] Queue wiki reindex"
  bash ops/scripts/reindex-assistant.sh wiki
fi

cat <<EOF
Migration finished.

Next:
- Set ASSISTANT_EMBEDDING_DIMENSIONS=${TARGET_DIM} in .env
- Set ASSISTANT_EMBEDDING_MODEL to a matching model, for example:
  - 1536 -> text-embedding-3-small
  - 3072 -> text-embedding-3-large
- Recreate assistant_api / assistant_worker if their env changed
- Rebuild embeddings with: bash ops/scripts/reindex-assistant.sh wiki

Rollback:
- Restore the backup if needed:
  ${restore_cmd}
- Or rerun this script with the previous dimension after restoring .env.
EOF
