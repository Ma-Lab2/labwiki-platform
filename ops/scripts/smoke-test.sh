#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

PUBLIC_URL="${PUBLIC_SMOKE_URL:-https://localhost}"
PRIVATE_URL="${PRIVATE_SMOKE_URL:-https://127.0.0.1:8443}"
PUBLIC_NAME="${PUBLIC_SITE_NAME:-Lab Public Wiki}"
PRIVATE_NAME="${PRIVATE_SITE_NAME:-Lab Internal Wiki}"

check_http() {
  local url="$1"
  local label="$2"
  local code

  code="$(curl -k -s -o /dev/null -w '%{http_code}' "${url}")"
  case "${label}:${code}" in
    public:200|public:302|private:200|private:302|private:401|private:403)
      printf '[ok] %s returned %s\n' "${label}" "${code}"
      ;;
    *)
      printf '[fail] %s returned %s for %s\n' "${label}" "${code}" "${url}" >&2
      exit 1
      ;;
  esac
}

docker compose ps mariadb mw_public mw_private caddy_public caddy_private >/dev/null

docker compose exec -T mw_public sh -lc 'test -s /state/LocalSettings.php && test -w /var/www/html/images'
docker compose exec -T mw_private sh -lc 'test -s /state/LocalSettings.php && test -w /var/www/html/images'
docker compose exec -T mariadb sh -lc \
  'mariadb -uroot -p"$(cat /run/secrets/db_root_password)" -e "USE labwiki_public; SHOW TABLES;" >/dev/null && mariadb -uroot -p"$(cat /run/secrets/db_root_password)" -e "USE labwiki_private; SHOW TABLES;" >/dev/null'

docker compose exec -T mw_public sh -lc "grep -F \"${PUBLIC_NAME}\" /state/LocalSettings.php >/dev/null"
docker compose exec -T mw_private sh -lc "grep -F \"${PRIVATE_NAME}\" /state/LocalSettings.php >/dev/null"

check_http "${PUBLIC_URL}" public
check_http "${PRIVATE_URL}" private

printf '[ok] smoke test passed\n'
