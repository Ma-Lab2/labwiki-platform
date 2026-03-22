from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.services.student_eval_report import StudentEvalCase
from app.services.student_eval_runner import build_chat_payload, mode_for_case, summarize_error


class StudentEvalRunnerTests(unittest.TestCase):
    def test_mode_for_case_maps_compare_and_draft_like_cases(self) -> None:
        compare_case = StudentEvalCase(
            id="c1",
            category="compare_judgment",
            question="比较 TNSA 和 RPA",
            current_page="Theory:TNSA",
            expected_behavior="",
            must_have=[],
            must_not_have=[],
            gold_reference_pages=[],
            eval_type="compare",
        )
        draft_case = StudentEvalCase(
            id="c2",
            category="term_structuring",
            question="把当前页整理成词条",
            current_page="Theory:TNSA",
            expected_behavior="",
            must_have=[],
            must_not_have=[],
            gold_reference_pages=[],
            eval_type="draft",
        )
        answer_case = StudentEvalCase(
            id="c3",
            category="concept",
            question="什么是 TNSA",
            current_page="Theory:TNSA",
            expected_behavior="",
            must_have=[],
            must_not_have=[],
            gold_reference_pages=[],
            eval_type="answer",
        )

        self.assertEqual(mode_for_case(compare_case), "compare")
        self.assertEqual(mode_for_case(draft_case), "draft")
        self.assertEqual(mode_for_case(answer_case), "qa")

    def test_build_chat_payload_includes_context_page_and_model(self) -> None:
        case = StudentEvalCase(
            id="c1",
            category="concept",
            question="什么是 TNSA",
            current_page="Theory:TNSA",
            expected_behavior="",
            must_have=[],
            must_not_have=[],
            gold_reference_pages=[],
            eval_type="answer",
        )

        payload = build_chat_payload(case, generation_model="gpt-5.4-mini")

        self.assertEqual(payload["question"], "什么是 TNSA")
        self.assertEqual(payload["mode"], "qa")
        self.assertEqual(payload["detail_level"], "intro")
        self.assertEqual(payload["context_pages"], ["Theory:TNSA"])
        self.assertEqual(payload["generation_model"], "gpt-5.4-mini")

    def test_summarize_error_distinguishes_timeout_and_http_failure(self) -> None:
        timeout_error = summarize_error(TimeoutError("timed out"))
        self.assertEqual(timeout_error["error_kind"], "timeout")
        self.assertTrue(timeout_error["retryable"])

        http_error = summarize_error(RuntimeError("HTTP Error 500: Internal Server Error"))
        self.assertEqual(http_error["error_kind"], "http_500")
        self.assertTrue(http_error["retryable"])


if __name__ == "__main__":
    unittest.main()
