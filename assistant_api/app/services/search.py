from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..constants import STRUCTURED_SOURCE_TYPES
from ..models import DocumentChunk


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    for char in ",.;:!?()[]{}<>|/\\\n\t":
        text = text.replace(char, " ")
    return [token for token in text.split(" ") if token]


def _score(query_tokens: list[str], title: str, heading: str | None, content: str) -> float:
    haystack = f"{title} {heading or ''} {content}".lower()
    counts = Counter(haystack.split())
    score = 0.0
    for token in query_tokens:
        if token in haystack:
            score += 1.0
            score += counts.get(token, 0) * 0.15
    if title:
        title_lower = title.lower()
        score += sum(0.8 for token in query_tokens if token in title_lower)
    return score


def search_chunks(db: Session, query: str, source_types: list[str] | None = None, limit: int = 8) -> list[dict]:
    query_tokens = _tokenize(query)
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
    results = []
    for score, chunk in ranked[:limit]:
        results.append({
            "source_type": chunk.document.source_type,
            "source_id": chunk.document.source_id,
            "title": chunk.document.title,
            "url": chunk.document.url,
            "heading": chunk.heading,
            "snippet": chunk.snippet or chunk.content[:280],
            "content": chunk.content,
            "score": score,
        })
    return results
