from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..clients.openalex import OpenAlexClient
from ..config import Settings
from ..constants import SourceType
from .llm import LLMClient
from .search import normalize_query_text, search_chunks
from .vector_store import build_vector_store, VectorStore


def normalize_query(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    cleaned = cleaned.replace("（", "(").replace("）", ")")
    return cleaned


@dataclass
class RetrievalBroker:
    db: Session
    settings: Settings
    llm: LLMClient
    openalex: OpenAlexClient
    vector_store: VectorStore | None = None

    def __post_init__(self) -> None:
        if self.vector_store is None:
            self.vector_store = build_vector_store(
                self.settings.vector_store_backend,
                db=self.db,
                embedding_dimensions=self.settings.embedding_dimensions,
            )

    def search_local(
        self,
        query: str,
        *,
        source_types: list[str] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        normalized = normalize_query_text(
            normalize_query(query),
            mode=self.settings.retrieval_normalization_mode,
        )
        query_embedding = self.llm.embed([normalized])
        return search_chunks(
            self.db,
            normalized,
            source_types=source_types,
            limit=limit,
            query_embedding=query_embedding[0] if query_embedding else None,
            tokenizer_mode=self.settings.retrieval_tokenizer_mode,
            normalization_mode=self.settings.retrieval_normalization_mode,
            vector_store=self.vector_store,
        )

    def search_openalex(self, query: str, *, limit: int = 4) -> list[dict[str, Any]]:
        return self.openalex.search(normalize_query(query), limit=limit)

    def search_web(self, query: str, *, limit: int = 4) -> list[dict[str, Any]]:
        hits = self.llm.search_web(normalize_query(query), limit=limit)
        return [
            {
                "source_type": item.get("source_type") or SourceType.WEB.value,
                "source_id": item.get("source_id") or item.get("url") or f"web:{index}",
                "title": item.get("title") or item.get("source_id") or "Web result",
                "url": item.get("url"),
                "snippet": item.get("snippet"),
                "content": item.get("content", ""),
                "score": float(item.get("score", 0.0)),
            }
            for index, item in enumerate(hits, start=1)
        ]
