from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.student_eval_report import (
    build_score_template_rows,
    load_cases,
    load_scores_csv,
    render_markdown_report,
    summarize_student_eval,
)


class StudentEvalReportTests(unittest.TestCase):
    def test_summary_aggregates_scores_penalties_and_failure_tags(self) -> None:
        cases = load_cases(
            Path(__file__).resolve().parents[1] / "app" / "benchmarks" / "student_eval_cases.json"
        )
        rows = [
            {
                "case_id": "concept-tnsa-intro",
                "model": "gpt-5.4-mini",
                "task_type": "answer",
                "hit_current_page": "yes",
                "hit_correct_pages": "yes",
                "final_answer_summary": "直接解释 TNSA，并引用站内页。",
                "task_completion": "2",
                "lab_context_fit": "2",
                "current_page_use": "1",
                "structure_usability": "2",
                "boundary_honesty": "2",
                "penalty_off_topic": "0",
                "penalty_index_as_answer": "0",
                "failure_tags": "",
                "optimization_note": "",
                "evidence_ref": "turn-001",
            },
            {
                "case_id": "current-page-term-entry",
                "model": "gpt-5.4-mini",
                "task_type": "draft",
                "hit_current_page": "no",
                "hit_correct_pages": "partial",
                "final_answer_summary": "主要解释索引页，没有整理当前页。",
                "task_completion": "1",
                "lab_context_fit": "1",
                "current_page_use": "0",
                "structure_usability": "1",
                "boundary_honesty": "2",
                "penalty_off_topic": "0",
                "penalty_index_as_answer": "2",
                "failure_tags": "ignored_current_page;answered_retrieval_instead_of_task;wrong_source_priority",
                "optimization_note": "强化当前页优先级和整理类回答模板。",
                "evidence_ref": "turn-002",
            },
        ]

        summary = summarize_student_eval(cases, rows)

        self.assertEqual(summary["overall"]["case_count"], 2)
        self.assertEqual(summary["overall"]["average_score"], 6.0)
        self.assertEqual(summary["overall"]["grade"], "unstable")
        self.assertEqual(summary["categories"]["concept"]["average_score"], 9.0)
        self.assertEqual(summary["categories"]["term_structuring"]["average_score"], 3.0)
        self.assertEqual(summary["failure_tags"][0]["tag"], "answered_retrieval_instead_of_task")
        self.assertEqual(summary["failure_tags"][0]["count"], 1)
        self.assertEqual(summary["top_optimization_priorities"][0]["tag"], "ignored_current_page")

    def test_markdown_report_contains_overview_categories_and_priority_sections(self) -> None:
        cases = load_cases(
            Path(__file__).resolve().parents[1] / "app" / "benchmarks" / "student_eval_cases.json"
        )
        rows = [
            {
                "case_id": "concept-tnsa-intro",
                "model": "gpt-5.4-mini",
                "task_type": "answer",
                "hit_current_page": "yes",
                "hit_correct_pages": "yes",
                "final_answer_summary": "直接解释 TNSA，并引用站内页。",
                "task_completion": "2",
                "lab_context_fit": "2",
                "current_page_use": "2",
                "structure_usability": "2",
                "boundary_honesty": "2",
                "penalty_off_topic": "0",
                "penalty_index_as_answer": "0",
                "failure_tags": "",
                "optimization_note": "",
                "evidence_ref": "turn-001",
            }
        ]

        summary = summarize_student_eval(cases, rows)
        markdown = render_markdown_report(summary)

        self.assertIn("# Assistant Student Evaluation Report", markdown)
        self.assertIn("## Overview", markdown)
        self.assertIn("## Category Results", markdown)
        self.assertIn("## Top Optimization Priorities", markdown)
        self.assertIn("concept", markdown)
        self.assertIn("10.0", markdown)

    def test_template_rows_cover_all_cases_with_blank_scoring_columns(self) -> None:
        cases = load_cases(
            Path(__file__).resolve().parents[1] / "app" / "benchmarks" / "student_eval_cases.json"
        )
        template_rows = build_score_template_rows(cases)

        self.assertEqual(len(template_rows), len(cases))
        self.assertEqual(template_rows[0]["case_id"], "concept-tnsa-intro")
        self.assertEqual(template_rows[0]["task_completion"], "")
        self.assertEqual(template_rows[0]["penalty_index_as_answer"], "")

    def test_load_scores_csv_reads_failure_tags_as_semicolon_separated_values(self) -> None:
        csv_text = """case_id,model,task_type,hit_current_page,hit_correct_pages,final_answer_summary,task_completion,lab_context_fit,current_page_use,structure_usability,boundary_honesty,penalty_off_topic,penalty_index_as_answer,failure_tags,optimization_note,evidence_ref
current-page-term-entry,gpt-5.4-mini,draft,no,partial,主要解释索引页，没有整理当前页。,1,1,0,1,2,0,2,ignored_current_page;wrong_source_priority,强化当前页优先级,turn-002
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "scores.csv"
            path.write_text(csv_text, encoding="utf-8")

            rows = load_scores_csv(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["failure_tags"], ["ignored_current_page", "wrong_source_priority"])


if __name__ == "__main__":
    unittest.main()
