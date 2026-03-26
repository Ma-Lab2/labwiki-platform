from __future__ import annotations

import argparse
import json
from pathlib import Path


def _yes_no(value: object) -> str:
    return "yes" if bool(value) else "no"


def build_report_markdown(summary: dict[str, object]) -> str:
    artifacts = summary.get("artifacts") or []
    artifact_lines = "\n".join(f"- `{item}`" for item in artifacts)
    return "\n".join(
        [
            "# PDF 阅读回归报告",
            "",
            f"- Base URL: `{summary.get('base_url', '')}`",
            f"- Literature page with PDF: `{summary.get('literature_page_with_pdf', '')}`",
            f"- Literature empty page: `{summary.get('literature_page_empty', '')}`",
            f"- Empty state present: `{_yes_no(summary.get('empty_state_present'))}`",
            f"- Embedded reader present: `{_yes_no(summary.get('embedded_reader_present'))}`",
            f"- Embedded navigation present: `{_yes_no(summary.get('embedded_navigation_present'))}`",
            f"- Literature edit entry present: `{_yes_no(summary.get('literature_edit_entry_present'))}`",
            f"- Embedded reader src: `{summary.get('embedded_reader_src', '')}`",
            f"- Assistant seeded from embedded quote: `{_yes_no(summary.get('assistant_seeded_from_embedded_quote'))}`",
            f"- Attachment chip present: `{_yes_no(summary.get('attachment_chip_present'))}`",
            f"- Floating reader present: `{_yes_no(summary.get('floating_reader_present'))}`",
            f"- Floating reader src: `{summary.get('floating_reader_src', '')}`",
            f"- Assistant seeded from attachment quote: `{_yes_no(summary.get('assistant_seeded_from_attachment_quote'))}`",
            "",
            "## Artifacts",
            artifact_lines or "- none",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render PDF reader markdown report from JSON summary.")
    parser.add_argument("--summary-file", required=True, help="Path to the JSON summary file.")
    parser.add_argument("--output", required=True, help="Path to the markdown report file.")
    args = parser.parse_args()

    summary = json.loads(Path(args.summary_file).read_text(encoding="utf-8"))
    Path(args.output).write_text(build_report_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
