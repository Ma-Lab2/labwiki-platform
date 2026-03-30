import importlib.util
import json
import pathlib
import re
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ops" / "scripts" / "check_mediawiki_resource_sync.py"
SPEC = importlib.util.spec_from_file_location("check_mediawiki_resource_sync", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ResourceSyncTests(unittest.TestCase):
    def test_build_default_manifest_includes_core_private_wiki_resources(self) -> None:
        manifest = MODULE.build_default_manifest(ROOT)
        host_paths = {
            item.host_path.relative_to(ROOT).as_posix(): item.container_path
            for item in manifest
        }

        self.assertIn(
            "images/mediawiki-app/theme/base.css",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/theme/private.css",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/theme/private.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/includes/Hooks.php",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.asset-version.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.attachment-utils.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.pdf-reader-utils.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.pdf-ingest-utils.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.session-export-utils.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell-utils.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.css",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/extension.json",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.editor-utils.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAuth/modules/ext.labauth.admin.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabAuth/modules/ext.labauth.ui.css",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabWorkbook/extension.json",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabWorkbook/modules/ext.labworkbook.ui.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/extensions/LabWorkbook/modules/ext.labworkbook.utils.js",
            host_paths,
        )
        self.assertIn(
            "images/mediawiki-app/entrypoint/bootstrap-instance.sh",
            host_paths,
        )

    def test_compare_manifest_marks_missing_and_mismatched_files(self) -> None:
        manifest = [
            MODULE.ManifestItem(
                host_path=ROOT / "images" / "mediawiki-app" / "extensions" / "LabAssistant" / "extension.json",
                container_path="/var/www/html/extensions/LabAssistant/extension.json",
            ),
            MODULE.ManifestItem(
                host_path=ROOT / "images" / "mediawiki-app" / "entrypoint" / "bootstrap-instance.sh",
                container_path="/usr/local/bin/bootstrap-instance.sh",
            ),
        ]

        host_hashes = {
            manifest[0].host_path: "abc",
            manifest[1].host_path: "def",
        }
        container_hashes = {
            manifest[0].container_path: "abc",
        }

        records = MODULE.compare_manifest(manifest, host_hashes, container_hashes)

        self.assertEqual(records[0].status, "ok")
        self.assertEqual(records[1].status, "missing")

        container_hashes[manifest[1].container_path] = "zzz"
        records = MODULE.compare_manifest(manifest, host_hashes, container_hashes)
        self.assertEqual(records[1].status, "drift")

    def test_bootstrap_keeps_localsettings_php_fpm_readable(self) -> None:
        script = (
            ROOT / "images" / "mediawiki-app" / "entrypoint" / "bootstrap-instance.sh"
        ).read_text(encoding="utf-8")

        self.assertRegex(
            script,
            re.compile(r'chmod\s+64[04]\s+"\$\{LOCAL_SETTINGS\}"'),
        )

    def test_labauth_before_page_display_hook_uses_global_skin_type(self) -> None:
        hooks_php = (
            ROOT / "images" / "mediawiki-app" / "extensions" / "LabAuth" / "includes" / "Hooks.php"
        ).read_text(encoding="utf-8")

        self.assertIn("use Skin;", hooks_php)
        self.assertNotIn("use MediaWiki\\Skin\\Skin;", hooks_php)

    def test_labauth_registers_special_page_before_execute_hook(self) -> None:
        extension_json = json.loads(
            (
                ROOT / "images" / "mediawiki-app" / "extensions" / "LabAuth" / "extension.json"
            ).read_text(encoding="utf-8")
        )

        hooks = extension_json.get("Hooks", {})
        self.assertIn("SpecialPageBeforeExecute", hooks)

    def test_labauth_signup_module_is_style_only(self) -> None:
        extension_json = json.loads(
            (
                ROOT / "images" / "mediawiki-app" / "extensions" / "LabAuth" / "extension.json"
            ).read_text(encoding="utf-8")
        )

        signup_module = extension_json["ResourceModules"]["ext.labauth.signup"]
        self.assertNotIn("scripts", signup_module)
        self.assertEqual(signup_module.get("styles"), ["modules/ext.labauth.ui.css"])

    def test_labauth_whitelists_lab_login_page(self) -> None:
        hooks_php = (
            ROOT / "images" / "mediawiki-app" / "extensions" / "LabAuth" / "includes" / "Hooks.php"
        ).read_text(encoding="utf-8")

        self.assertIn("$title->isSpecial( 'LabLogin' )", hooks_php)

    def test_private_theme_picker_is_not_global_floating_ui(self) -> None:
        private_css = (
            ROOT / "images" / "mediawiki-app" / "theme" / "private.css"
        ).read_text(encoding="utf-8")

        self.assertNotIn(".labwiki-theme-picker {", private_css)
        self.assertNotIn("position: fixed;", private_css)

    def test_private_theme_repuposes_vector_appearance_slot_as_settings_shortcut(self) -> None:
        private_css = (
            ROOT / "images" / "mediawiki-app" / "theme" / "private.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".vector-appearance-landmark", private_css)
        self.assertIn("#vector-appearance-dropdown-label.labwiki-appearance-settings-link", private_css)
        self.assertIn("#vector-appearance-dropdown .vector-dropdown-content", private_css)
        self.assertIn("display: flex !important;", private_css)
        self.assertIn(".vector-dropdown-label-text", private_css)

    def test_private_theme_js_deduplicates_and_resets_drawer_state(self) -> None:
        private_js = (
            ROOT / "images" / "mediawiki-app" / "theme" / "private.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn("document.querySelector( '.labwiki-theme-picker' )", private_js)
        self.assertNotIn("document.body.appendChild( picker );", private_js)
        self.assertIn("Special:参数设置#mw-prefsection-rendering-skin", private_js)
        self.assertIn("document.querySelector( '#vector-main-menu-unpinned-container' )", private_js)
        self.assertIn("wrapper.classList.add( 'labwiki-sidebar-shell--dropdown' );", private_js)
        self.assertIn("new MutationObserver( function () {", private_js)
        self.assertIn("useskin=vector", private_js)
        self.assertIn("data-labwiki-appearance-bound", private_js)
        self.assertIn("var MENU_GROUPS = {", private_js)
        self.assertIn("var DEFAULT_MENU_STATE = {", private_js)
        self.assertIn("setSectionExpanded", private_js)
        self.assertIn("aria-expanded", private_js)
        self.assertIn("matchesCurrentLocation", private_js)
        self.assertIn("getCurrentPageCandidates", private_js)
        self.assertIn("new URL( href, window.location.origin )", private_js)
        self.assertIn("renameKnowledgeTreeTrigger", private_js)
        self.assertIn("vector-main-menu-dropdown-label", private_js)
        self.assertIn("知识树", private_js)
        self.assertIn("scheduleInjectedUiRefresh", private_js)
        self.assertIn("setNodeTextIfNeeded", private_js)
        self.assertIn("setAttributeIfNeeded", private_js)
        self.assertIn("window.requestAnimationFrame( function () {", private_js)
        self.assertIn("var THEME_HINT_COOKIE = 'labwiki_private_theme_hint';", private_js)
        self.assertIn("document.cookie = THEME_HINT_COOKIE + '=' + encodeURIComponent( themeId )", private_js)
        self.assertIn("function readThemeHint()", private_js)
        self.assertIn("function syncThemeFromUserOptions()", private_js)
        self.assertIn("mw.user.options.get( 'labwiki-private-theme' )", private_js)
        self.assertIn("mw.loader.using( 'user.options' ).then( function () {", private_js)
        self.assertIn("var initialTheme = document.documentElement.getAttribute( 'data-labwiki-theme' );", private_js)
        self.assertIn("if ( initialTheme ) {", private_js)
        self.assertIn("initialTheme = readThemeHint();", private_js)
        self.assertNotIn("target.id === 'vector-main-menu-unpinned-container' &&", private_js)
        self.assertNotIn("wrapper.appendChild( clone );", private_js)
        self.assertNotIn("setGroupExpanded", private_js)
        self.assertNotIn("closeSectionGroups", private_js)
        self.assertNotIn("renderGroup(", private_js)
        self.assertNotIn("group:", private_js)
        self.assertNotIn("document.querySelectorAll( '#vector-main-menu-dropdown label, #vector-main-menu-dropdown button' )", private_js)
        self.assertNotIn("node.textContent = '知识树';", private_js)
        self.assertNotIn("document.documentElement.getAttribute( 'data-labwiki-theme' ) || DEFAULT_THEME", private_js)

    def test_labassistant_ui_describes_controlled_section_commit(self) -> None:
        ui_js = (
            ROOT / "images" / "mediawiki-app" / "extensions" / "LabAssistant" / "modules" / "ext.labassistant.ui.js"
        ).read_text(encoding="utf-8")

        self.assertIn("当前页若支持助手填充模块，我可以先生成区块预览，你确认后再提交。", ui_js)
        self.assertIn("function getOperationPreview( result ) {", ui_js)
        self.assertIn("function getOperationResult( result ) {", ui_js)
        self.assertIn("state.currentResult.operation_preview = body;", ui_js)
        self.assertIn("state.currentResult.operation_result = body;", ui_js)
        self.assertIn("区块：", ui_js)
        self.assertIn("label: '操作'", ui_js)
        self.assertIn("defaultSectionId: 'operation'", ui_js)
        self.assertIn("getOperationPreview( result ) || getOperationResult( result )", ui_js)
        self.assertIn("代我编辑这个模块", ui_js)
        self.assertIn("applyManagedPageSectionBody", ui_js)
        self.assertIn("function renderOperationCard( result, rerender ) {", ui_js)

    def test_labassistant_ui_migrates_stored_gpt_mini_preference_to_gpt_5_4(self) -> None:
        ui_js = (
            ROOT / "images" / "mediawiki-app" / "extensions" / "LabAssistant" / "modules" / "ext.labassistant.ui.js"
        ).read_text(encoding="utf-8")
        asset_version = (
            ROOT / "images" / "mediawiki-app" / "extensions" / "LabAssistant" / "modules" / "ext.labassistant.asset-version.js"
        ).read_text(encoding="utf-8")

        self.assertIn("gpt-5.4-mini", ui_js)
        self.assertIn("gpt-5.4", ui_js)
        self.assertIn("MODEL_PREF_VERSION =", ui_js)
        self.assertRegex(asset_version, r"2026-03-29-.*gpt54")

    def test_playwright_managed_page_write_check_script_exists(self) -> None:
        script = (
            ROOT / "ops" / "scripts" / "playwright-private-managed-page-write-check.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("Meeting:%E4%BC%9A%E8%AE%AE%E5%85%A5%E5%8F%A3", script)
        self.assertIn("FAQ:%E5%B8%B8%E8%A7%81%E9%97%AE%E9%A2%98%E5%85%A5%E5%8F%A3", script)
        self.assertIn("Project:%E9%A1%B9%E7%9B%AE%E6%80%BB%E8%A7%88", script)
        self.assertIn("/write/commit", script)
        self.assertIn("确认提交", script)

    def test_playwright_assistant_operation_check_script_exists(self) -> None:
        script = (
            ROOT / "ops" / "scripts" / "playwright-private-assistant-operation-check.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("/chat", script)
        self.assertIn("operation_preview", script)
        self.assertIn("buildDraftHandoffStorageKey", script)
        self.assertIn("#wpTextbox1", script)
        self.assertIn("把刚加的这条使用规则删掉", script)
        self.assertIn("把使用规则里", script)
        self.assertIn("改成更正式的写法", script)

    def test_base_button_style_excludes_theme_controls(self) -> None:
        base_css = (
            ROOT / "images" / "mediawiki-app" / "theme" / "base.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".cdx-button--action-progressive,", base_css)
        self.assertIn(".mw-ui-button.mw-ui-progressive,", base_css)
        self.assertIn(".oo-ui-buttonElement-button.oo-ui-flaggedElement-progressive,", base_css)
        self.assertIn("button[type=\"submit\"] {", base_css)
        self.assertIn("button[type=\"submit\"]:hover {", base_css)
        self.assertNotIn(
            "button:not(.labwiki-theme-toggle):not(.labwiki-theme-card):not(.labwiki-theme-backdrop)",
            base_css,
        )
        self.assertIn(".vector-page-toolbar .selected a,", base_css)
        self.assertIn(".vector-page-toolbar [aria-current=\"page\"] {", base_css)
        self.assertIn("pointer-events: none;", base_css)
        self.assertIn("cursor: default;", base_css)

    def test_private_dropdown_shell_has_explicit_layout(self) -> None:
        private_css = (
            ROOT / "images" / "mediawiki-app" / "theme" / "private.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".labwiki-sidebar-shell--dropdown {", private_css)
        self.assertIn("position: static;", private_css)
        self.assertIn("width: min(22rem, calc(100vw - 32px));", private_css)
        self.assertIn("max-height: calc(100dvh - 7.5rem);", private_css)
        self.assertIn("padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));", private_css)
        self.assertIn("#vector-main-menu-unpinned-container > #vector-main-menu {", private_css)
        self.assertIn("display: none;", private_css)
        self.assertNotIn("max-height: min(70vh, 42rem);", private_css)
        self.assertIn(".vector-page-titlebar .vector-toc-landmark {", private_css)
        self.assertIn("display: none !important;", private_css)
        self.assertIn("#mw-panel-toc,", private_css)
        self.assertIn(".mw-table-of-contents-container.vector-toc-landmark {", private_css)
        self.assertNotIn(":root,\nhtml[data-labwiki-private=\"1\"][data-labwiki-theme=\"deep-space-window\"] {", private_css)
        self.assertIn(
            'html[data-labwiki-private="1"][data-labwiki-theme="deep-space-window"],\nhtml.labwiki-private.labwiki-theme-deep-space-window {',
            private_css,
        )
        self.assertIn(
            'html[data-labwiki-private="1"][data-labwiki-theme="polar-silver-blue"],\nhtml.labwiki-private.labwiki-theme-polar-silver-blue {',
            private_css,
        )
        self.assertIn(
            'html[data-labwiki-private="1"][data-labwiki-theme="cyan-tide-glow"],\nhtml.labwiki-private.labwiki-theme-cyan-tide-glow {',
            private_css,
        )
        self.assertNotIn('.mw-logo-wordmark::before {\n  content: "实验运行台账";\n}', private_css)

    def test_private_sidebar_uses_accordion_classes(self) -> None:
        private_css = (
            ROOT / "images" / "mediawiki-app" / "theme" / "private.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".labwiki-sidebar-accordion {", private_css)
        self.assertIn(".labwiki-sidebar-section-toggle {", private_css)
        self.assertIn(".labwiki-sidebar-links {", private_css)
        self.assertIn(".labwiki-sidebar-link.is-active {", private_css)
        self.assertNotIn(".labwiki-sidebar-group-toggle {", private_css)

    def test_bootstrap_pins_private_vector_defaults_to_modern_skin(self) -> None:
        script = (
            ROOT / "images" / "mediawiki-app" / "entrypoint" / "bootstrap-instance.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("$wgResourceModules['ext.labwiki.theme.v20260328'] = [", script)
        self.assertIn("$out->addModuleStyles( 'ext.labwiki.theme.v20260328' );", script)
        self.assertIn("$out->addModules( 'ext.labwiki.theme.v20260328' );", script)
        self.assertNotIn("$wgResourceModules['ext.labwiki.theme'] = [", script)
        self.assertIn("$wgVectorDefaultSkinVersionForExistingAccounts = '2';", script)
        self.assertIn("$wgVectorDefaultSkinVersionForNewAccounts = '2';", script)
        self.assertIn("if [[ \"${SITE_VARIANT}\" == \"private\" ]]; then", script)
        self.assertIn("'labwiki/theme/private.css',", script)
        self.assertIn("'labwiki/theme/base.css',", script)
        self.assertIn("'labwiki/theme/public.css',", script)

    def test_bootstrap_migrates_private_users_off_legacy_vector(self) -> None:
        script = (
            ROOT / "images" / "mediawiki-app" / "entrypoint" / "bootstrap-instance.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("UPDATE user_properties", script)
        self.assertIn("up_property = 'skin'", script)
        self.assertIn("up_value = 'vector-2022'", script)

    def test_bootstrap_inlines_private_theme_bootstrap(self) -> None:
        script = (
            ROOT / "images" / "mediawiki-app" / "entrypoint" / "bootstrap-instance.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("labwiki-theme-bootstrap", script)
        self.assertIn("labwiki-private-theme", script)
        self.assertIn("data-labwiki-private", script)
        self.assertIn("data-labwiki-theme", script)
        self.assertIn("data-labwiki-server-theme", script)
        self.assertIn("data-labwiki-theme-hint", script)
        self.assertIn("data-labwiki-debug-user", script)
        self.assertIn("addHtmlClasses( [", script)
        self.assertIn("'labwiki-private'", script)
        self.assertIn("'labwiki-theme-' . \\$serverTheme", script)
        self.assertIn('var fallback="deep-space-window";', script)
        self.assertIn('labwiki_private_theme_hint', script)
        self.assertIn('var cookieMatch=document.cookie.match(/(?:^|; )labwiki_private_theme_hint=([^;]+)/);', script)
        self.assertIn('if(allowed[hintedTheme]){theme=hintedTheme;}', script)
        self.assertIn('document.cookie="labwiki_private_theme_hint="+encodeURIComponent(theme)+"; path=/; max-age=31536000; SameSite=Lax";', script)
        self.assertNotIn(':root,html[data-labwiki-private=\\"1\\"][data-labwiki-theme=\\"deep-space-window\\"]{', script)
        self.assertIn('html[data-labwiki-private=\\"1\\"][data-labwiki-theme=\\"deep-space-window\\"],html.labwiki-private.labwiki-theme-deep-space-window{', script)
        self.assertIn('html[data-labwiki-private=\\"1\\"][data-labwiki-theme=\\"polar-silver-blue\\"],html.labwiki-private.labwiki-theme-polar-silver-blue{', script)
        self.assertIn('html[data-labwiki-private=\\"1\\"][data-labwiki-theme=\\"cyan-tide-glow\\"],html.labwiki-private.labwiki-theme-cyan-tide-glow{', script)
        self.assertIn('--labwiki-critical-page-fill:#eef4fb;', script)
        self.assertIn('html[data-labwiki-private=\\"1\\"],html.labwiki-private{background-color:var(--labwiki-critical-page-fill);background-image:var(--labwiki-critical-body-bg);background-size:24px 24px,24px 24px,auto;}', script)
        self.assertIn("addInlineStyle", script)
        self.assertIn("--labwiki-critical-body-bg", script)
        self.assertIn("--labwiki-critical-accent", script)
        self.assertIn(".mw-page-container{max-width:min(1500px,calc(100vw - 34px));", script)
        self.assertIn(".vector-header-container,.vector-sticky-header-container,.vector-page-toolbar-container", script)
        self.assertIn(".mw-header,.vector-page-toolbar{background:rgba(255, 253, 249, 0.92);", script)
        self.assertIn(".vector-search-box{max-width:38rem;}", script)
        self.assertIn('button.cdx-button--action-progressive,input[type=\\"submit\\"],button[type=\\"submit\\"]{', script)
        self.assertNotIn(".mw-logo-wordmark::before", script)
        self.assertNotIn(".cdx-button,.mw-ui-button,.oo-ui-buttonElement-button", script)

    def test_base_theme_styles_keep_wordmark_text_and_narrow_button_scope(self) -> None:
        base_css = (
            ROOT / "images" / "mediawiki-app" / "theme" / "base.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".mw-logo-wordmark {", base_css)
        self.assertIn("font-size: 0.98rem;", base_css)
        self.assertNotIn(".mw-logo-wordmark::before {", base_css)
        self.assertIn(".cdx-button--action-progressive,", base_css)
        self.assertIn(".mw-ui-button.mw-ui-progressive,", base_css)
        self.assertIn(".oo-ui-buttonElement-button.oo-ui-flaggedElement-progressive,", base_css)
        self.assertIn("button[type=\"submit\"] {", base_css)
        self.assertNotIn("button:not(.labwiki-theme-toggle):not(.labwiki-theme-card):not(.labwiki-theme-backdrop)", base_css)

    def test_labassistant_composer_sticks_to_bottom_of_workspace(self) -> None:
        assistant_css = (
            ROOT
            / "images"
            / "mediawiki-app"
            / "extensions"
            / "LabAssistant"
            / "modules"
            / "ext.labassistant.ui.css"
        ).read_text(encoding="utf-8")

        self.assertIn(".labassistant-main-column {", assistant_css)
        self.assertIn("grid-template-rows: auto auto minmax(0, 1fr) auto;", assistant_css)
        self.assertIn("min-height: 100%;", assistant_css)
        self.assertIn(".labassistant-composer {", assistant_css)
        self.assertIn("margin-top: auto;", assistant_css)
        self.assertIn("position: sticky;", assistant_css)
        self.assertIn("bottom: 0;", assistant_css)

    def test_labassistant_compact_workspace_collapses_process_after_answer(self) -> None:
        assistant_js = (
            ROOT
            / "images"
            / "mediawiki-app"
            / "extensions"
            / "LabAssistant"
            / "modules"
            / "ext.labassistant.ui.js"
        ).read_text(encoding="utf-8")
        assistant_css = (
            ROOT
            / "images"
            / "mediawiki-app"
            / "extensions"
            / "LabAssistant"
            / "modules"
            / "ext.labassistant.ui.css"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "var isOpen = !!( ( isPending && !result.answer ) || getOperationPreview( result ) || getOperationResult( result ) );",
            assistant_js,
        )
        self.assertIn(".labassistant-workspace.is-drawer .labassistant-transcript,", assistant_css)
        self.assertIn("padding-bottom: 104px;", assistant_css)

    def test_labassistant_drawer_history_can_resume_session(self) -> None:
        assistant_js = (
            ROOT
            / "images"
            / "mediawiki-app"
            / "extensions"
            / "LabAssistant"
            / "modules"
            / "ext.labassistant.ui.js"
        ).read_text(encoding="utf-8")

        self.assertIn("搜索任意历史会话，点开继续对话；导出放在右侧。", assistant_js)
        self.assertIn("className: 'labassistant-history-open'", assistant_js)
        self.assertIn("openButton.addEventListener( 'click', function () {", assistant_js)
        self.assertIn("loadHistorySession( item );", assistant_js)
        self.assertIn("className: 'labassistant-history-item is-resumable'", assistant_js)

    def test_bootstrap_registers_private_theme_preference_and_shortcut(self) -> None:
        script = (
            ROOT / "images" / "mediawiki-app" / "entrypoint" / "bootstrap-instance.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("$wgDefaultUserOptions['labwiki-private-theme'] = 'deep-space-window';", script)
        self.assertIn("$wgHooks['GetPreferences'][]", script)
        self.assertIn("'labwiki-private-theme'", script)
        self.assertIn("section' => 'rendering/skin", script)
        self.assertIn("labwiki-appearance-settings-link", script)
        self.assertIn("mw-prefsection-rendering-skin", script)
        self.assertIn("data-labwiki-appearance-settings-url", script)
        self.assertIn("\\MediaWiki\\SpecialPage\\SpecialPage::getTitleFor( 'Preferences' )", script)
        self.assertIn("'debugUser' =>", script)
        self.assertIn("getUser()->getName()", script)

    def test_bootstrap_uses_current_skin_when_bootstrapping_private_theme(self) -> None:
        script = (
            ROOT / "images" / "mediawiki-app" / "entrypoint" / "bootstrap-instance.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("getUserOptionsLookup()", script)
        self.assertIn("'labwiki-private-theme', 'deep-space-window'", script)
        self.assertIn("data-labwiki-current-skin", script)
        self.assertIn("vector-2022", script)
        self.assertIn("vector", script)

    def test_private_runtime_is_canonicalized_to_localhost(self) -> None:
        script = (
            ROOT / "images" / "mediawiki-app" / "entrypoint" / "bootstrap-instance.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("\\$labwikiAllowedServerHosts = [ 'localhost:8443' ];", script)
        self.assertNotIn("192.168.1.2:8443", script)

    def test_private_override_uses_localhost_for_private_services(self) -> None:
        override_text = (ROOT / "compose.override.yaml").read_text(encoding="utf-8")

        self.assertIn("ASSISTANT_WIKI_URL: http://localhost:8443", override_text)
        self.assertIn("ASSISTANT_WIKI_API_HOST_HEADER: localhost", override_text)
        self.assertIn("ASSISTANT_CORS_ALLOWED_ORIGINS: http://localhost:8443", override_text)
        self.assertIn("MW_SERVER: http://localhost:8443", override_text)
        self.assertIn("PRIVATE_HOST: localhost", override_text)
        self.assertNotIn("ASSISTANT_WIKI_URL: http://192.168.1.2:8443", override_text)
        self.assertNotIn("ASSISTANT_WIKI_API_HOST_HEADER: 192.168.1.2", override_text)
        self.assertNotIn("PRIVATE_HOST: 192.168.1.2", override_text)

    def test_private_caddy_redirects_all_noncanonical_hosts_to_private_host(self) -> None:
        caddy_text = (ROOT / "ops" / "caddy" / "Caddyfile.private.local").read_text(encoding="utf-8")

        self.assertIn("@allowed_host host {$PRIVATE_HOST}", caddy_text)
        self.assertIn("@noncanonical_host not host {$PRIVATE_HOST}", caddy_text)
        self.assertNotIn("@allowed_host host {$PRIVATE_HOST} 127.0.0.1 localhost", caddy_text)
        self.assertNotIn("@noncanonical_host not host {$PRIVATE_HOST} 127.0.0.1 localhost", caddy_text)
        self.assertIn("redir @noncanonical_host http://{$PRIVATE_HOST}:8443{uri} 308", caddy_text)


if __name__ == "__main__":
    unittest.main()
