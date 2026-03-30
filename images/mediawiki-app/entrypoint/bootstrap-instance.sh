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

upsert_managed_block() {
  local marker="$1"
  local content="$2"
  local tmp_file=""
  local output_file=""

  tmp_file="$(mktemp)"
  output_file="$(mktemp)"

  if [[ -f "${LOCAL_SETTINGS}" ]]; then
    awk -v marker="${marker}" '
      BEGIN {
        skip = 0
      }
      $0 == "# " marker {
        skip = 1
        next
      }
      skip && /^# / {
        skip = 0
      }
      !skip {
        print
      }
    ' "${LOCAL_SETTINGS}" > "${tmp_file}"
  fi

  {
    cat "${tmp_file}"
    printf "\n# %s\n" "${marker}"
    printf "%s\n" "${content}"
  } > "${output_file}"

  mv "${output_file}" "${LOCAL_SETTINGS}"
  rm -f "${tmp_file}"
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

sync_private_vector_skin_preferences() {
  php <<'PHP'
<?php
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
$pass = trim(file_get_contents(getenv('MW_DB_PASS_FILE')));
$conn = new mysqli(
    getenv('MW_DB_SERVER'),
    getenv('MW_DB_USER'),
    $pass,
    getenv('MW_DB_NAME')
);
$sql = <<<SQL
UPDATE user_properties
SET up_value = 'vector-2022'
WHERE up_property = 'skin'
  AND up_value = 'vector'
SQL;
$conn->query($sql);
PHP
}

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
  if [[ "${existing_text}" =~ ^Page[[:space:]].*[[:space:]]does[[:space:]]not[[:space:]]exist\.$ ]]; then
    existing_text=""
  fi
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
  if [[ "${existing_text}" =~ ^Page[[:space:]].*[[:space:]]does[[:space:]]not[[:space:]]exist\.$ ]]; then
    existing_text=""
  fi
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

rebuild_cargo_tables_once() {
  local marker_name="$1"
  local marker_file="${STATE_DIR}/.${marker_name}"
  local table_name

  if [[ -f "${marker_file}" ]]; then
    return 0
  fi

  for table_name in \
    lab_terms \
    lab_devices \
    lab_mechanisms \
    lab_diagnostics \
    lab_literature_guides; do
    php extensions/Cargo/maintenance/cargoRecreateData.php --quiet --table="${table_name}"
  done
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

if [[ "${SITE_VARIANT}" == "private" ]]; then
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
\$labwikiCanonicalServer = '${MW_SERVER}';
\$labwikiAllowedServerHosts = [ 'localhost:8443' ];
if ( PHP_SAPI !== 'cli' ) {
  \$labwikiRequestHost = \$_SERVER['HTTP_HOST'] ?? '';
  if ( in_array( \$labwikiRequestHost, \$labwikiAllowedServerHosts, true ) ) {
    \$wgServer = 'http://' . \$labwikiRequestHost;
  } else {
    \$wgServer = \$labwikiCanonicalServer;
  }
}
EOF
)"
else
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
fi

if [[ "${SITE_VARIANT}" == "private" ]]; then
  THEME_STYLE_LIST="$(cat <<'EOF'
    'labwiki/theme/private.css',
    'labwiki/theme/base.css',
EOF
)"
else
  THEME_STYLE_LIST="$(cat <<'EOF'
    'labwiki/theme/base.css',
    'labwiki/theme/public.css',
EOF
)"
fi

