#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${STATE_DIR:-/state}"
LOCAL_SETTINGS="${STATE_DIR}/LocalSettings.php"
SCRIPT_PATH="${MW_SCRIPT_PATH:-}"
THEME_ROOT="/var/www/html/labwiki/theme"
SEED_ROOT="/opt/labwiki/seed"
IMAGE_SEED_ROOT="/opt/labwiki/seed/uploads"
MAIN_PAGE_TITLE="${MW_MAIN_PAGE_TITLE:-首页}"

SITE_VARIANT="public"
if [[ "${MW_PRIVATE_MODE:-false}" == "true" ]]; then
  SITE_VARIANT="private"
fi

LOGO_PATH="/labwiki/theme/${SITE_VARIANT}-logo.svg"

required_env=(
  MW_DB_TYPE
  MW_DB_SERVER
  MW_DB_NAME
  MW_DB_USER
  MW_DB_PASS_FILE
  MW_ADMIN_USER
  MW_ADMIN_PASS_FILE
  MW_SERVER
  MW_SITE_NAME
)

for name in "${required_env[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 1
  fi
done

if [[ ! -f "${MW_DB_PASS_FILE}" ]]; then
  echo "Database password file not found: ${MW_DB_PASS_FILE}" >&2
  exit 1
fi

if [[ ! -f "${MW_ADMIN_PASS_FILE}" ]]; then
  echo "Admin password file not found: ${MW_ADMIN_PASS_FILE}" >&2
  exit 1
fi

mkdir -p "${STATE_DIR}" /var/www/html/images
cd /var/www/html

append_block_once() {
  local marker="$1"
  local content="$2"

  if [[ ! -f "${LOCAL_SETTINGS}" ]] || grep -Fq "${marker}" "${LOCAL_SETTINGS}"; then
    return 0
  fi

  {
    printf "\n# %s\n" "${marker}"
    printf "%s\n" "${content}"
  } >> "${LOCAL_SETTINGS}"
}

wait_for_db() {
  local attempts=30

  until php -r '
    mysqli_report(MYSQLI_REPORT_OFF);
    $pass = trim(file_get_contents(getenv("MW_DB_PASS_FILE")));
    $conn = @new mysqli(getenv("MW_DB_SERVER"), getenv("MW_DB_USER"), $pass, getenv("MW_DB_NAME"));
    exit($conn->connect_errno ? 1 : 0);
  '; do
    attempts=$((attempts - 1))
    if [[ "${attempts}" -le 0 ]]; then
      echo "Database did not become ready in time" >&2
      exit 1
    fi
    sleep 2
  done
}

wait_for_db

seed_page_if_default() {
  local title="$1"
  local seed_file="$2"
  local existing_text
  local legacy_hint=""

  if [[ ! -f "${seed_file}" ]]; then
    return 0
  fi

  case "${SITE_VARIANT}" in
    public)
      legacy_hint="公开研究档案"
      ;;
    private)
      legacy_hint="内部协作中枢"
      ;;
  esac

  existing_text="$(php maintenance/run.php getText "${title}" 2>/dev/null || true)"
  if [[ -n "${existing_text}" ]] \
    && ! grep -Fq "已安装MediaWiki" <<<"${existing_text}" \
    && ! grep -Fq "LABWIKI_MANAGED_PAGE" <<<"${existing_text}" \
    && [[ -z "${legacy_hint}" || "${existing_text}" != *"${legacy_hint}"* ]]; then
    return 0
  fi

  php maintenance/run.php edit \
    --summary="Seed labwiki landing page" \
    --user="${MW_ADMIN_USER}" \
    "${title}" < "${seed_file}"
}

seed_page_if_missing_or_managed() {
  local title="$1"
  local seed_file="$2"
  local existing_text

  if [[ ! -f "${seed_file}" ]]; then
    return 0
  fi

  existing_text="$(php maintenance/run.php getText "${title}" 2>/dev/null || true)"
  if [[ -n "${existing_text}" ]] && ! grep -Fq "LABWIKI_MANAGED_PAGE" <<<"${existing_text}"; then
    return 0
  fi

  php maintenance/run.php edit \
    --summary="Seed labwiki content skeleton" \
    --user="${MW_ADMIN_USER}" \
    "${title}" < "${seed_file}"
}

seed_manifest_pages() {
  local manifest_file="$1"
  local title=""
  local relative_path=""

  if [[ ! -f "${manifest_file}" ]]; then
    return 0
  fi

  while IFS=$'\t' read -r title relative_path; do
    [[ -z "${title}" || -z "${relative_path}" ]] && continue
    seed_page_if_missing_or_managed "${title}" "${SEED_ROOT}/${relative_path}"
  done < "${manifest_file}"
}

