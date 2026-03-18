from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..clients.wiki import MediaWikiClient
from ..config import Settings
from ..constants import SourceType
from ..models import Document, DocumentChunk, Job
from .audit import log_audit
from .chunking import chunk_wiki_text
from .llm import LLMClient


def upsert_document(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    title: str,
    url: str | None,
    namespace: str | None,
    metadata_json: dict[str, Any] | None,
    raw_text: str,
    chunks: list[dict[str, str]],
    embeddings: list[list[float]] | None = None,
) -> None:
    doc = db.execute(
        select(Document).where(Document.source_type == source_type, Document.source_id == source_id)
    ).scalar_one_or_none()
    if doc is None:
        doc = Document(
            source_type=source_type,
            source_id=source_id,
            title=title,
            url=url,
            namespace=namespace,
            metadata_json=metadata_json,
            raw_text=raw_text,
        )
        db.add(doc)
        db.flush()
    else:
        doc.title = title
        doc.url = url
        doc.namespace = namespace
        doc.metadata_json = metadata_json
        doc.raw_text = raw_text
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
        db.flush()

    for index, chunk in enumerate(chunks):
        vector = None
        if embeddings and index < len(embeddings):
            vector = embeddings[index]
        db.add(DocumentChunk(
            document_id=doc.id,
            chunk_index=index,
            heading=chunk.get("heading"),
            content=chunk["content"],
            snippet=chunk.get("snippet"),
            embedding=vector,
        ))


def reindex_wiki(db: Session, settings: Settings, llm: LLMClient) -> dict[str, Any]:
    wiki = MediaWikiClient(settings)
    namespaces = [0, 10, 106]
    titles = wiki.iter_all_pages(namespaces)
    indexed = 0

    for title in titles:
        raw_text = wiki.get_page_text(title)
        if not raw_text.strip():
            continue
        chunks = chunk_wiki_text(raw_text)
        embeddings = llm.embed([chunk["content"][:3000] for chunk in chunks]) if chunks else None
        upsert_document(
            db,
            source_type=SourceType.WIKI.value,
            source_id=title,
            title=title,
            url=wiki.page_url(title),
            namespace=title.split(":", 1)[0] if ":" in title else "Main",
            metadata_json={"source": "mediawiki"},
            raw_text=raw_text,
            chunks=chunks,
            embeddings=embeddings,
        )
        indexed += 1

    cargo_specs = [
        ("lab_terms", "Page,name_zh,name_en,abbr,summary"),
        ("lab_devices", "Page,device_name,system_group,key_parameters,purpose"),
        ("lab_mechanisms", "Page,mechanism_name,english_name,core_driver,key_signals"),
        ("lab_diagnostics", "Page,diagnostic_name,measurement_target,primary_outputs,pitfalls"),
        ("lab_literature_guides", "Page,title_text,authors,pub_year,doi,summary"),
    ]
    cargo_indexed = 0
    for table_name, fields in cargo_specs:
        try:
            rows = wiki.cargo_query(table_name, fields, limit=500)
        except Exception:
            continue
        for row in rows:
            field_data = row.get("title") if isinstance(row.get("title"), dict) else row
            if not isinstance(field_data, dict):
                continue
            title = field_data.get("Page") or field_data.get("page") or table_name
            raw = "\n".join(
                f"{key}: {value}"
                for key, value in field_data.items()
                if value not in (None, "")
            )
            chunks = chunk_wiki_text(raw)
            upsert_document(
                db,
                source_type=SourceType.CARGO.value,
                source_id=f"{table_name}:{title}",
                title=title,
                url=wiki.page_url(title),
                namespace="Cargo",
                metadata_json={"table": table_name},
                raw_text=raw,
                chunks=chunks or [{"heading": table_name, "content": raw, "snippet": raw[:280]}],
            )
            cargo_indexed += 1

    log_audit(db, action_type="reindex_wiki", payload={"wiki_pages": indexed, "cargo_rows": cargo_indexed})
    return {"wiki_pages": indexed, "cargo_rows": cargo_indexed}


def _iter_snapshot_documents(root: Path):
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if path.suffix.lower() in {".json", ".md", ".txt"}:
            yield path


def reindex_zotero(db: Session, settings: Settings, llm: LLMClient) -> dict[str, Any]:
    root = Path(settings.zotero_snapshot_dir)
    if not root.exists():
        return {"zotero_items": 0}

    indexed = 0
    for path in _iter_snapshot_documents(root):
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            items = payload if isinstance(payload, list) else payload.get("items", [])
            for item in items:
                title = item.get("title") or item.get("data", {}).get("title") or item.get("key") or path.stem
                abstract = item.get("abstractNote") or item.get("abstract") or item.get("data", {}).get("abstractNote") or ""
                creators = item.get("creators") or item.get("data", {}).get("creators") or []
                creator_text = ", ".join(
                    creator.get("name") or " ".join(filter(None, [creator.get("firstName"), creator.get("lastName")]))
                    for creator in creators if isinstance(creator, dict)
                )
                raw_text = "\n".join(filter(None, [
                    title,
                    creator_text,
                    abstract,
                    item.get("url") or item.get("DOI") or item.get("data", {}).get("url"),
                ]))
                chunks = chunk_wiki_text(raw_text)
                upsert_document(
                    db,
                    source_type=SourceType.ZOTERO.value,
                    source_id=item.get("key") or f"{path.name}:{indexed}",
                    title=title,
                    url=item.get("url") or item.get("DOI") or item.get("data", {}).get("url"),
                    namespace="Zotero",
                    metadata_json={"file": str(path.relative_to(root))},
                    raw_text=raw_text,
                    chunks=chunks or [{"heading": "摘要", "content": raw_text, "snippet": raw_text[:280]}],
                )
                indexed += 1
        else:
            raw_text = path.read_text(encoding="utf-8", errors="ignore").strip()
            if not raw_text:
                continue
            chunks = chunk_wiki_text(raw_text)
            upsert_document(
                db,
                source_type=SourceType.ZOTERO.value,
                source_id=str(path.relative_to(root)),
                title=path.stem,
                url=None,
                namespace="Zotero",
                metadata_json={"file": str(path.relative_to(root))},
                raw_text=raw_text,
                chunks=chunks or [{"heading": "正文", "content": raw_text, "snippet": raw_text[:280]}],
            )
            indexed += 1

    log_audit(db, action_type="reindex_zotero", payload={"zotero_items": indexed})
    return {"zotero_items": indexed}


def create_job(db: Session, job_type: str, payload: dict[str, Any] | None = None) -> Job:
    job = Job(job_type=job_type, status="pending", payload=payload or {})
    db.add(job)
    db.flush()
    log_audit(db, action_type="job_created", payload={"job_id": job.id, "job_type": job_type})
    return job
