from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ops" / "scripts" / "render_pdf_ingest_report.py"
SPEC = importlib.util.spec_from_file_location("render_pdf_ingest_report", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RenderPdfIngestReportTests(unittest.TestCase):
    def test_build_report_markdown_summarizes_pdf_ingest_flow(self) -> None:
        markdown = MODULE.build_report_markdown(
            {
                "base_url": "http://localhost:8443",
                "target_page": "首页",
                "sample_pdf": "怀柔真空管道电机控制.pdf",
                "forced_model_before": "gpt-5.4-mini",
                "active_model_after_review": "gpt-5.4",
                "model_promoted_from_mini": True,
                "launcher_present": True,
                "attachment_ready": True,
                "review_card_present": True,
                "review_mentions_control_manual": True,
                "primary_target_control": True,
                "draft_preview_present": True,
                "draft_commit_success": True,
                "draft_page_title": "知识助手草稿/PDF提取/怀柔真空管道电机控制",
                "draft_page_contains_control_target": True,
                "draft_page_contains_page_gallery": True,
                "draft_page_contains_uploaded_files": True,
                "formal_preview_present": True,
                "formal_preview_targets_control": True,
                "formal_preview_blocked_items": 2,
                "formal_commit_success": True,
                "formal_page_title": "Control:怀柔真空管道电机控制流程",
                "overview_page_title": "Control:控制与运行总览",
                "formal_page_contains_managed_block": True,
                "overview_page_contains_topic_link": True,
                "artifacts": [
                    "01-page.yml",
                    "02-review.yml",
                    "03-preview.yml",
                    "04-commit.yml",
                    "05-draft-raw.txt",
                ],
            }
        )

        self.assertIn("# PDF 摄取写入回归报告", markdown)
        self.assertIn("Base URL: `http://localhost:8443`", markdown)
        self.assertIn("Target page: `首页`", markdown)
        self.assertIn("Sample PDF: `怀柔真空管道电机控制.pdf`", markdown)
        self.assertIn("Forced model before review: `gpt-5.4-mini`", markdown)
        self.assertIn("Active model after review: `gpt-5.4`", markdown)
        self.assertIn("Model promoted from mini: `yes`", markdown)
        self.assertIn("Launcher present: `yes`", markdown)
        self.assertIn("Review card present: `yes`", markdown)
        self.assertIn("Primary target is Control: `yes`", markdown)
        self.assertIn("Draft commit success: `yes`", markdown)
        self.assertIn("Draft page title: `知识助手草稿/PDF提取/怀柔真空管道电机控制`", markdown)
        self.assertIn("Formal preview present: `yes`", markdown)
        self.assertIn("Formal preview targets Control: `yes`", markdown)
        self.assertIn("Formal preview blocked items: `2`", markdown)
        self.assertIn("Formal commit success: `yes`", markdown)
        self.assertIn("Formal page title: `Control:怀柔真空管道电机控制流程`", markdown)
        self.assertIn("Overview page title: `Control:控制与运行总览`", markdown)
        self.assertIn("Formal page contains managed block: `yes`", markdown)
        self.assertIn("Overview page contains topic link: `yes`", markdown)
        self.assertIn("- `05-draft-raw.txt`", markdown)


if __name__ == "__main__":
    unittest.main()
