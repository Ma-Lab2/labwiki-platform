from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from qdrant_client import QdrantClient
from qdrant_client import models as qmodels
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..constants import STRUCTURED_SOURCE_TYPES
from ..models import Document, DocumentChunk


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


class VectorStore(Protocol):
    def search(
        self,
        *,
        query_embedding: list[float],
        source_types: list[str] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        ...


@dataclass
class PgVectorStore:
    db: Session

    def search(
        self,
        *,
        query_embedding: list[float],
        source_types: list[str] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .options(joinedload(DocumentChunk.document))
            .where(DocumentChunk.embedding.is_not(None))
        )
        if source_types:
            stmt = stmt.where(Document.source_type.in_(source_types))
        rows = self.db.execute(stmt.order_by("distance").limit(max(limit * 2, 12))).all()
        hits: list[dict[str, Any]] = []
        for chunk, distance in rows:
            similarity = max(0.0, 1.0 - float(distance))
            score = similarity + (0.2 if chunk.document.source_type in STRUCTURED_SOURCE_TYPES else 0.0)
            hits.append(_serialize_chunk(chunk, score))
        return hits[:limit]


@dataclass
class QdrantLocalVectorStore:
    db: Session
    embedding_dimensions: int
    client: QdrantClient = field(default_factory=lambda: QdrantClient(location=":memory:"))
    collection_name: str = "assistant_chunks"
    _indexed: bool = field(default=False, init=False)

    def _ensure_index(self) -> None:
        if self._indexed:
            return
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(
                size=self.embedding_dimensions,
                distance=qmodels.Distance.COSINE,
            ),
        )
        stmt = (
            select(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .options(joinedload(DocumentChunk.document))
            .where(DocumentChunk.embedding.is_not(None))
        )
        chunks = self.db.execute(stmt).scalars().all()
        if not chunks:
            self._indexed = True
            return
        points = [
            qmodels.PointStruct(
                id=int(chunk.id),
                vector=chunk.embedding,
                payload={
                    "source_type": chunk.document.source_type,
                    "source_id": chunk.document.source_id,
                    "title": chunk.document.title,
                    "url": chunk.document.url,
                    "heading": chunk.heading,
                    "snippet": chunk.snippet or chunk.content[:280],
                    "content": chunk.content,
                },
            )
            for chunk in chunks
            if chunk.embedding is not None
        ]
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        self._indexed = True

    def search(
        self,
        *,
        query_embedding: list[float],
        source_types: list[str] | None = None,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        self._ensure_index()
        if not query_embedding:
            return []
        points = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=max(limit * 2, 12),
            with_payload=True,
        )
        hits: list[dict[str, Any]] = []
        for point in points:
            payload = point.payload or {}
            if source_types and payload.get("source_type") not in source_types:
                continue
            score = float(point.score) + (0.2 if payload.get("source_type") in STRUCTURED_SOURCE_TYPES else 0.0)
            hits.append({
                "source_type": payload.get("source_type"),
                "source_id": payload.get("source_id"),
                "title": payload.get("title"),
                "url": payload.get("url"),
                "heading": payload.get("heading"),
                "snippet": payload.get("snippet"),
                "content": payload.get("content", ""),
                "score": score,
            })
        return hits[:limit]


def build_vector_store(
    backend: str,
    *,
    db: Session,
    embedding_dimensions: int,
) -> VectorStore:
    if backend == "pgvector":
        return PgVectorStore(db)
    if backend == "qdrant_local":
        return QdrantLocalVectorStore(db=db, embedding_dimensions=embedding_dimensions)
    raise ValueError(f"Unsupported vector store backend: {backend}")
