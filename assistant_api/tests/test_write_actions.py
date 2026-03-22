from __future__ import annotations

import unittest

from app.services.write_actions import prepare_write_preview


class _DisabledGenerationProvider:
    enabled = False


class _FakeLLM:
    def __init__(self) -> None:
        self.generation_provider = _DisabledGenerationProvider()


class _FakeWiki:
    def get_page_text(self, title: str) -> str:
        return ""


class WritePreviewTests(unittest.TestCase):
    def test_page_structuring_request_degrades_to_term_entry_preview(self) -> None:
        preview = prepare_write_preview(
            settings=None,  # unused in current implementation
            llm=_FakeLLM(),
            wiki=_FakeWiki(),
            question="帮我整理这个页面的词条。",
            answer="TNSA 是靶背鞘层加速机制。",
            source_titles=["Theory:TNSA"],
            current_page="Theory:TNSA",
            conversation_history=[],
        )

        self.assertEqual(preview["action_type"], "create_term_entry")
        self.assertTrue(preview["target_page"].startswith("术语条目/"))
        self.assertIn("中文名", preview["metadata_json"]["missing_fields"])

    def test_weekly_log_preview_uses_append_operation(self) -> None:
        preview = prepare_write_preview(
            settings=None,  # unused in current implementation
            llm=_FakeLLM(),
            wiki=_FakeWiki(),
            question="把这个 shot 补进本周周实验日志。",
            answer="Shot 结果显示质子截止能量提升。",
            source_titles=["Shot:2026-03-20-Run01-Shot001"],
            current_page="Shot:2026-W11 周实验日志",
            conversation_history=[],
        )

        self.assertEqual(preview["action_type"], "append_weekly_shot_log")
        self.assertEqual(preview["operation"], "append")


if __name__ == "__main__":
    unittest.main()
