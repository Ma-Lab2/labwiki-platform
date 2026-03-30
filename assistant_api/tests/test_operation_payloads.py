from __future__ import annotations

import unittest

from app.schemas import DraftPreviewPayload, ResultFillPayload, WritePreviewPayload, WriteResultPayload
from app.services.operation_payloads import derive_operation_preview, derive_operation_result


class OperationPayloadDerivationTests(unittest.TestCase):
    def test_write_preview_derives_managed_section_operation_preview(self) -> None:
        preview = derive_operation_preview(
            write_preview=WritePreviewPayload(
                preview_id="preview-1",
                action_type="update_managed_page_section",
                operation="replace_section_body",
                target_page="Shot:Shot日志入口",
                target_section="使用规则",
                preview_text="目标页面：Shot:Shot日志入口",
                structured_payload={"区块": "使用规则"},
                missing_fields=[],
                metadata={"target_section": "使用规则"},
            )
        )

        self.assertIsNotNone(preview)
        self.assertEqual(preview.kind, "managed_section_edit")
        self.assertEqual(preview.target_section, "使用规则")

    def test_result_fill_derives_shot_result_operation_preview(self) -> None:
        preview = derive_operation_preview(
            result_fill=ResultFillPayload(
                title="Shot:2026-03-20-Run01-Shot001",
                field_suggestions={"截止能量": "12 MeV"},
                draft_text="建议写入结果字段",
                missing_items=[],
                evidence=["Shot 页面截图"],
            )
        )

        self.assertIsNotNone(preview)
        self.assertEqual(preview.kind, "shot_result_fill")
        self.assertEqual(preview.operation, "fill")
        self.assertEqual(preview.structured_payload["field_suggestions"]["截止能量"], "12 MeV")

    def test_write_result_derives_operation_result(self) -> None:
        result = derive_operation_result(
            write_result=WriteResultPayload(
                status="success",
                page_title="Shot:Shot日志入口",
                operation="replace_section_body",
                action_type="update_managed_page_section",
                target_section="使用规则",
                detail="受控提交已执行。",
            )
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.kind, "managed_section_edit")
        self.assertEqual(result.page_title, "Shot:Shot日志入口")


if __name__ == "__main__":
    unittest.main()
