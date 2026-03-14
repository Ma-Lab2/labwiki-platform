#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

compose_cmd=(docker compose -f compose.yaml)
if [[ "${LABWIKI_LOCAL_OVERRIDE:-false}" == "true" ]]; then
  compose_cmd+=(-f compose.override.yaml)
fi

check_http() {
  local url="$1"
  local label="$2"
  local code

  code="$(curl --noproxy '*' -k -s -o /dev/null -w '%{http_code}' "${url}")"
  case "${label}:${code}" in
    public:200|public:301|public:302|private:200|private:301|private:302|private:401|private:403|rcf-ui:200|rcf-api:200)
      printf '[ok] %s returned %s\n' "${label}" "${code}"
      ;;
    *)
      printf '[fail] %s returned %s for %s\n' "${label}" "${code}" "${url}" >&2
      exit 1
      ;;
  esac
}

"${compose_cmd[@]}" ps mariadb mw_public mw_private caddy_public caddy_private >/dev/null
"${compose_cmd[@]}" ps rcf_backend rcf_frontend >/dev/null

PUBLIC_URL="${PUBLIC_SMOKE_URL:-$("${compose_cmd[@]}" exec -T mw_public sh -lc 'printf %s "$MW_SERVER"')}"
PRIVATE_URL="${PRIVATE_SMOKE_URL:-$("${compose_cmd[@]}" exec -T mw_private sh -lc 'printf %s "$MW_SERVER"')}"
PUBLIC_NAME="$("${compose_cmd[@]}" exec -T mw_public sh -lc 'printf %s "$MW_SITE_NAME"')"
PRIVATE_NAME="$("${compose_cmd[@]}" exec -T mw_private sh -lc 'printf %s "$MW_SITE_NAME"')"

"${compose_cmd[@]}" exec -T mw_public sh -lc 'test -s /state/LocalSettings.php && test -w /var/www/html/images'
"${compose_cmd[@]}" exec -T mw_private sh -lc 'test -s /state/LocalSettings.php && test -w /var/www/html/images'
"${compose_cmd[@]}" exec -T mariadb sh -lc \
  'mariadb -uroot -p"$(cat /run/secrets/db_root_password)" -e "USE labwiki_public; SHOW TABLES;" >/dev/null && mariadb -uroot -p"$(cat /run/secrets/db_root_password)" -e "USE labwiki_private; SHOW TABLES;" >/dev/null'

"${compose_cmd[@]}" exec -T mw_public sh -lc "grep -F \"${PUBLIC_NAME}\" /state/LocalSettings.php >/dev/null"
"${compose_cmd[@]}" exec -T mw_private sh -lc "grep -F \"${PRIVATE_NAME}\" /state/LocalSettings.php >/dev/null"

check_http "${PUBLIC_URL}" public
check_http "${PRIVATE_URL}" private
check_http "${PRIVATE_URL%/}/tools/rcf/" rcf-ui
check_http "${PRIVATE_URL%/}/tools/rcf/api/v1/health" rcf-api

printf '[ok] smoke test passed\n'
