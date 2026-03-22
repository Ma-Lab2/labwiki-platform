from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..db import session_scope
from .llm import LLMClient
from .search import keyword_search_chunks, normalize_query_text, search_chunks
from .vector_store import build_vector_store


DEFAULT_CASES_PATH = Path("/app/app/benchmarks/retrieval_cases.json")


@dataclass(frozen=True)
class RetrievalCase:
    name: str
    category: str
    query: str
    source_types: list[str]
    expected_titles: list[str]


def _load_cases(path: Path | None) -> list[RetrievalCase]:
    source = path or DEFAULT_CASES_PATH
    raw_cases = json.loads(source.read_text(encoding="utf-8"))
    return [
        RetrievalCase(
            name=item["name"],
            category=item.get("category") or "general",
            query=item["query"],
            source_types=item.get("source_types") or [],
            expected_titles=item.get("expected_titles") or [],
        )
        for item in raw_cases
    ]


def _matches_expected(hit: dict[str, Any], expected_titles: list[str]) -> bool:
    title = (hit.get("title") or "").lower()
    source_id = (hit.get("source_id") or "").lower()
    return any(expected.lower() in title or expected.lower() in source_id for expected in expected_titles)


def _evaluate_hits(hits: list[dict[str, Any]], expected_titles: list[str]) -> dict[str, Any]:
    matched_rank = None
    matched_title = None
    for index, hit in enumerate(hits, start=1):
        if _matches_expected(hit, expected_titles):
            matched_rank = index
            matched_title = hit.get("title") or hit.get("source_id")
            break
    return {
        "matched": matched_rank is not None,
        "matched_rank": matched_rank,
        "matched_title": matched_title,
        "top_titles": [item.get("title") or item.get("source_id") for item in hits[:5]],
    }


