#!/usr/bin/env python3
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Iterable


@dataclasses.dataclass(frozen=True)
class ManifestItem:
    host_path: pathlib.Path
    container_path: str


@dataclasses.dataclass(frozen=True)
class ComparisonRecord:
    host_path: pathlib.Path
    container_path: str
    host_sha256: str | None
    container_sha256: str | None
    status: str


def build_default_manifest(root_dir: pathlib.Path) -> list[ManifestItem]:
    pairs = [
        (
            "images/mediawiki-app/entrypoint/bootstrap-instance.sh",
            "/usr/local/bin/bootstrap-instance.sh",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/extension.json",
            "/var/www/html/extensions/LabAssistant/extension.json",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/includes/Hooks.php",
            "/var/www/html/extensions/LabAssistant/includes/Hooks.php",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.asset-version.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.asset-version.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.attachment-utils.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.attachment-utils.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.pdf-reader-utils.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.pdf-reader-utils.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.pdf-ingest-utils.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.pdf-ingest-utils.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.session-export-utils.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.session-export-utils.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell-utils.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.shell-utils.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.ui.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.editor-utils.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.editor-utils.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.shell.js",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.shell.js",
        ),
        (
            "images/mediawiki-app/extensions/LabAssistant/modules/ext.labassistant.ui.css",
            "/var/www/html/extensions/LabAssistant/modules/ext.labassistant.ui.css",
        ),
        (
            "images/mediawiki-app/extensions/LabAuth/extension.json",
            "/var/www/html/extensions/LabAuth/extension.json",
        ),
        (
            "images/mediawiki-app/extensions/LabAuth/includes/RegistrationStore.php",
            "/var/www/html/extensions/LabAuth/includes/RegistrationStore.php",
        ),
        (
            "images/mediawiki-app/extensions/LabAuth/modules/ext.labauth.admin.js",
            "/var/www/html/extensions/LabAuth/modules/ext.labauth.admin.js",
        ),
        (
            "images/mediawiki-app/extensions/LabWorkbook/extension.json",
            "/var/www/html/extensions/LabWorkbook/extension.json",
        ),
        (
            "images/mediawiki-app/extensions/LabWorkbook/includes/WorkbookStore.php",
            "/var/www/html/extensions/LabWorkbook/includes/WorkbookStore.php",
        ),
        (
            "images/mediawiki-app/extensions/LabWorkbook/modules/ext.labworkbook.ui.js",
            "/var/www/html/extensions/LabWorkbook/modules/ext.labworkbook.ui.js",
        ),
        (
            "images/mediawiki-app/extensions/LabWorkbook/modules/ext.labworkbook.utils.js",
            "/var/www/html/extensions/LabWorkbook/modules/ext.labworkbook.utils.js",
        ),
        (
            "images/mediawiki-app/extensions/LabWorkbook/modules/ext.labworkbook.ui.css",
            "/var/www/html/extensions/LabWorkbook/modules/ext.labworkbook.ui.css",
        ),
    ]
    return [
        ManifestItem(host_path=root_dir / host_rel, container_path=container_path)
        for host_rel, container_path in pairs
    ]


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_host_hashes(manifest: Iterable[ManifestItem]) -> dict[pathlib.Path, str]:
    return {item.host_path: sha256_file(item.host_path) for item in manifest}


def collect_container_hashes(service: str, container_paths: Iterable[str]) -> dict[str, str]:
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        service,
        "python3",
        "-",
        *container_paths,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        input=(
            "import hashlib\n"
            "import json\n"
            "import pathlib\n"
            "import sys\n"
            "result = {}\n"
            "for raw in sys.argv[1:]:\n"
            "    path = pathlib.Path(raw)\n"
            "    if not path.exists():\n"
            "        continue\n"
            "    digest = hashlib.sha256()\n"
            "    with path.open('rb') as handle:\n"
            "        for chunk in iter(lambda: handle.read(1024 * 1024), b''):\n"
            "            digest.update(chunk)\n"
            "    result[raw] = digest.hexdigest()\n"
            "print(json.dumps(result, ensure_ascii=False))\n"
        ),
    )
    return json.loads(completed.stdout or "{}")


def compare_manifest(
    manifest: Iterable[ManifestItem],
    host_hashes: dict[pathlib.Path, str],
    container_hashes: dict[str, str],
) -> list[ComparisonRecord]:
    records: list[ComparisonRecord] = []
    for item in manifest:
        host_sha256 = host_hashes.get(item.host_path)
        container_sha256 = container_hashes.get(item.container_path)
        if host_sha256 is None or container_sha256 is None:
            status = "missing"
        elif host_sha256 == container_sha256:
            status = "ok"
        else:
            status = "drift"
        records.append(
            ComparisonRecord(
                host_path=item.host_path,
                container_path=item.container_path,
                host_sha256=host_sha256,
                container_sha256=container_sha256,
                status=status,
            )
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="Check MediaWiki runtime resources against repo files.")
    parser.add_argument("--service", default="mw_private", help="docker compose service name to inspect")
    parser.add_argument("--root-dir", default=None, help="repository root (defaults to script parents)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args()

    root_dir = pathlib.Path(args.root_dir).resolve() if args.root_dir else pathlib.Path(__file__).resolve().parents[2]
    manifest = build_default_manifest(root_dir)
    host_hashes = collect_host_hashes(manifest)
    container_hashes = collect_container_hashes(args.service, [item.container_path for item in manifest])
    records = compare_manifest(manifest, host_hashes, container_hashes)

    payload = {
        "service": args.service,
        "root_dir": root_dir.as_posix(),
        "status": "ok" if all(record.status == "ok" for record in records) else "drift",
        "records": [
            {
                "host_path": record.host_path.as_posix(),
                "container_path": record.container_path,
                "host_sha256": record.host_sha256,
                "container_sha256": record.container_sha256,
                "status": record.status,
            }
            for record in records
        ],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for record in records:
            label = "[ok]" if record.status == "ok" else "[fail]"
            print(f"{label} {record.status}: {record.host_path} -> {record.container_path}")

    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
