from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops" / "scripts"))

from extract_lab_workbooks import extract_workbook  # type: ignore  # noqa: E402


class ExtractLabWorkbooksTests(unittest.TestCase):
    def test_extracts_main_log_sheet_from_real_workbook(self) -> None:
        workbook = extract_workbook(ROOT / "shotlist20250926.xls")

        self.assertEqual(workbook["slug"], "20250926")
        self.assertEqual(workbook["source_filename"], "shotlist20250926.xls")
        self.assertGreaterEqual(len(workbook["sheets"]), 3)

        main_sheet = workbook["sheets"][0]
        self.assertEqual(main_sheet["type"], "main_log")
        self.assertIn("时间", main_sheet["columns"])
        self.assertIn("No", main_sheet["columns"])
        self.assertIn("靶类型", main_sheet["columns"])
        self.assertEqual(main_sheet["rows"][0]["No"], "1")
        self.assertEqual(main_sheet["rows"][0]["时间"], "2025-09-26 17:01:48")

    def test_infers_grid_and_calibration_sheet_types(self) -> None:
        workbook = extract_workbook(ROOT / "shotlist20251111.xls")

        sheet_types = {sheet["sheet_name"]: sheet["type"] for sheet in workbook["sheets"]}

        self.assertEqual(sheet_types["Sheet1"], "main_log")
        self.assertEqual(sheet_types["Sheet3"], "target_grid")
        self.assertEqual(sheet_types["Sheet4"], "target_grid")
        self.assertEqual(sheet_types["Sheet5"], "target_grid")
        self.assertEqual(sheet_types["Sheet6"], "calibration")

    def test_preserves_workbook_level_run_label_as_editable_blank_default(self) -> None:
        workbook = extract_workbook(ROOT / "shotlist20251111.xls")

        self.assertEqual(workbook["run_label"], "")


if __name__ == "__main__":
    unittest.main()