def run_benchmark(
    *,
    vector_backends: list[str],
    tokenizer_modes: list[str],
    normalization_modes: list[str],
    strategies: list[str],
    limit: int,
    cases_path: Path | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    llm = LLMClient(settings)
    cases = _load_cases(cases_path)

    with session_scope() as db:
        rows: list[dict[str, Any]] = []
        for case in cases:
            for normalization_mode in normalization_modes:
                normalized_query = normalize_query_text(case.query, mode=normalization_mode)
                query_embedding = None
                if llm.embedding_provider.enabled:
                    embedded = llm.embed([normalized_query])
                    query_embedding = embedded[0] if embedded else None
                for vector_backend in vector_backends:
                    vector_store = build_vector_store(
                        vector_backend,
                        db=db,
                        embedding_dimensions=settings.embedding_dimensions,
                    )
                    for tokenizer_mode in tokenizer_modes:
                        for strategy in strategies:
                            if strategy == "keyword":
                                hits = keyword_search_chunks(
                                    db,
                                    case.query,
                                    source_types=case.source_types,
                                    limit=limit,
                                    tokenizer_mode=tokenizer_mode,
                                    normalization_mode=normalization_mode,
                                )
                            elif strategy == "vector":
                                hits = vector_store.search(
                                    query_embedding=query_embedding or [],
                                    source_types=case.source_types,
                                    limit=limit,
                                ) if query_embedding else []
                            elif strategy == "hybrid":
                                hits = search_chunks(
                                    db,
                                    case.query,
                                    source_types=case.source_types,
                                    limit=limit,
                                    query_embedding=query_embedding,
                                    tokenizer_mode=tokenizer_mode,
                                    normalization_mode=normalization_mode,
                                    vector_store=vector_store,
                                )
                            else:
                                raise ValueError(f"Unsupported strategy: {strategy}")

                            evaluation = _evaluate_hits(hits, case.expected_titles)
                            rows.append({
                                "case": case.name,
                                "category": case.category,
                                "query": case.query,
                                "strategy": strategy,
                                "vector_backend": vector_backend,
                                "tokenizer_mode": tokenizer_mode,
                                "normalization_mode": normalization_mode,
                                "matched": evaluation["matched"],
                                "matched_rank": evaluation["matched_rank"],
                                "matched_title": evaluation["matched_title"],
                                "top_titles": evaluation["top_titles"],
                            })

    summary: dict[str, dict[str, Any]] = {}
    category_summary: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = f"{row['vector_backend']}::{row['strategy']}::{row['tokenizer_mode']}::{row['normalization_mode']}"
        bucket = summary.setdefault(key, {"total": 0, "matched": 0, "avg_rank_numerator": 0})
        bucket["total"] += 1
        if row["matched"]:
            bucket["matched"] += 1
            bucket["avg_rank_numerator"] += row["matched_rank"] or 0

        category_bucket = category_summary.setdefault(key, {}).setdefault(
            row["category"],
            {"total": 0, "matched": 0, "avg_rank_numerator": 0},
        )
        category_bucket["total"] += 1
        if row["matched"]:
            category_bucket["matched"] += 1
            category_bucket["avg_rank_numerator"] += row["matched_rank"] or 0

    for key, bucket in summary.items():
        bucket["recall_at_k"] = round(bucket["matched"] / bucket["total"], 3) if bucket["total"] else 0.0
        bucket["avg_rank"] = (
            round(bucket["avg_rank_numerator"] / bucket["matched"], 3)
            if bucket["matched"]
            else None
        )
        bucket.pop("avg_rank_numerator", None)

    for strategy_key, categories in category_summary.items():
        for category, bucket in categories.items():
            bucket["recall_at_k"] = round(bucket["matched"] / bucket["total"], 3) if bucket["total"] else 0.0
            bucket["avg_rank"] = (
                round(bucket["avg_rank_numerator"] / bucket["matched"], 3)
                if bucket["matched"]
                else None
            )
            bucket.pop("avg_rank_numerator", None)

    leaderboard = []
    for key, bucket in summary.items():
        vector_backend, strategy, tokenizer_mode, normalization_mode = key.split("::", 3)
        leaderboard.append({
            "vector_backend": vector_backend,
            "strategy": strategy,
            "tokenizer_mode": tokenizer_mode,
            "normalization_mode": normalization_mode,
            "total": bucket["total"],
            "matched": bucket["matched"],
            "recall_at_k": bucket["recall_at_k"],
            "avg_rank": bucket["avg_rank"],
        })
    leaderboard.sort(
        key=lambda item: (
            -item["recall_at_k"],
            item["avg_rank"] if item["avg_rank"] is not None else 999.0,
            item["vector_backend"],
            item["strategy"],
            item["tokenizer_mode"],
            item["normalization_mode"],
        )
    )

    misses: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["matched"]:
            continue
        key = f"{row['vector_backend']}::{row['strategy']}::{row['tokenizer_mode']}::{row['normalization_mode']}"
        misses.setdefault(key, []).append({
            "case": row["case"],
            "category": row["category"],
            "query": row["query"],
            "top_titles": row["top_titles"],
        })

    return {
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "vector_backends": vector_backends,
        "tokenizer_modes": tokenizer_modes,
        "normalization_modes": normalization_modes,
        "strategies": strategies,
        "limit": limit,
        "rows": rows,
        "summary": summary,
        "category_summary": category_summary,
        "leaderboard": leaderboard,
        "misses": misses,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark assistant retrieval strategies and tokenizer modes.")
    parser.add_argument("--cases", type=Path, default=None, help="Optional JSON file with retrieval benchmark cases.")
    parser.add_argument("--limit", type=int, default=5, help="Top-k limit for each retrieval run.")
    parser.add_argument(
        "--tokenizer-mode",
        action="append",
        dest="tokenizer_modes",
        help="Tokenizer mode to include. Repeat for multiple values. Defaults to mixed/ascii/cjk.",
    )
    parser.add_argument(
        "--normalization-mode",
        action="append",
        dest="normalization_modes",
        help="Normalization mode to include. Repeat for multiple values. Defaults to basic/lab.",
    )
    parser.add_argument(
        "--vector-backend",
        action="append",
        dest="vector_backends",
        help="Vector backend to include. Repeat for multiple values. Defaults to pgvector/qdrant_local.",
    )
    parser.add_argument(
        "--strategy",
        action="append",
        dest="strategies",
        help="Retrieval strategy to include. Repeat for multiple values. Defaults to keyword/vector/hybrid.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write the JSON report.")
    args = parser.parse_args()

    tokenizer_modes = args.tokenizer_modes or ["mixed", "ascii", "cjk"]
    normalization_modes = args.normalization_modes or ["basic", "lab"]
    vector_backends = args.vector_backends or ["pgvector", "qdrant_local"]
    strategies = args.strategies or ["keyword", "vector", "hybrid"]
    report = run_benchmark(
        vector_backends=vector_backends,
        tokenizer_modes=tokenizer_modes,
        normalization_modes=normalization_modes,
        strategies=strategies,
        limit=args.limit,
        cases_path=args.cases,
    )
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
