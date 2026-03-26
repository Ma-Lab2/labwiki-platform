from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.schemas import AttachmentItem, ChatRequest
from app.services.result_fill import is_shot_result_fill_request, prepare_shot_result_fill
from app.services.attachments import store_attachment


class _FakeGenerationProvider:
    enabled = True


class _FakeLLM:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.generation_provider = _FakeGenerationProvider()
        self.last_prompt = None

    def generate_prompt(self, prompt):
        self.last_prompt = prompt
        return self.raw


class ShotResultFillTests(unittest.TestCase):
    def test_is_shot_result_fill_request_requires_shot_context_and_image(self) -> None:
        request = ChatRequest(
            question="请根据这些结果截图回填一版 Shot 记录，列出待确认项。",
            context_pages=["Shot:2026-03-14-Run01-Shot001"],
            attachments=[
                AttachmentItem(
                    id="att-001",
                    kind="image",
                    name="shot-summary.png",
                    mime_type="image/png",
                    size_bytes=128,
                )
            ],
            workflow_hint="shot_result_fill",
        )

        self.assertTrue(is_shot_result_fill_request(request))

    def test_prepare_shot_result_fill_returns_structured_payload(self) -> None:
        llm = _FakeLLM(
            """
            {
              "title": "Shot 结果回填建议",
              "field_suggestions": {
                "日期": {
                  "value": "2026-03-14",
                  "status": "confirmed",
                  "evidence": ["当前页 Shot:2026-03-14-Run01-Shot001"]
                },
                "Run": {
                  "value": "Run01",
                  "status": "confirmed",
                  "evidence": ["当前页 Shot:2026-03-14-Run01-Shot001"]
                },
                "TPS结果图": {
                  "value": "shot-summary.png",
                  "status": "confirmed",
                  "evidence": ["附件 shot-summary.png"]
                },
                "主要观测": {
                  "value": "质子截止能量较上一发抬升。",
                  "status": "pending",
                  "evidence": ["附件 shot-summary.png"]
                }
              },
              "draft_text": "== 结果摘要 ==\\n* 主要观测：质子截止能量较上一发抬升。",
              "missing_items": [
                {
                  "label": "RCF结果截图",
                  "reason": "当前附件里没有对应的 RCF 图，请学生补充。",
                  "evidence": ["附件 shot-summary.png"]
                },
                "真空"
              ],
              "evidence": ["附件 shot-summary.png", "当前页 Shot:2026-03-14-Run01-Shot001"]
            }
            """.strip()
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = store_attachment(
                attachments_dir=Path(tmp_dir),
                filename="shot-summary.png",
                content_type="image/png",
                content=b"png-bytes",
            )
            request = ChatRequest(
                question="请根据这些结果截图回填一版 Shot 记录，列出待确认项。",
                context_pages=["Shot:2026-03-14-Run01-Shot001"],
                attachments=[payload],
                workflow_hint="shot_result_fill",
            )

            result = prepare_shot_result_fill(
                settings=None,
                llm=llm,
                attachments_dir=Path(tmp_dir),
                request=request,
                answer="已先整理出一版 shot 记录草稿。",
                source_titles=["Shot:2026-03-14-Run01-Shot001"],
                conversation_history=[],
            )

        self.assertEqual(result["title"], "Shot 结果回填建议")
        self.assertEqual(result["field_suggestions"]["Run"]["value"], "Run01")
        self.assertEqual(result["field_suggestions"]["Run"]["status"], "confirmed")
        self.assertEqual(result["field_suggestions"]["主要观测"]["status"], "pending")
        self.assertEqual(result["missing_items"][0]["label"], "RCF结果截图")
        self.assertIn("附件 shot-summary.png", result["missing_items"][0]["evidence"])
        self.assertEqual(result["missing_items"][1], "真空")
        self.assertEqual(result["evidence"][0], "附件 shot-summary.png")
        self.assertIsNotNone(llm.last_prompt)

    def test_prepare_shot_result_fill_fallback_builds_field_level_evidence(self) -> None:
        llm = _FakeLLM("not-json")
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = store_attachment(
                attachments_dir=Path(tmp_dir),
                filename="shot-summary.png",
                content_type="image/png",
                content=b"png-bytes",
            )
            request = ChatRequest(
                question="请根据这些结果截图回填一版 Shot 记录，列出待确认项。",
                context_pages=["Shot:2026-03-14-Run01-Shot001"],
                attachments=[payload],
                workflow_hint="shot_result_fill",
            )

            result = prepare_shot_result_fill(
                settings=None,
                llm=llm,
                attachments_dir=Path(tmp_dir),
                request=request,
                answer="",
                source_titles=["Shot:2026-03-14-Run01-Shot001"],
                conversation_history=[],
            )

        self.assertEqual(result["field_suggestions"]["Run"]["value"], "Run01")
        self.assertEqual(result["field_suggestions"]["Run"]["status"], "confirmed")
        self.assertIn("当前页 Shot:2026-03-14-Run01-Shot001", result["field_suggestions"]["Run"]["evidence"])
        self.assertEqual(result["field_suggestions"]["TPS结果图"]["value"], "shot-summary.png")
        self.assertIn("附件 shot-summary.png", result["field_suggestions"]["TPS结果图"]["evidence"])
        self.assertEqual(result["field_suggestions"]["原始数据主目录"]["status"], "pending")
        self.assertEqual(result["field_suggestions"]["原始数据主目录"]["value"], "/data/shot/2026-03-14/Run01")
        self.assertEqual(result["field_suggestions"]["处理结果文件"]["status"], "pending")
        self.assertEqual(result["field_suggestions"]["处理结果文件"]["value"], "Shot-2026-03-14-Run01-Shot001-analysis.zip")
        self.assertEqual(result["missing_items"][0]["label"], "主要观测")
        self.assertIn("附件 shot-summary.png", result["missing_items"][0]["evidence"])
        self.assertEqual(result["missing_items"][1]["label"], "判断依据")

    def test_prepare_shot_result_fill_adds_pending_candidates_when_model_has_none(self) -> None:
        llm = _FakeLLM(
            """
            {
              "title": "Shot 结果回填建议",
              "field_suggestions": {
                "日期": {
                  "value": "2026-03-14",
                  "status": "confirmed",
                  "evidence": ["当前页 Shot:2026-03-14-Run01-Shot001"]
                },
                "Run": {
                  "value": "Run01",
                  "status": "confirmed",
                  "evidence": ["当前页 Shot:2026-03-14-Run01-Shot001"]
                }
              },
              "draft_text": "== 结果摘要 ==",
              "missing_items": ["原始数据主目录", "处理结果文件", "主要观测"],
              "evidence": ["附件 shot-summary.png"]
            }
            """.strip()
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = store_attachment(
                attachments_dir=Path(tmp_dir),
                filename="shot-summary.png",
                content_type="image/png",
                content=b"png-bytes",
            )
            request = ChatRequest(
                question="请根据这些结果截图回填一版 Shot 记录，列出待确认项。",
                context_pages=["Shot:2026-03-14-Run01-Shot001"],
                attachments=[payload],
                workflow_hint="shot_result_fill",
            )

            result = prepare_shot_result_fill(
                settings=None,
                llm=llm,
                attachments_dir=Path(tmp_dir),
                request=request,
                answer="",
                source_titles=["Shot:2026-03-14-Run01-Shot001"],
                conversation_history=[],
            )

        self.assertEqual(result["field_suggestions"]["原始数据主目录"]["status"], "pending")
        self.assertEqual(result["field_suggestions"]["处理结果文件"]["status"], "pending")
        self.assertEqual(result["field_suggestions"]["原始数据主目录"]["reason"], "按 Shot 标题可推得本次原始数据主目录候选，请学生确认实际存储路径。")
        self.assertNotIn("原始数据主目录", result["missing_items"])
        self.assertNotIn("处理结果文件", result["missing_items"])
        self.assertIn("主要观测", result["missing_items"])


if __name__ == "__main__":
    unittest.main()
