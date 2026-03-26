from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ops" / "scripts" / "render_shot_student_report.py"
SPEC = importlib.util.spec_from_file_location("render_shot_student_report", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RenderShotStudentReportTests(unittest.TestCase):
    def test_build_report_markdown_summarizes_student_flow_assertions(self) -> None:
        markdown = MODULE.build_report_markdown(
            {
                "base_url": "http://localhost:8443",
                "shot_page": "Special:编辑表格/Shot记录/Shot:2026-03-23-Run96-Shot001",
                "result_fill_card_present": True,
                "form_fill_card_present": True,
                "pending_fields_count_before_confirm": 2,
                "missing_fields_count_before_confirm": 2,
                "submission_guidance_split_present": True,
                "confirmed_field_label": "原始数据主目录",
                "confirmed_field_value": "/data/shot/2026-03-23/Run96",
                "pending_fields_count_after_confirm": 1,
                "page_auto_submitted": False,
                "restored_submission_guidance": True,
                "artifacts": [
                    "01-shot-form.yml",
                    "02-shot-result-fill.yml",
                    "03-shot-after-confirm.yml",
                    "04-shot-after-refresh.yml",
                ],
            }
        )

        self.assertIn("# Shot 学生流程回归报告", markdown)
        self.assertIn("Base URL: `http://localhost:8443`", markdown)
        self.assertIn("Shot page: `Special:编辑表格/Shot记录/Shot:2026-03-23-Run96-Shot001`", markdown)
        self.assertIn("Result fill card present: `yes`", markdown)
        self.assertIn("Submission guidance split present: `yes`", markdown)
        self.assertIn("Confirmed field label: `原始数据主目录`", markdown)
        self.assertIn("Confirmed field value: `/data/shot/2026-03-23/Run96`", markdown)
        self.assertIn("Page auto-submitted: `no`", markdown)
        self.assertIn("Restored submission guidance: `yes`", markdown)
        self.assertIn("- `04-shot-after-refresh.yml`", markdown)


if __name__ == "__main__":
    unittest.main()
