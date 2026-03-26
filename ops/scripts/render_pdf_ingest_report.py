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
            "# PDF 摄取写入回归报告",
            "",
            f"- Base URL: `{summary.get('base_url', '')}`",
            f"- Target page: `{summary.get('target_page', '')}`",
            f"- Sample PDF: `{summary.get('sample_pdf', '')}`",
            f"- Forced model before review: `{summary.get('forced_model_before', '')}`",
            f"- Active model after review: `{summary.get('active_model_after_review', '')}`",
            f"- Model promoted from mini: `{_yes_no(summary.get('model_promoted_from_mini'))}`",
            f"- Launcher present: `{_yes_no(summary.get('launcher_present'))}`",
            f"- Attachment ready: `{_yes_no(summary.get('attachment_ready'))}`",
            f"- Review card present: `{_yes_no(summary.get('review_card_present'))}`",
            f"- Review mentions control-manual details: `{_yes_no(summary.get('review_mentions_control_manual'))}`",
            f"- Primary target is Control: `{_yes_no(summary.get('primary_target_control'))}`",
            f"- Draft preview present: `{_yes_no(summary.get('draft_preview_present'))}`",
            f"- Draft commit success: `{_yes_no(summary.get('draft_commit_success'))}`",
            f"- Draft page title: `{summary.get('draft_page_title', '')}`",
            f"- Draft page includes suggested Control target: `{_yes_no(summary.get('draft_page_contains_control_target'))}`",
            f"- Draft page includes page gallery: `{_yes_no(summary.get('draft_page_contains_page_gallery'))}`",
            f"- Draft page includes uploaded page files: `{_yes_no(summary.get('draft_page_contains_uploaded_files'))}`",
            f"- Formal preview present: `{_yes_no(summary.get('formal_preview_present'))}`",
            f"- Formal preview targets Control: `{_yes_no(summary.get('formal_preview_targets_control'))}`",
            f"- Formal preview blocked items: `{summary.get('formal_preview_blocked_items', 0)}`",
            f"- Formal commit success: `{_yes_no(summary.get('formal_commit_success'))}`",
            f"- Formal page title: `{summary.get('formal_page_title', '')}`",
            f"- Overview page title: `{summary.get('overview_page_title', '')}`",
            f"- Formal page contains managed block: `{_yes_no(summary.get('formal_page_contains_managed_block'))}`",
            f"- Overview page contains topic link: `{_yes_no(summary.get('overview_page_contains_topic_link'))}`",
            "",
            "## Artifacts",
            artifact_lines or "- none",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render PDF ingest markdown report from JSON summary.")
    parser.add_argument("--summary-file", required=True, help="Path to the JSON summary file.")
    parser.add_argument("--output", required=True, help="Path to the markdown report file.")
    args = parser.parse_args()

    summary = json.loads(Path(args.summary_file).read_text(encoding="utf-8"))
    Path(args.output).write_text(build_report_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
