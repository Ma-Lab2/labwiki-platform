from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .student_eval_report import StudentEvalCase, load_cases


def mode_for_case(case: StudentEvalCase) -> str:
    if case.eval_type == "compare":
        return "compare"
    if case.eval_type in {"draft", "write_preview", "write"}:
        return "draft"
    return "qa"


def build_chat_payload(case: StudentEvalCase, *, generation_model: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "question": case.question,
        "mode": mode_for_case(case),
        "detail_level": "intro",
        "context_pages": [case.current_page] if case.current_page else [],
        "generation_model": generation_model,
    }
    return payload


def summarize_error(error: Exception) -> dict[str, Any]:
    message = f"{type(error).__name__}: {error}"
    lowered = message.lower()
    if "timed out" in lowered or "timeout" in lowered:
        return {"error": message, "error_kind": "timeout", "retryable": True}
    if "http error 429" in lowered:
        return {"error": message, "error_kind": "http_429", "retryable": True}
    if "http error 500" in lowered:
        return {"error": message, "error_kind": "http_500", "retryable": True}
    if "http error 5" in lowered:
        return {"error": message, "error_kind": "http_5xx", "retryable": True}
    if "http error 4" in lowered:
        return {"error": message, "error_kind": "http_4xx", "retryable": False}
    if "connection" in lowered or "refused" in lowered or "reset" in lowered:
        return {"error": message, "error_kind": "connection", "retryable": True}
    return {"error": message, "error_kind": "unknown", "retryable": False}


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def run_student_eval(
    *,
    base_url: str,
    generation_model: str,
    timeout_seconds: int,
    retries: int,
    retry_delay_seconds: float,
    cases_path: Path | None = None,
    case_ids: set[str] | None = None,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    if case_ids:
        cases = [case for case in cases if case.id in case_ids]

    rows: list[dict[str, Any]] = []
    started_at = time.time()

    for index, case in enumerate(cases, start=1):
        payload = build_chat_payload(case, generation_model=generation_model)
        attempts = 0
        last_error: str | None = None
        response_data: dict[str, Any] | None = None
        elapsed_ms: float | None = None
        while attempts <= retries:
            attempts += 1
            call_started = time.time()
            try:
                response_data = _post_json(f"{base_url.rstrip('/')}/chat", payload, timeout_seconds)
                elapsed_ms = round((time.time() - call_started) * 1000, 1)
                break
            except Exception as exc:  # noqa: BLE001
                elapsed_ms = round((time.time() - call_started) * 1000, 1)
                last_error = summarize_error(exc)
                if attempts > retries:
                    break
                time.sleep(retry_delay_seconds)

        row = {
            "case_id": case.id,
            "category": case.category,
            "question": case.question,
            "current_page": case.current_page,
            "eval_type": case.eval_type,
            "request_payload": payload,
            "attempts": attempts,
            "elapsed_ms": elapsed_ms,
            "error": last_error["error"] if last_error else None,
            "error_kind": last_error["error_kind"] if last_error else None,
            "retryable": last_error["retryable"] if last_error else None,
            "response": response_data,
        }
        rows.append(row)

    total_elapsed_ms = round((time.time() - started_at) * 1000, 1)
    success_count = sum(1 for row in rows if row["response"] is not None)

    return {
        "generation_model": generation_model,
        "base_url": base_url,
        "case_count": len(rows),
        "success_count": success_count,
        "failure_count": len(rows) - success_count,
        "total_elapsed_ms": total_elapsed_ms,
        "rows": rows,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the student evaluation prompt set against the live assistant API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Assistant API base URL.")
    parser.add_argument("--cases", type=Path, default=None, help="Optional case JSON path.")
    parser.add_argument("--case-id", action="append", dest="case_ids", help="Repeatable case id filter.")
    parser.add_argument("--generation-model", default="gpt-5.4-mini", help="Generation model to use.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=1, help="Retry count per case on request failure.")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Delay between retries in seconds.")
    parser.add_argument("--output", type=Path, default=None, help="Optional file path for JSON output.")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.case_ids:
        case_filter = set(args.case_ids)
        cases = [case for case in cases if case.id in case_filter]

    rows: list[dict[str, Any]] = []
    started_at = time.time()
    output_path = args.output

    for case in cases:
        single_report = run_student_eval(
            base_url=args.base_url,
            generation_model=args.generation_model,
            timeout_seconds=args.timeout,
            retries=args.retries,
            retry_delay_seconds=args.retry_delay,
            cases_path=args.cases,
            case_ids={case.id},
        )
        rows.extend(single_report["rows"])
        running_report = {
            "generation_model": args.generation_model,
            "base_url": args.base_url,
            "case_count": len(cases),
            "success_count": sum(1 for row in rows if row["response"] is not None),
            "failure_count": sum(1 for row in rows if row["response"] is None),
            "total_elapsed_ms": round((time.time() - started_at) * 1000, 1),
            "rows": rows,
        }
        if output_path:
            _write_report(output_path, running_report)

    report = {
        "generation_model": args.generation_model,
        "base_url": args.base_url,
        "case_count": len(cases),
        "success_count": sum(1 for row in rows if row["response"] is not None),
        "failure_count": sum(1 for row in rows if row["response"] is None),
        "total_elapsed_ms": round((time.time() - started_at) * 1000, 1),
        "rows": rows,
    }

    if output_path:
        _write_report(output_path, report)
        print(
            json.dumps(
                {
                    "generation_model": report["generation_model"],
                    "case_count": report["case_count"],
                    "success_count": report["success_count"],
                    "failure_count": report["failure_count"],
                    "output": str(output_path),
                },
                ensure_ascii=False,
            )
        )
        return

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
