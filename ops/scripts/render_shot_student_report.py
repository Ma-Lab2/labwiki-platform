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
            "# Shot 学生流程回归报告",
            "",
            f"- Base URL: `{summary.get('base_url', '')}`",
            f"- Shot page: `{summary.get('shot_page', '')}`",
            f"- Result fill card present: `{_yes_no(summary.get('result_fill_card_present'))}`",
            f"- Form fill card present: `{_yes_no(summary.get('form_fill_card_present'))}`",
            f"- Pending fields before confirm: `{summary.get('pending_fields_count_before_confirm', 0)}`",
            f"- Missing fields before confirm: `{summary.get('missing_fields_count_before_confirm', 0)}`",
            f"- Submission guidance split present: `{_yes_no(summary.get('submission_guidance_split_present'))}`",
            f"- Confirmed field label: `{summary.get('confirmed_field_label', '')}`",
            f"- Confirmed field value: `{summary.get('confirmed_field_value', '')}`",
            f"- Pending fields after confirm: `{summary.get('pending_fields_count_after_confirm', 0)}`",
            f"- Page auto-submitted: `{_yes_no(summary.get('page_auto_submitted'))}`",
            f"- Restored submission guidance: `{_yes_no(summary.get('restored_submission_guidance'))}`",
            "",
            "## Artifacts",
            artifact_lines or "- none",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Shot student flow markdown report from JSON summary.")
    parser.add_argument("--summary-file", required=True, help="Path to the JSON summary file.")
    parser.add_argument("--output", required=True, help="Path to the markdown report file.")
    args = parser.parse_args()

    summary = json.loads(Path(args.summary_file).read_text(encoding="utf-8"))
    Path(args.output).write_text(build_report_markdown(summary), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
