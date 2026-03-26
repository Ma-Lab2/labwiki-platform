from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ops" / "scripts" / "render_pdf_reader_report.py"
SPEC = importlib.util.spec_from_file_location("render_pdf_reader_report", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RenderPdfReaderReportTests(unittest.TestCase):
    def test_build_report_markdown_summarizes_pdf_reader_flow(self) -> None:
        markdown = MODULE.build_report_markdown(
            {
                "base_url": "http://localhost:8443",
                "literature_page_with_pdf": "文献导读/PDF阅读测试",
                "literature_page_empty": "文献导读/PDF阅读空状态测试",
                "empty_state_present": True,
                "embedded_reader_present": True,
                "embedded_navigation_present": True,
                "literature_edit_entry_present": True,
                "embedded_reader_src": "/wiki/Special:Redirect/file/LabAssistant-Sample-Paper.pdf#page=3&zoom=110",
                "assistant_seeded_from_embedded_quote": True,
                "attachment_chip_present": True,
                "floating_reader_present": True,
                "floating_reader_src": "http://localhost:8443/tools/assistant/api/attachments/att-123/content#page=1&zoom=110",
                "assistant_seeded_from_attachment_quote": True,
                "artifacts": [
                    "01-literature-empty.yml",
                    "02-literature-reader.yml",
                    "03-embedded-quote-sent.yml",
                    "04-attachment-reader.yml",
                ],
            }
        )

        self.assertIn("# PDF 阅读回归报告", markdown)
        self.assertIn("Base URL: `http://localhost:8443`", markdown)
        self.assertIn("Literature page with PDF: `文献导读/PDF阅读测试`", markdown)
        self.assertIn("Literature empty page: `文献导读/PDF阅读空状态测试`", markdown)
        self.assertIn("Empty state present: `yes`", markdown)
        self.assertIn("Embedded reader present: `yes`", markdown)
        self.assertIn("Embedded navigation present: `yes`", markdown)
        self.assertIn("Literature edit entry present: `yes`", markdown)
        self.assertIn("Embedded reader src: `/wiki/Special:Redirect/file/LabAssistant-Sample-Paper.pdf#page=3&zoom=110`", markdown)
        self.assertIn("Assistant seeded from embedded quote: `yes`", markdown)
        self.assertIn("Attachment chip present: `yes`", markdown)
        self.assertIn("Floating reader present: `yes`", markdown)
        self.assertIn("Assistant seeded from attachment quote: `yes`", markdown)
        self.assertIn("- `04-attachment-reader.yml`", markdown)


if __name__ == "__main__":
    unittest.main()