THEME_BLOCK="$(cat <<EOF
\$wgResourceModules['ext.labwiki.theme.v20260328'] = [
  'styles' => [
${THEME_STYLE_LIST}
  ],
  'scripts' => [
    'labwiki/theme/${SITE_VARIANT}.js',
  ],
  'localBasePath' => '/var/www/html',
  'remoteBasePath' => \$wgResourceBasePath ?: '',
];
\$wgDefaultUserOptions['labwiki-private-theme'] = 'deep-space-window';
\$wgHooks['GetPreferences'][] = static function ( \$user, &\$preferences ) {
  if ( '${SITE_VARIANT}' !== 'private' ) {
    return true;
  }

  \$preferences['labwiki-private-theme'] = [
    'type' => 'select',
    'label' => '新外观主题',
    'options' => [
      '深空蓝窗' => 'deep-space-window',
      '极地银蓝' => 'polar-silver-blue',
      '青色波光' => 'cyan-tide-glow',
    ],
    'section' => 'rendering/skin/skin-prefs',
    'help' => '仅在新外观（Vector 2022）下生效。',
    'hide-if' => [ '!==', 'skin', 'vector-2022' ],
  ];

  return true;
};
\$wgHooks['BeforePageDisplay'][] = static function ( \$out, \$skin ) {
  if ( '${SITE_VARIANT}' === 'private' ) {
    \$currentSkin = \$skin->getSkinName();
    \$serverTheme = 'deep-space-window';
    if ( \$skin->getUser()->isRegistered() ) {
      \$storedTheme = (string)\MediaWiki\MediaWikiServices::getInstance()
        ->getUserOptionsLookup()
        ->getOption( \$skin->getUser(), 'labwiki-private-theme', 'deep-space-window' );
      if ( in_array( \$storedTheme, [ 'deep-space-window', 'polar-silver-blue', 'cyan-tide-glow' ], true ) ) {
        \$serverTheme = \$storedTheme;
      }
    }
    \$out->addHtmlClasses( [
      'labwiki-private',
      'labwiki-theme-' . \$serverTheme,
      'labwiki-skin-' . \$currentSkin,
    ] );
    \$appearanceSettingsUrl = \MediaWiki\SpecialPage\SpecialPage::getTitleFor( 'Preferences' )->getLocalURL() . '#mw-prefsection-rendering-skin';
    \$bootstrapConfig = json_encode(
      [
        'appearanceSettingsUrl' => \$appearanceSettingsUrl,
        'currentSkin' => \$currentSkin,
        'serverTheme' => \$serverTheme,
        'debugUser' => \$skin->getUser()->getName(),
      ],
      JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE
    );
    \$out->addHeadItem(
      'labwiki-theme-bootstrap',
      '<script>(function(){var cfg=' . \$bootstrapConfig . ';var fallback="deep-space-window";var allowed={"deep-space-window":1,"polar-silver-blue":1,"cyan-tide-glow":1};var cookieMatch=document.cookie.match(/(?:^|; )labwiki_private_theme_hint=([^;]+)/);var hintedTheme="";var theme=fallback;if(cookieMatch&&cookieMatch[1]){try{hintedTheme=decodeURIComponent(cookieMatch[1]);}catch(e){hintedTheme="";}}if(cfg.currentSkin==="vector-2022"){if(allowed[hintedTheme]){theme=hintedTheme;}else if(allowed[cfg.serverTheme]){theme=cfg.serverTheme;}}document.documentElement.setAttribute("data-labwiki-private","1");document.documentElement.setAttribute("data-labwiki-current-skin",cfg.currentSkin);document.documentElement.setAttribute("data-labwiki-appearance-settings-url",cfg.appearanceSettingsUrl);document.documentElement.setAttribute("data-labwiki-server-theme",cfg.serverTheme||"");document.documentElement.setAttribute("data-labwiki-theme-hint",hintedTheme||"");document.documentElement.setAttribute("data-labwiki-debug-user",cfg.debugUser||"");document.documentElement.setAttribute("data-labwiki-theme",theme);if(cfg.currentSkin==="vector-2022"&&allowed[theme]){document.cookie="labwiki_private_theme_hint="+encodeURIComponent(theme)+"; path=/; max-age=31536000; SameSite=Lax";}}());</script>'
    );
    \$out->addInlineStyle(
      'html[data-labwiki-private=\"1\"][data-labwiki-theme=\"deep-space-window\"],html.labwiki-private.labwiki-theme-deep-space-window{' .
      '--labwiki-critical-page-fill:#08112a;' .
      '--labwiki-critical-body-bg:radial-gradient(circle at 16% 18%, rgba(140, 193, 255, 0.16), transparent 20%),radial-gradient(circle at 82% 14%, rgba(101, 135, 255, 0.18), transparent 24%),linear-gradient(rgba(140, 188, 255, 0.04) 1px, transparent 1px),linear-gradient(90deg, rgba(140, 188, 255, 0.04) 1px, transparent 1px),linear-gradient(180deg, #08112a 0%, #101c42 42%, #081029 100%);' .
      '--labwiki-critical-overlay:radial-gradient(circle at 12% 20%, rgba(255, 255, 255, 0.82) 0 1px, transparent 1.7px),radial-gradient(circle at 72% 24%, rgba(175, 210, 255, 0.62) 0 1px, transparent 1.9px),radial-gradient(circle at 84% 72%, rgba(255, 255, 255, 0.7) 0 1px, transparent 1.8px),linear-gradient(180deg, rgba(255, 255, 255, 0.14), transparent 220px),radial-gradient(circle at top right, rgba(146, 207, 255, 0.14), transparent 26%);' .
      '--labwiki-critical-surface:rgba(244, 248, 255, 0.94);' .
      '--labwiki-critical-line:rgba(107, 140, 219, 0.2);' .
      '--labwiki-critical-line-strong:rgba(70, 111, 197, 0.36);' .
      '--labwiki-critical-accent:#2f6cf2;' .
      '--labwiki-critical-accent-strong:#1844ad;' .
      '--labwiki-critical-accent-soft:rgba(47, 108, 242, 0.12);' .
      '}' .
      'html[data-labwiki-private=\"1\"][data-labwiki-theme=\"polar-silver-blue\"],html.labwiki-private.labwiki-theme-polar-silver-blue{' .
      '--labwiki-critical-page-fill:#eef4fb;' .
      '--labwiki-critical-body-bg:radial-gradient(circle at 14% 18%, rgba(255, 255, 255, 0.32), transparent 18%),linear-gradient(rgba(123, 144, 170, 0.05) 1px, transparent 1px),linear-gradient(90deg, rgba(123, 144, 170, 0.05) 1px, transparent 1px),linear-gradient(180deg, #eef4fb 0%, #dfe7f1 100%);' .
      '--labwiki-critical-overlay:linear-gradient(180deg, rgba(255, 255, 255, 0.34), transparent 240px),radial-gradient(circle at top right, rgba(196, 214, 236, 0.3), transparent 24%);' .
      '--labwiki-critical-surface:rgba(248, 251, 255, 0.97);' .
      '--labwiki-critical-line:rgba(113, 135, 167, 0.18);' .
      '--labwiki-critical-line-strong:rgba(86, 108, 142, 0.28);' .
      '--labwiki-critical-accent:#5f7ca8;' .
      '--labwiki-critical-accent-strong:#425a7d;' .
      '--labwiki-critical-accent-soft:rgba(95, 124, 168, 0.12);' .
      '}' .
      'html[data-labwiki-private=\"1\"][data-labwiki-theme=\"cyan-tide-glow\"],html.labwiki-private.labwiki-theme-cyan-tide-glow{' .
      '--labwiki-critical-page-fill:#061329;' .
      '--labwiki-critical-body-bg:radial-gradient(circle at 18% 16%, rgba(38, 210, 235, 0.14), transparent 20%),radial-gradient(circle at 84% 18%, rgba(91, 150, 255, 0.12), transparent 24%),linear-gradient(rgba(54, 172, 197, 0.05) 1px, transparent 1px),linear-gradient(90deg, rgba(54, 172, 197, 0.05) 1px, transparent 1px),linear-gradient(180deg, #061329 0%, #0a203c 46%, #081628 100%);' .
      '--labwiki-critical-overlay:radial-gradient(circle at 12% 22%, rgba(255, 255, 255, 0.72) 0 1px, transparent 1.8px),radial-gradient(circle at 72% 28%, rgba(167, 242, 255, 0.52) 0 1px, transparent 2px),linear-gradient(120deg, rgba(152, 245, 255, 0.1) 0%, rgba(152, 245, 255, 0) 40%, rgba(152, 245, 255, 0.12) 70%, rgba(152, 245, 255, 0) 100%);' .
      '--labwiki-critical-surface:rgba(240, 251, 255, 0.93);' .
      '--labwiki-critical-line:rgba(63, 171, 192, 0.18);' .
      '--labwiki-critical-line-strong:rgba(42, 146, 167, 0.32);' .
      '--labwiki-critical-accent:#1da8c6;' .
      '--labwiki-critical-accent-strong:#0d6f84;' .
      '--labwiki-critical-accent-soft:rgba(29, 168, 198, 0.14);' .
      '}' .
      'html[data-labwiki-private=\"1\"],html.labwiki-private{background-color:var(--labwiki-critical-page-fill);background-image:var(--labwiki-critical-body-bg);background-size:24px 24px,24px 24px,auto;}' .
      'body.skin-vector-2022,body.skin-vector-legacy{background-color:var(--labwiki-critical-page-fill);background-image:var(--labwiki-critical-body-bg);background-size:24px 24px,24px 24px,auto;min-height:100vh;}' .
      'body.skin-vector-2022::before,body.skin-vector-legacy::before{content:\"\";position:fixed;inset:0;pointer-events:none;background:var(--labwiki-critical-overlay);}' .
      '.mw-page-container{max-width:min(1500px,calc(100vw - 34px));margin:16px auto 32px;background:var(--labwiki-critical-surface);border:1px solid var(--labwiki-critical-line);border-radius:20px;box-shadow:0 24px 64px rgba(20, 20, 20, 0.08);overflow:hidden;}' .
      '.vector-header-container,.vector-sticky-header-container,.vector-page-toolbar-container{background:transparent;}' .
      '.mw-header,.vector-page-toolbar{background:rgba(255, 253, 249, 0.92);border-bottom:1px solid var(--labwiki-critical-line);}' .
      '.mw-header{padding:12px 18px;}' .
      '.mw-logo,.mw-logo-container{gap:10px;}' .
      '.mw-logo img,.mw-logo-icon{width:20px;height:20px;border-radius:5px;opacity:0.9;}' .
      '.mw-logo-wordmark{font-size:0.98rem;line-height:1.2;font-weight:700;letter-spacing:0.02em;}' .
      '.vector-search-box{max-width:38rem;}' .
      '.cdx-text-input__input,.cdx-search-input__input,input[type=\"text\"],input[type=\"password\"],input[type=\"search\"],textarea,select{border-radius:10px;border:1px solid var(--labwiki-critical-line-strong);background:rgba(255, 255, 255, 0.9);box-shadow:inset 0 1px 0 rgba(255, 255, 255, 0.82);}' .
      '.cdx-text-input__input:focus,.cdx-search-input__input:focus,input[type=\"text\"]:focus,input[type=\"password\"]:focus,input[type=\"search\"]:focus,textarea:focus,select:focus{border-color:var(--labwiki-critical-accent);box-shadow:0 0 0 3px var(--labwiki-critical-accent-soft);outline:none;}' .
      'button.cdx-button--action-progressive,input[type=\"submit\"],button[type=\"submit\"]{border-radius:10px;border:1px solid var(--labwiki-critical-accent);background:var(--labwiki-critical-accent)!important;color:#fffaf2!important;box-shadow:none;}' .
      'button.cdx-button--action-progressive:hover,input[type=\"submit\"]:hover,button[type=\"submit\"]:hover{background:var(--labwiki-critical-accent-strong)!important;border-color:var(--labwiki-critical-accent-strong);}' .
      '.vector-appearance-landmark{display:flex!important;align-items:center;}' .
      '.labwiki-appearance-settings-link{display:flex;align-items:center;justify-content:center;width:32px;min-width:32px;height:32px;border-radius:10px;text-decoration:none;}' .
      '.labwiki-appearance-settings-link .vector-dropdown-label-text{display:none;}' .
      '#vector-page-titlebar-toc,#mw-panel-toc,#mw-panel-toc-list,.mw-table-of-contents-container.vector-toc-landmark,.vector-page-titlebar .vector-toc-landmark,.vector-sticky-pinned-container .vector-toc-landmark{display:none!important;}'
    );
  }
  \$out->addModuleStyles( 'ext.labwiki.theme.v20260328' );
  \$out->addModules( 'ext.labwiki.theme.v20260328' );
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
wfLoadExtension( 'Cargo' );
wfLoadExtension( 'PageForms' );
$wgDefaultUserOptions['usebetatoolbar'] = 1;
$wgDefaultUserOptions['usebetatoolbar-cgd'] = 1;
$wgDefaultUserOptions['wikieditor-preview'] = 1;
$wgDefaultUserOptions['wikieditor-publish'] = 1;
$wgMathEnableFormulaLinks = true;
EOF
)"

