from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CASES_PATH = Path(__file__).resolve().parents[1] / "benchmarks" / "student_eval_cases.json"

SCORE_FIELDS = [
    "task_completion",
    "lab_context_fit",
    "current_page_use",
    "structure_usability",
    "boundary_honesty",
]

PENALTY_FIELDS = [
    "penalty_off_topic",
    "penalty_index_as_answer",
]

FAILURE_PRIORITY = {
    "ignored_current_page": {
        "priority": "P0",
        "weight": 100,
        "recommended_focus": "加强当前页读取、上下文注入和 source priority。",
    },
    "answered_retrieval_instead_of_task": {
        "priority": "P0",
        "weight": 95,
        "recommended_focus": "收紧回答模板，要求直接完成任务而不是汇报检索过程。",
    },
    "wrong_task_type": {
        "priority": "P0",
        "weight": 90,
        "recommended_focus": "修正意图分类和 planner 分支选择。",
    },
    "missing_write_preview": {
        "priority": "P0",
        "weight": 88,
        "recommended_focus": "补强 draft/write preview 路径和相关前端触发。",
    },
    "wrong_source_priority": {
        "priority": "P1",
        "weight": 84,
        "recommended_focus": "调整当前页、结构化页和索引页的优先级。",
    },
    "insufficient_grounding": {
        "priority": "P1",
        "weight": 82,
        "recommended_focus": "优化检索、rerank 和证据注入。",
    },
    "too_generic": {
        "priority": "P1",
        "weight": 80,
        "recommended_focus": "强化领域关键词、few-shot 和站内表达模板。",
    },
    "bad_structure": {
        "priority": "P1",
        "weight": 76,
        "recommended_focus": "优化回答模板与前端展示结构。",
    },
    "overexplained_process": {
        "priority": "P2",
        "weight": 70,
        "recommended_focus": "减少主回答中的过程噪声，把过程信息收进折叠区。",
    },
    "unsafe_write_assumption": {
        "priority": "P0",
        "weight": 92,
        "recommended_focus": "收紧写入保护、字段校验和确认逻辑。",
    },
}

GRADE_BANDS = [
    (9.0, "ready"),
    (7.0, "usable_with_edits"),
    (5.0, "unstable"),
    (0.0, "needs_work"),
]


@dataclass(frozen=True)
class StudentEvalCase:
    id: str
    category: str
    question: str
    current_page: str
    expected_behavior: str
    must_have: list[str]
    must_not_have: list[str]
    gold_reference_pages: list[str]
    eval_type: str


def load_cases(path: Path | None = None) -> list[StudentEvalCase]:
    source = path or DEFAULT_CASES_PATH
    raw_cases = json.loads(source.read_text(encoding="utf-8"))
    return [
        StudentEvalCase(
            id=item["id"],
            category=item["category"],
            question=item["question"],
            current_page=item.get("current_page") or "",
            expected_behavior=item.get("expected_behavior") or "",
            must_have=item.get("must_have") or [],
            must_not_have=item.get("must_not_have") or [],
            gold_reference_pages=item.get("gold_reference_pages") or [],
            eval_type=item.get("eval_type") or "answer",
        )
        for item in raw_cases
    ]


def build_score_template_rows(cases: list[StudentEvalCase]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case in cases:
        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "current_page": case.current_page,
                "question": case.question,
                "eval_type": case.eval_type,
                "expected_behavior": case.expected_behavior,
                "must_have": ";".join(case.must_have),
                "must_not_have": ";".join(case.must_not_have),
                "gold_reference_pages": ";".join(case.gold_reference_pages),
                "model": "",
                "task_type": "",
                "hit_current_page": "",
                "hit_correct_pages": "",
                "final_answer_summary": "",
                "task_completion": "",
                "lab_context_fit": "",
                "current_page_use": "",
                "structure_usability": "",
                "boundary_honesty": "",
                "penalty_off_topic": "",
                "penalty_index_as_answer": "",
                "failure_tags": "",
                "optimization_note": "",
                "evidence_ref": "",
            }
        )
    return rows


def load_scores_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, Any]] = []
        for row in reader:
            normalized = {key: (value or "").strip() for key, value in row.items()}
            normalized["failure_tags"] = [
                tag.strip()
                for tag in normalized.get("failure_tags", "").split(";")
                if tag.strip()
            ]
            rows.append(normalized)
    return rows


def _safe_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(value)


