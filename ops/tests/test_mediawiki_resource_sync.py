import importlib.util
import pathlib
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


if __name__ == "__main__":
    unittest.main()
