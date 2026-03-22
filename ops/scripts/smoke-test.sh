#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is not available." >&2
  exit 1
fi

check_http() {
  local url="$1"
  local label="$2"
  local code

  code="$(curl --noproxy '*' -k -s -o /dev/null -w '%{http_code}' "${url}")"
  case "${label}:${code}" in
    public:200|public:301|public:302|private:200|private:301|private:302|private:401|private:403|assistant-api:200|rcf-ui:200|rcf-api:200|tps-ui:200|tps-api:200)
      printf '[ok] %s returned %s\n' "${label}" "${code}"
      ;;
    *)
      printf '[fail] %s returned %s for %s\n' "${label}" "${code}" "${url}" >&2
      exit 1
      ;;
  esac
}

"${compose_cmd[@]}" ps mariadb mw_public mw_private caddy_public caddy_private >/dev/null
"${compose_cmd[@]}" ps rcf_backend rcf_frontend tps_web assistant_store assistant_api assistant_worker >/dev/null

if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  default_public_url="http://127.0.0.1"
  default_private_url="http://localhost:8443"
else
  default_public_url="$("${compose_cmd[@]}" exec -T mw_public sh -lc 'printf %s "$MW_SERVER"')"
  default_private_url="$("${compose_cmd[@]}" exec -T mw_private sh -lc 'printf %s "$MW_SERVER"')"
fi

PUBLIC_URL="${PUBLIC_SMOKE_URL:-${default_public_url}}"
PRIVATE_URL="${PRIVATE_SMOKE_URL:-${default_private_url}}"
PUBLIC_NAME="$("${compose_cmd[@]}" exec -T mw_public sh -lc 'printf %s "$MW_SITE_NAME"')"
PRIVATE_NAME="$("${compose_cmd[@]}" exec -T mw_private sh -lc 'printf %s "$MW_SITE_NAME"')"

"${compose_cmd[@]}" exec -T mw_public sh -lc 'test -s /state/LocalSettings.php && test -w /var/www/html/images'
"${compose_cmd[@]}" exec -T mw_private sh -lc 'test -s /state/LocalSettings.php && test -w /var/www/html/images'
"${compose_cmd[@]}" exec -T mariadb sh -lc \
  'mariadb -uroot -p"$(cat /run/secrets/db_root_password)" -e "USE labwiki_public; SHOW TABLES;" >/dev/null && mariadb -uroot -p"$(cat /run/secrets/db_root_password)" -e "USE labwiki_private; SHOW TABLES;" >/dev/null'

"${compose_cmd[@]}" exec -T mw_public sh -lc "grep -F \"${PUBLIC_NAME}\" /state/LocalSettings.php >/dev/null"
"${compose_cmd[@]}" exec -T mw_private sh -lc "grep -F \"${PRIVATE_NAME}\" /state/LocalSettings.php >/dev/null"
printf '%s\n' 'foreach (["PageForms","TemplateData"] as $name) { if (!ExtensionRegistry::getInstance()->isLoaded($name)) { fwrite(STDERR, $name . " missing\n"); exit(1); } }' \
  | "${compose_cmd[@]}" exec -T mw_private php maintenance/run.php eval.php >/dev/null
printf '%s\n' 'foreach (["Cargo","LabAssistant"] as $name) { if (!ExtensionRegistry::getInstance()->isLoaded($name)) { fwrite(STDERR, $name . " missing\n"); exit(1); } }' \
  | "${compose_cmd[@]}" exec -T mw_private php maintenance/run.php eval.php >/dev/null
"${compose_cmd[@]}" exec -T mw_private php maintenance/run.php getText "Form:Shot记录" >/dev/null
"${compose_cmd[@]}" exec -T mw_private php maintenance/run.php getText "Template:Shot记录" >/dev/null
"${compose_cmd[@]}" exec -T mw_private php maintenance/run.php getText "Shot:表单新建" >/dev/null
"${compose_cmd[@]}" exec -T mariadb sh -lc \
  'mariadb -N -uroot -p"$(cat /run/secrets/db_root_password)" labwiki_private -e "SELECT COUNT(*) FROM page WHERE page_namespace = 0 AND page_title = '\''FAQ:知识助手使用说明'\'';" | grep -qx 1'
"${compose_cmd[@]}" exec -T assistant_api python -c "import langgraph"
"${compose_cmd[@]}" exec -T assistant_api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()"

check_http "${PUBLIC_URL}" public
check_http "${PRIVATE_URL}" private
check_http "${PRIVATE_URL%/}/tools/assistant/api/health" assistant-api
check_http "${PRIVATE_URL%/}/tools/rcf/" rcf-ui
check_http "${PRIVATE_URL%/}/tools/rcf/api/v1/health" rcf-api
check_http "${PRIVATE_URL%/}/tools/tps/" tps-ui
check_http "${PRIVATE_URL%/}/tools/tps/api/health" tps-api

printf '[ok] smoke test passed\n'