def _normalize_failure_tags(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [tag.strip() for tag in value.split(";") if tag.strip()]
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    return [str(value).strip()]


def _compute_total_score(row: dict[str, Any]) -> int:
    score = sum(_safe_int(row.get(field)) for field in SCORE_FIELDS)
    penalties = sum(_safe_int(row.get(field)) for field in PENALTY_FIELDS)
    return max(0, min(10, score - penalties))


def _grade_for_score(score: float) -> str:
    for threshold, label in GRADE_BANDS:
        if score >= threshold:
            return label
    return "needs_work"


def summarize_student_eval(
    cases: list[StudentEvalCase],
    score_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    case_map = {case.id: case for case in cases}
    enriched_rows: list[dict[str, Any]] = []
    category_scores: dict[str, list[int]] = defaultdict(list)
    failure_counter: Counter[str] = Counter()
    grade_counter: Counter[str] = Counter()

    for row in score_rows:
        case_id = row["case_id"]
        if case_id not in case_map:
            raise ValueError(f"Unknown case_id in score sheet: {case_id}")
        case = case_map[case_id]
        total_score = _compute_total_score(row)
        grade = _grade_for_score(float(total_score))
        category_scores[case.category].append(total_score)
        grade_counter[grade] += 1
        normalized_failure_tags = _normalize_failure_tags(row.get("failure_tags"))
        for tag in normalized_failure_tags:
            failure_counter[tag] += 1
        enriched_rows.append(
            {
                **row,
                "category": case.category,
                "question": case.question,
                "current_page": case.current_page,
                "eval_type": case.eval_type,
                "total_score": total_score,
                "grade": grade,
                "failure_tags": normalized_failure_tags,
            }
        )

    overall_average = round(
        sum(item["total_score"] for item in enriched_rows) / len(enriched_rows), 2
    ) if enriched_rows else 0.0

    category_summary: dict[str, dict[str, Any]] = {}
    for category in sorted({case.category for case in cases}):
        scores = category_scores.get(category, [])
        category_rows = [row for row in enriched_rows if row["category"] == category]
        category_summary[category] = {
            "case_count": len(scores),
            "average_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "lowest_cases": [
                {
                    "case_id": row["case_id"],
                    "question": row["question"],
                    "score": row["total_score"],
                    "failure_tags": row.get("failure_tags") or [],
                }
                for row in sorted(
                    category_rows,
                    key=lambda item: (item["total_score"], item["case_id"]),
                )[:2]
            ],
        }

    failure_rows = []
    for tag, count in failure_counter.items():
        config = FAILURE_PRIORITY.get(
            tag,
            {
                "priority": "P2",
                "weight": 0,
                "recommended_focus": "补充失败标签定义并确定优化落点。",
            },
        )
        failure_rows.append(
            {
                "tag": tag,
                "count": count,
                "priority": config["priority"],
                "recommended_focus": config["recommended_focus"],
                "_weight": config["weight"],
            }
        )
    failure_rows.sort(key=lambda item: (-item["count"], item["tag"]))

    optimization_priorities = sorted(
        failure_rows,
        key=lambda item: (-item["_weight"], -item["count"], item["tag"]),
    )[:5]

    for item in failure_rows:
        item.pop("_weight", None)
    for item in optimization_priorities:
        item.pop("_weight", None)

    return {
        "overall": {
            "case_count": len(enriched_rows),
            "average_score": overall_average,
            "grade": _grade_for_score(overall_average),
            "grade_distribution": dict(grade_counter),
        },
        "categories": category_summary,
        "failure_tags": failure_rows,
        "top_optimization_priorities": optimization_priorities,
        "rows": enriched_rows,
        "scoring_standard": {
            "dimensions": SCORE_FIELDS,
            "penalties": PENALTY_FIELDS,
            "bands": [
                {"label": label, "min_score": threshold}
                for threshold, label in GRADE_BANDS
            ],
        },
    }


def render_markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Assistant Student Evaluation Report",
        "",
        "## Overview",
        f"- Cases scored: {summary['overall']['case_count']}",
        f"- Average score: {summary['overall']['average_score']}",
        f"- Grade: {summary['overall']['grade']}",
        "",
        "## Category Results",
    ]
    for category, bucket in summary["categories"].items():
        lines.append(
            f"- {category}: average {bucket['average_score']} ({bucket['case_count']} scored)"
        )
        for case in bucket["lowest_cases"]:
            lines.append(
                f"  - lowest: {case['case_id']} ({case['score']})"
            )

    lines.extend(["", "## Top Failure Tags"])
    if summary["failure_tags"]:
        for item in summary["failure_tags"][:5]:
            lines.append(
                f"- {item['tag']}: {item['count']} [{item['priority']}]"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Top Optimization Priorities"])
    if summary["top_optimization_priorities"]:
        for item in summary["top_optimization_priorities"]:
            lines.append(
                f"- {item['priority']} {item['tag']}: {item['recommended_focus']}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def _write_template_csv(path: Path, cases: list[StudentEvalCase]) -> None:
    rows = build_score_template_rows(cases)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build student-facing assistant evaluation assets and reports.")
    parser.add_argument("--cases", type=Path, default=None, help="Optional JSON file with evaluation cases.")
    parser.add_argument("--scores", type=Path, default=None, help="CSV score sheet for completed evaluations.")
    parser.add_argument("--template-output", type=Path, default=None, help="Optional path for a blank CSV score sheet.")
    parser.add_argument("--json-output", type=Path, default=None, help="Optional path for the JSON summary.")
    parser.add_argument("--markdown-output", type=Path, default=None, help="Optional path for the Markdown summary.")
    args = parser.parse_args()

    cases = load_cases(args.cases)

    if args.template_output:
        args.template_output.parent.mkdir(parents=True, exist_ok=True)
        _write_template_csv(args.template_output, cases)

    if not args.scores:
        if args.template_output:
            print(
                json.dumps(
                    {
                        "template_rows": len(cases),
                        "template_output": str(args.template_output),
                        "category_count": len({case.category for case in cases}),
                    },
                    ensure_ascii=False,
                )
            )
            return
        raise SystemExit("Provide --scores to build a report, or --template-output to export a blank score sheet.")

    rows = load_scores_csv(args.scores)
    summary = summarize_student_eval(cases, rows)
    markdown = render_markdown_report(summary)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown, encoding="utf-8")

    if args.json_output or args.markdown_output:
        print(
            json.dumps(
                {
                    "overall_average_score": summary["overall"]["average_score"],
                    "cases_scored": summary["overall"]["case_count"],
                    "json_output": str(args.json_output) if args.json_output else None,
                    "markdown_output": str(args.markdown_output) if args.markdown_output else None,
                },
                ensure_ascii=False,
            )
        )
        return

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