import_seed_images_once() {
  local relative_dir="$1"
  local marker_name="$2"
  local image_dir="${IMAGE_SEED_ROOT}/${relative_dir}"
  local marker_file="${STATE_DIR}/.${marker_name}"

  if [[ ! -d "${image_dir}" ]] || [[ -f "${marker_file}" ]]; then
    return 0
  fi

  php maintenance/run.php importImages \
    --summary="Seed labwiki image assets" \
    --search-recursively \
    --skip-dupes \
    --user="${MW_ADMIN_USER}" \
    "${image_dir}"

  touch "${marker_file}"
}

if [[ ! -s "${LOCAL_SETTINGS}" ]]; then
  php maintenance/run.php install \
    --confpath="${STATE_DIR}" \
    --dbtype="${MW_DB_TYPE}" \
    --dbserver="${MW_DB_SERVER}" \
    --dbname="${MW_DB_NAME}" \
    --dbuser="${MW_DB_USER}" \
    --dbpassfile="${MW_DB_PASS_FILE}" \
    --server="${MW_SERVER}" \
    --scriptpath="${SCRIPT_PATH}" \
    --lang="${MW_LANG:-zh-cn}" \
    --passfile="${MW_ADMIN_PASS_FILE}" \
    "${MW_SITE_NAME}" "${MW_ADMIN_USER}"
fi

RUNTIME_BLOCK="$(cat <<EOF
\$wgServer = '${MW_SERVER}';
\$wgScriptPath = '${SCRIPT_PATH}';
\$wgResourceBasePath = \$wgScriptPath;
\$wgSitename = '${MW_SITE_NAME}';
\$wgLogos = [
  '1x' => '${LOGO_PATH}',
  'icon' => '${LOGO_PATH}',
];
\$wgEnableUploads = true;
EOF
)"

THEME_BLOCK="$(cat <<EOF
\$wgResourceModules['ext.labwiki.theme'] = [
  'styles' => [
    'labwiki/theme/base.css',
    'labwiki/theme/${SITE_VARIANT}.css',
  ],
  'scripts' => [
    'labwiki/theme/${SITE_VARIANT}.js',
  ],
  'localBasePath' => '/var/www/html',
  'remoteBasePath' => \$wgResourceBasePath ?: '',
];
\$wgHooks['BeforePageDisplay'][] = static function ( \$out, \$skin ) {
  \$out->addModuleStyles( 'ext.labwiki.theme' );
  \$out->addModules( 'ext.labwiki.theme' );
  return true;
};
EOF
)"

COMMON_BLOCK="$(cat <<EOF
wfLoadExtension( 'VisualEditor' );
\$wgGroupPermissions['user']['writeapi'] = true;
\$wgMainCacheType = CACHE_ACCEL;
\$wgParserCacheType = CACHE_ACCEL;
\$wgSessionCacheType = CACHE_ACCEL;
\$wgLanguageCode = '${MW_LANG:-zh-cn}';
\$wgFileExtensions = array_values( array_unique( array_merge( \$wgFileExtensions, [ 'csv', 'tsv', 'xlsx', 'ods', 'pdf', 'txt', 'md' ] ) ) );
EOF
)"

EDITOR_BLOCK="$(cat <<'EOF'
wfLoadExtension( 'Math' );
wfLoadExtension( 'Cite' );
wfLoadExtension( 'WikiEditor' );
wfLoadExtension( 'TemplateData' );
wfLoadExtension( 'PageForms' );
$wgDefaultUserOptions['usebetatoolbar'] = 1;
$wgDefaultUserOptions['usebetatoolbar-cgd'] = 1;
$wgDefaultUserOptions['wikieditor-preview'] = 1;
$wgDefaultUserOptions['wikieditor-publish'] = 1;
$wgMathEnableFormulaLinks = true;
EOF
)"

append_block_once "LABWIKI_COMMON" "${COMMON_BLOCK}"
append_block_once "LABWIKI_EDITOR_EXTENSIONS_V2" "${EDITOR_BLOCK}"
append_block_once "LABWIKI_THEME_V1" "${THEME_BLOCK}"
append_block_once "LABWIKI_RUNTIME_OVERRIDES_V5" "${RUNTIME_BLOCK}"

if [[ "${MW_PRIVATE_MODE:-false}" == "true" ]]; then
  PRIVATE_BLOCK="$(cat <<'EOF'
$wgGroupPermissions['*']['read'] = false;
$wgGroupPermissions['*']['edit'] = false;
$wgGroupPermissions['*']['createaccount'] = false;
EOF
)"
  append_block_once "PRIVATE_WIKI_HARDENING" "${PRIVATE_BLOCK}"
fi

if [[ "${MW_PRIVATE_MODE:-false}" == "true" ]]; then
  import_seed_images_once "private/field-manual-20250723" "seed-images-field-manual-20250723-v1"
fi

seed_page_if_default "${MAIN_PAGE_TITLE}" "${SEED_ROOT}/${SITE_VARIANT}-mainpage.wiki"
seed_manifest_pages "${SEED_ROOT}/${SITE_VARIANT}-manifest.tsv"

chmod 600 "${LOCAL_SETTINGS}"
ln -sf "${LOCAL_SETTINGS}" /var/www/html/LocalSettings.php

exec "$@"
