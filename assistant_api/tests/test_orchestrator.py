from __future__ import annotations

import unittest

from app.constants import AssistantMode, TaskType
from app.services.orchestrator import _source_priority, classify_question


class OrchestratorClassificationTests(unittest.TestCase):
    def test_newcomer_explanation_stays_concept(self) -> None:
        task_type = classify_question(
            "什么是 TNSA？请用新人能懂的话解释。",
            AssistantMode.QA,
            ["Theory:TNSA"],
        )

        self.assertEqual(task_type, TaskType.CONCEPT)

    def test_learning_path_requires_explicit_navigation_intent(self) -> None:
        task_type = classify_question(
            "如果我要学 TPS，建议按什么顺序看 wiki？",
            AssistantMode.QA,
            ["Diagnostic:TPS"],
        )

        self.assertEqual(task_type, TaskType.LEARNING_PATH)

    def test_compare_beats_concept_even_with_current_page(self) -> None:
        task_type = classify_question(
            "RPA 和 TNSA 的核心差别是什么？",
            AssistantMode.QA,
            ["Theory:离子加速机制概览"],
        )

        self.assertEqual(task_type, TaskType.COMPARE)

    def test_page_structuring_stays_draft(self) -> None:
        task_type = classify_question(
            "帮我整理这个页面的词条。",
            AssistantMode.QA,
            ["Theory:TNSA"],
        )

        self.assertEqual(task_type, TaskType.DRAFT)


class SourcePriorityTests(unittest.TestCase):
    def test_context_is_highest_priority_for_structured_only(self) -> None:
        self.assertLess(
            _source_priority("context", structured_only=True),
            _source_priority("cargo", structured_only=True),
        )

    def test_context_is_highest_priority_for_normal_answers(self) -> None:
        self.assertLess(
            _source_priority("context", structured_only=False),
            _source_priority("cargo", structured_only=False),
        )


if __name__ == "__main__":
    unittest.main()