upsert_managed_block "LABWIKI_COMMON" "${COMMON_BLOCK}"
upsert_managed_block "LABWIKI_EDITOR_EXTENSIONS_V3" "${EDITOR_BLOCK}"
upsert_managed_block "LABWIKI_THEME_V1" "${THEME_BLOCK}"
upsert_managed_block "LABWIKI_RUNTIME_OVERRIDES_V5" "${RUNTIME_BLOCK}"

if [[ "${MW_PRIVATE_MODE:-false}" == "true" ]]; then
  PRIVATE_BLOCK="$(cat <<'EOF'
$wgGroupPermissions['*']['read'] = false;
$wgGroupPermissions['*']['edit'] = false;
$wgGroupPermissions['*']['createaccount'] = false;
$wgVectorDefaultSkinVersionForExistingAccounts = '2';
$wgVectorDefaultSkinVersionForNewAccounts = '2';
wfLoadExtension( 'LabAssistant' );
wfLoadExtension( 'LabAuth' );
wfLoadExtension( 'LabWorkbook' );
$wgLabAssistantApiBase = getenv( 'MW_ASSISTANT_API_BASE' ) ?: '/tools/assistant/api';
$wgLabAssistantDraftPrefix = getenv( 'MW_ASSISTANT_DRAFT_PREFIX' ) ?: '知识助手草稿';
EOF
)"
  upsert_managed_block "PRIVATE_WIKI_HARDENING_V2" "${PRIVATE_BLOCK}"
fi

ln -sf "${LOCAL_SETTINGS}" /var/www/html/LocalSettings.php
php maintenance/run.php update --quick

if [[ "${MW_PRIVATE_MODE:-false}" == "true" ]]; then
  sync_private_vector_skin_preferences
  import_seed_images_once "private/field-manual-20250723" "seed-images-field-manual-20250723-v1"
fi

seed_page_if_default "${MAIN_PAGE_TITLE}" "${SEED_ROOT}/${SITE_VARIANT}-mainpage.wiki"
seed_manifest_pages "${SEED_ROOT}/${SITE_VARIANT}-manifest.tsv"

if [[ "${MW_PRIVATE_MODE:-false}" == "true" ]]; then
  rebuild_cargo_tables_once "cargo-bootstrap-v5"
  seed_manifest_pages "${SEED_ROOT}/private-cargo-manifest.tsv"
fi

chmod 644 "${LOCAL_SETTINGS}"

exec "$@"
