from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..constants import STRUCTURED_SOURCE_TYPES
from ..models import DocumentChunk
from .vector_store import PgVectorStore, VectorStore


ASCII_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+\-./]*")
LAB_ALIAS_GROUPS = {
    "tnsa": [
        "tnsa",
        "target normal sheath acceleration",
        "靶法向鞘层加速",
        "靶后法向鞘层加速",
    ],
    "tps": [
        "tps",
        "thomson parabola spectrometer",
        "thomson parabola",
        "解谱",
        "能谱",
    ],
    "rcf": [
        "rcf",
        "radiochromic film",
        "胶片堆栈",
        "堆栈",
    ],
    "shot_log": [
        "周实验日志",
        "周日志",
        "weekly shot log",
        "shot日志",
        "shot log",
    ],
    "shot_record": [
        "shot记录",
        "shot 记录",
        "shot表单",
        "shot form",
        "打靶记录",
    ],
}


def normalize_query_text(text: str, *, mode: str = "basic") -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    normalized = normalized.replace("（", "(").replace("）", ")").replace("：", ":")
    if mode == "basic":
        return normalized

    lowered = normalized.lower()
    expansion_tokens: list[str] = []
    for aliases in LAB_ALIAS_GROUPS.values():
        if any(alias.lower() in lowered or alias in normalized for alias in aliases):
            expansion_tokens.extend(aliases)
    if not expansion_tokens:
        return normalized
    return f"{normalized} {' '.join(expansion_tokens)}"


def _cjk_chars(text: str) -> list[str]:
    return [char for char in text if "\u4e00" <= char <= "\u9fff"]


def _cjk_ngrams(text: str) -> list[str]:
    chars = _cjk_chars(text)
    if not chars:
        return []
    grams = chars[:]
    grams.extend("".join(chars[index:index + 2]) for index in range(len(chars) - 1))
    return grams


def tokenize(text: str, *, mode: str = "mixed") -> list[str]:
    lowered = text.lower()
    ascii_tokens = ASCII_TOKEN_RE.findall(lowered)
    if mode == "ascii":
        raw_tokens = ascii_tokens
    elif mode == "cjk":
        raw_tokens = _cjk_ngrams(text)
    else:
        raw_tokens = ascii_tokens + _cjk_ngrams(text)

    seen: set[str] = set()
    ordered: list[str] = []
    for token in raw_tokens:
        if token and token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def _score(query_tokens: list[str], title: str, heading: str | None, content: str) -> float:
    haystack = f"{title} {heading or ''} {content}".lower()
    counts = Counter(ASCII_TOKEN_RE.findall(haystack))
    score = 0.0
    for token in query_tokens:
        if token in haystack:
            score += 1.0
            score += counts.get(token, 0) * 0.15
    if title:
        title_lower = title.lower()
        score += sum(0.8 for token in query_tokens if token in title_lower)
    return score


def _serialize_chunk(chunk: DocumentChunk, score: float) -> dict[str, Any]:
    return {
        "source_type": chunk.document.source_type,
        "source_id": chunk.document.source_id,
        "title": chunk.document.title,
        "url": chunk.document.url,
        "heading": chunk.heading,
        "snippet": chunk.snippet or chunk.content[:280],
        "content": chunk.content,
        "score": score,
    }


def keyword_search_chunks(
    db: Session,
    query: str,
    *,
    source_types: list[str] | None = None,
    limit: int = 8,
    tokenizer_mode: str = "mixed",
    normalization_mode: str = "basic",
) -> list[dict[str, Any]]:
    normalized_query = normalize_query_text(query, mode=normalization_mode)
    query_tokens = tokenize(normalized_query, mode=tokenizer_mode)
    if not query_tokens:
        return []

    stmt = select(DocumentChunk).options(joinedload(DocumentChunk.document))
    chunks = db.execute(stmt).scalars().all()
    ranked = []
    for chunk in chunks:
        if source_types and chunk.document.source_type not in source_types:
            continue
        score = _score(query_tokens, chunk.document.title, chunk.heading, chunk.content)
        if score <= 0:
            continue
        if chunk.document.source_type in STRUCTURED_SOURCE_TYPES:
            score += 0.25
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [_serialize_chunk(chunk, score) for score, chunk in ranked[: max(limit * 2, 12)]]


def _rrf_merge(keyword_hits: list[dict[str, Any]], vector_hits: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    scores: Counter[tuple[str, str]] = Counter()
    for rank, item in enumerate(keyword_hits, start=1):
        key = (item["source_type"], item["source_id"])
        scores[key] += 1.0 / (50 + rank)
        merged.setdefault(key, item)
    for rank, item in enumerate(vector_hits, start=1):
        key = (item["source_type"], item["source_id"])
        scores[key] += 1.0 / (50 + rank)
        if key not in merged or item.get("score", 0.0) > merged[key].get("score", 0.0):
            merged[key] = item
    ranked = sorted(
        merged.items(),
        key=lambda row: (scores[row[0]], row[1].get("score", 0.0)),
        reverse=True,
    )
    return [item for _, item in ranked[:limit]]


def search_chunks(
    db: Session,
    query: str,
    source_types: list[str] | None = None,
    limit: int = 8,
    query_embedding: list[float] | None = None,
    tokenizer_mode: str = "mixed",
    normalization_mode: str = "basic",
    vector_store: VectorStore | None = None,
) -> list[dict[str, Any]]:
    keyword_hits = keyword_search_chunks(
        db,
        query,
        source_types=source_types,
        limit=limit,
        tokenizer_mode=tokenizer_mode,
        normalization_mode=normalization_mode,
    )
    vector_hits: list[dict[str, Any]] = []
    if query_embedding:
        vector_backend = vector_store or PgVectorStore(db)
        vector_hits = vector_backend.search(
            query_embedding=query_embedding,
            source_types=source_types,
            limit=limit,
        )

    if keyword_hits and vector_hits:
        return _rrf_merge(keyword_hits, vector_hits, limit)
    if vector_hits:
        return vector_hits[:limit]
    return keyword_hits[:limit]
