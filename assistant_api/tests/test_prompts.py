from __future__ import annotations

import unittest

from app.constants import TaskType
from app.services.prompts import build_answer_prompt


class PromptBehaviorTests(unittest.TestCase):
    def test_current_page_structuring_prompt_forbids_placeholder_field_values(self) -> None:
        envelope = build_answer_prompt(
            question="帮我整理这个页面的词条。",
            task_type=TaskType.DRAFT.value,
            detail_level="intro",
            mode="qa",
            current_page="Theory:TNSA",
            evidence=[],
            unresolved_gaps=[],
            structured_only=False,
            conversation_history=[],
        )

        self.assertIn("未知字段留空", envelope.system_prompt)
        self.assertIn("不要写“待补充”“未知”“无”", envelope.system_prompt)
        self.assertIn("缺失字段", envelope.system_prompt)


if __name__ == "__main__":
    unittest.main()
