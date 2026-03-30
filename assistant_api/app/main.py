from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select

from .clients.openalex import OpenAlexClient
from .clients.tools import ToolClients
from .clients.wiki import MediaWikiClient
from .config import get_settings
from .constants import AssistantMode
from .db import init_database, session_scope
from .models import AssistantSession, AssistantTurn, Document, DocumentChunk, DraftPreview, Job
from .schemas import (
    ActionCommitRequest,
    ActionCommitResponse,
    ActionPreviewRequest,
    ActionPreviewResponse,
    ActionTraceItem,
    AttachmentItem,
    CapabilityCatalogResponse,
    ChatRequest,
    ChatResponse,
    DraftCommitRequest,
    PdfControlCommitRequest,
    PdfControlCommitResponse,
    PdfControlPreviewPayload,
    PdfControlPreviewRequest,
    PdfDraftPreviewRequest,
    PdfIngestReviewPayload,
    DraftPreviewPayload,
    DraftPreviewRequest,
    IndexStatsResponse,
    JobStatusResponse,
    ModelCatalogResponse,
    OperationPreviewPayload,
    OperationResultPayload,
    PlanResponse,
    ResultFillPayload,
    ReindexResponse,
    SessionDetailResponse,
    SessionHistoryListItem,
    SessionHistoryListResponse,
    SessionModelUpdateRequest,
    SessionTurnPayload,
    SourceIndexStats,
    SourceItem,
    StepItem,
    StatsResponse,
    ToolExecuteRequest,
    WriteCommitRequest,
    WritePreviewPayload,
    WritePreviewRequest,
    WriteResultPayload,
)
from .services.llm import LLMClient
from .services.capabilities import build_capability_catalog, commit_capability_action, preview_capability_action
from .services.model_catalog import build_model_catalog, fallback_model_for, resolve_generation_selection
from .services.operation_payloads import derive_operation_preview, derive_operation_result
from .services.drafts import create_draft_preview, save_draft_preview
from .services.pdf_ingest import (
    commit_pdf_control_preview,
    commit_pdf_ingest_draft_preview,
    prepare_pdf_control_preview,
    prepare_pdf_draft_preview,
)
from .services.orchestrator import build_plan, run_chat, run_chat_stream
from .services.reindex import create_job
from .services.audit import log_audit
from .services.attachments import AttachmentStorageError, delete_attachment, load_attachment_file, store_attachment
from .services.write_actions import commit_write_preview, create_write_preview
from .services.session_exports import build_session_export_filename, build_session_markdown


settings = get_settings()
logger = logging.getLogger(__name__)
llm = LLMClient(settings)
wiki = MediaWikiClient(settings)
openalex = OpenAlexClient()
tools = ToolClients(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="LabWiki Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    started = time.perf_counter()
    with session_scope() as db:
        try:
            response = run_chat(db, settings, llm, wiki, openalex, tools, request)
            logger.info(
                "assistant.chat completed mode=%s session_id=%s model=%s elapsed_ms=%.1f",
                request.mode.value if request.mode else None,
                response.session_id,
                response.model_info.resolved_model if response.model_info else None,
                (time.perf_counter() - started) * 1000,
            )
            return response
        except Exception as error:
            logger.exception(
                "assistant.chat failed mode=%s session_id=%s elapsed_ms=%.1f",
                request.mode.value if request.mode else None,
                request.session_id,
                (time.perf_counter() - started) * 1000,
            )
            raise HTTPException(status_code=500, detail=str(error)) from error


def _format_sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _llm_for_generation_request(
    db,
    *,
    session_id: str | None,
    requested_provider: str | None,
    requested_model: str | None,
) -> LLMClient:
    session_record = db.get(AssistantSession, session_id) if session_id else None
    selection = resolve_generation_selection(
        settings,
        requested_provider=requested_provider,
        requested_model=requested_model,
        session_provider=session_record.generation_provider if session_record else None,
        session_model=session_record.generation_model if session_record else None,
    )
    if session_record is not None:
        session_record.generation_provider = selection.provider
        session_record.generation_model = selection.requested_model
        session_record.generation_fallback_model = fallback_model_for(selection.requested_model)
    return llm.with_generation_config(selection)


@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def event_stream():
        started = time.perf_counter()
        event_count = 0
        with session_scope() as db:
            try:
                for item in run_chat_stream(db, settings, llm, wiki, openalex, tools, request):
                    event_count += 1
                    yield _format_sse(item["event"], item["data"])
                logger.info(
                    "assistant.chat_stream completed mode=%s session_id=%s events=%s elapsed_ms=%.1f",
                    request.mode.value if request.mode else None,
                    request.session_id,
                    event_count,
                    (time.perf_counter() - started) * 1000,
                )
            except Exception as error:
                logger.exception(
                    "assistant.chat_stream failed mode=%s session_id=%s events=%s elapsed_ms=%.1f",
                    request.mode.value if request.mode else None,
                    request.session_id,
                    event_count,
                    (time.perf_counter() - started) * 1000,
                )
                yield _format_sse("error", {"detail": str(error)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/compare", response_model=ChatResponse)
def compare(request: ChatRequest) -> ChatResponse:
    request.mode = AssistantMode.COMPARE
    with session_scope() as db:
        try:
            return run_chat(db, settings, llm, wiki, openalex, tools, request)
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/plan", response_model=PlanResponse)
def plan(request: ChatRequest) -> PlanResponse:
    return build_plan(request.question, request.mode, request.context_pages, settings)


@app.get("/models/catalog", response_model=ModelCatalogResponse)
def models_catalog(include_all: bool = False) -> ModelCatalogResponse:
    try:
        payload = build_model_catalog(settings, include_all=include_all)
        return ModelCatalogResponse(**payload)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/capabilities", response_model=CapabilityCatalogResponse)
def capabilities_catalog() -> CapabilityCatalogResponse:
    try:
        payload = build_capability_catalog(settings)
        return CapabilityCatalogResponse(**payload)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/attachments", response_model=AttachmentItem)
async def upload_attachment(file: UploadFile = File(...)) -> AttachmentItem:
    try:
        payload = store_attachment(
            attachments_dir=Path(settings.attachments_dir),
            filename=file.filename or "attachment",
            content_type=file.content_type or "application/octet-stream",
            content=await file.read(),
        )
        return payload
    except AttachmentStorageError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.delete("/attachments/{attachment_id}")
def remove_attachment(attachment_id: str) -> dict[str, bool | str]:
    deleted = delete_attachment(
        attachments_dir=Path(settings.attachments_dir),
        attachment_id=attachment_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return {"attachment_id": attachment_id, "deleted": True}


@app.get("/attachments/{attachment_id}/content")
def get_attachment_content(attachment_id: str) -> FileResponse:
    try:
        item, blob_path = load_attachment_file(
            attachments_dir=Path(settings.attachments_dir),
            attachment_id=attachment_id,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Attachment not found") from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return FileResponse(
        path=blob_path,
        media_type=item.mime_type,
        filename=item.name,
    )


@app.post("/actions/preview", response_model=ActionPreviewResponse)
def action_preview(request: ActionPreviewRequest) -> ActionPreviewResponse:
    with session_scope() as db:
        request_llm = _llm_for_generation_request(
            db,
            session_id=request.session_id,
            requested_provider=request.generation_provider,
            requested_model=request.generation_model,
        )
        try:
            payload = preview_capability_action(
                db=db,
                settings=settings,
                llm=request_llm,
                wiki=wiki,
                tools=tools,
                action_id=request.action_id,
                request_payload={
                    "question": request.question,
                    "answer": request.answer,
                    "session_id": request.session_id,
                    "turn_id": request.turn_id,
                    "context_pages": request.context_pages,
                    "source_titles": request.source_titles,
                    "conversation_history": [],
                    **request.payload,
                },
            )
            return ActionPreviewResponse(**payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/actions/commit", response_model=ActionCommitResponse)
def action_commit(request: ActionCommitRequest) -> ActionCommitResponse:
    with session_scope() as db:
        try:
            payload = commit_capability_action(
                db=db,
                settings=settings,
                wiki=wiki,
                action_id=request.action_id,
                request_payload={
                    "preview_id": request.preview_id,
                    **request.payload,
                },
            )
            return ActionCommitResponse(**payload)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/tool/execute")
def execute_tool(request: ToolExecuteRequest) -> dict:
    with session_scope() as db:
        try:
            if request.tool.value == "tps":
                result = tools.tps_execute(request.action, request.payload)
            elif request.tool.value == "rcf":
                result = tools.rcf_execute(request.action, request.payload)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported tool: {request.tool.value}")
            log_audit(
                db,
                action_type="tool_execute",
                payload={"tool": request.tool.value, "action": request.action, "status": "ok"},
            )
            return result
        except HTTPException:
            raise
        except Exception as error:
            log_audit(
                db,
                action_type="tool_execute",
                payload={"tool": request.tool.value, "action": request.action, "status": "error", "detail": str(error)},
            )
            raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/draft/preview", response_model=DraftPreviewPayload)
def draft_preview(request: DraftPreviewRequest) -> DraftPreviewPayload:
    with session_scope() as db:
        request_llm = _llm_for_generation_request(
            db,
            session_id=request.session_id,
            requested_provider=request.generation_provider,
            requested_model=request.generation_model,
        )
        preview = create_draft_preview(
            db,
            settings,
            request_llm,
            session_id=request.session_id,
            turn_id=request.turn_id,
            question=request.question,
            answer=request.answer,
            source_titles=request.source_titles,
        )
        return DraftPreviewPayload(
            preview_id=preview.id,
            title=preview.title,
            target_page=preview.target_page,
            content=preview.content,
            metadata=preview.metadata_json,
        )


@app.post("/draft/commit")
def draft_commit(request: DraftCommitRequest) -> dict:
    with session_scope() as db:
        preview = db.get(DraftPreview, request.preview_id)
        if preview is None:
            raise HTTPException(status_code=404, detail="Draft preview not found")
        expected_prefix = f"{settings.draft_prefix}/"
        if not preview.target_page.startswith(expected_prefix):
            raise HTTPException(status_code=400, detail="Draft preview target page is outside the draft prefix")
        try:
            metadata = preview.metadata_json or {}
            if metadata.get("kind") == "pdf_ingest_draft":
                commit_pdf_ingest_draft_preview(wiki=wiki, preview=preview)
            else:
                wiki.edit_page(
                    preview.target_page,
                    preview.content,
                    "Create assistant draft preview",
                )
            log_audit(
                db,
                session_id=preview.session_id,
                turn_id=preview.turn_id,
                action_type="draft_commit",
                payload={"preview_id": preview.id, "page_title": preview.target_page},
            )
        except Exception as error:
            log_audit(
                db,
                session_id=preview.session_id,
                turn_id=preview.turn_id,
                action_type="draft_commit_error",
                payload={"preview_id": preview.id, "detail": str(error)},
            )
            raise HTTPException(status_code=500, detail=str(error)) from error
        return {"status": "ok", "page_title": preview.target_page}


@app.post("/pdf/draft/preview", response_model=DraftPreviewPayload)
def pdf_draft_preview(request: PdfDraftPreviewRequest) -> DraftPreviewPayload:
    with session_scope() as db:
        try:
            prepared = prepare_pdf_draft_preview(
                settings=settings,
                attachments_dir=Path(settings.attachments_dir),
                attachment_id=request.attachment_id,
                review=request.review.model_dump(),
            )
            preview = save_draft_preview(
                db,
                session_id=request.session_id,
                turn_id=request.turn_id,
                title=prepared["title"],
                target_page=prepared["target_page"],
                content=prepared["content"],
                metadata_json=prepared["metadata_json"],
            )
            return DraftPreviewPayload(
                preview_id=preview.id,
                title=preview.title,
                target_page=preview.target_page,
                content=preview.content,
                metadata=preview.metadata_json,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/pdf/control/preview", response_model=PdfControlPreviewPayload)
def pdf_control_preview(request: PdfControlPreviewRequest) -> PdfControlPreviewPayload:
    with session_scope() as db:
        draft_preview = db.get(DraftPreview, request.draft_preview_id)
        if draft_preview is None:
            raise HTTPException(status_code=404, detail="PDF draft preview not found")
        try:
            prepared = prepare_pdf_control_preview(
                wiki=wiki,
                draft_preview=draft_preview,
            )
            preview = save_draft_preview(
                db,
                session_id=draft_preview.session_id,
                turn_id=draft_preview.turn_id,
                title=prepared["title"],
                target_page=prepared["target_page"],
                content=prepared["content"],
                metadata_json=prepared["metadata_json"],
            )
            return PdfControlPreviewPayload(
                preview_id=preview.id,
                target_page=preview.target_page,
                overview_page=prepared["overview_page"],
                content=preview.content,
                overview_update=prepared["overview_update"],
                blocked_items=prepared["blocked_items"],
                metadata=preview.metadata_json,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/pdf/control/commit", response_model=PdfControlCommitResponse)
def pdf_control_commit(request: PdfControlCommitRequest) -> PdfControlCommitResponse:
    with session_scope() as db:
        preview = db.get(DraftPreview, request.preview_id)
        if preview is None:
            raise HTTPException(status_code=404, detail="PDF Control preview not found")
        try:
            result = commit_pdf_control_preview(
                wiki=wiki,
                preview=preview,
            )
            log_audit(
                db,
                session_id=preview.session_id,
                turn_id=preview.turn_id,
                action_type="pdf_control_commit",
                payload=result,
            )
            return PdfControlCommitResponse(**result)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            log_audit(
                db,
                session_id=preview.session_id,
                turn_id=preview.turn_id,
                action_type="pdf_control_commit_error",
                payload={"preview_id": preview.id, "detail": str(error)},
            )
            raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/write/preview", response_model=WritePreviewPayload)
def write_preview(request: WritePreviewRequest) -> WritePreviewPayload:
    with session_scope() as db:
        request_llm = _llm_for_generation_request(
            db,
            session_id=request.session_id,
            requested_provider=request.generation_provider,
            requested_model=request.generation_model,
        )
        preview = create_write_preview(
            db,
            settings,
            request_llm,
            wiki,
            session_id=request.session_id,
            turn_id=request.turn_id,
            question=request.question,
            answer=request.answer or "",
            source_titles=request.source_titles,
            current_page=request.context_pages[0] if request.context_pages else None,
            conversation_history=[],
        )
        metadata = preview.metadata_json or {}
        return WritePreviewPayload(
            preview_id=preview.id,
            action_type=metadata.get("action_type", ""),
            operation=metadata.get("operation", ""),
            target_page=preview.target_page,
            target_section=metadata.get("target_section"),
            preview_text=preview.content,
            structured_payload=metadata.get("structured_payload") or {},
            missing_fields=metadata.get("missing_fields", []),
            metadata=metadata,
        )


@app.post("/write/commit")
def write_commit(request: WriteCommitRequest) -> dict:
    with session_scope() as db:
        preview = db.get(DraftPreview, request.preview_id)
        if preview is None:
            raise HTTPException(status_code=404, detail="Write preview not found")
        try:
            return commit_write_preview(db, wiki, preview=preview)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            log_audit(
                db,
                session_id=preview.session_id,
                turn_id=preview.turn_id,
                action_type="write_commit_error",
                payload={"preview_id": preview.id, "detail": str(error)},
            )
            raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/reindex/wiki", response_model=ReindexResponse)
def reindex_wiki_endpoint() -> ReindexResponse:
    with session_scope() as db:
        job = create_job(db, "reindex_wiki")
        return ReindexResponse(job_id=job.id, status=job.status)


@app.post("/reindex/zotero", response_model=ReindexResponse)
def reindex_zotero_endpoint() -> ReindexResponse:
    if not settings.enable_zotero:
        return ReindexResponse(job_id="disabled", status="disabled")
    with session_scope() as db:
        job = create_job(db, "reindex_zotero")
        return ReindexResponse(job_id=job.id, status=job.status)


@app.get("/admin/jobs/{job_id}", response_model=JobStatusResponse)
def admin_job_status(job_id: str) -> JobStatusResponse:
    with session_scope() as db:
        job = db.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse(
            job_id=job.id,
            job_type=job.job_type,
            status=job.status,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


@app.get("/admin/stats", response_model=StatsResponse)
def admin_stats() -> StatsResponse:
    with session_scope() as db:
        sessions_total = db.scalar(select(func.count()).select_from(AssistantSession)) or 0
        turns_total = db.scalar(select(func.count()).select_from(AssistantTurn)) or 0
        chunks_total = db.scalar(select(func.count()).select_from(DocumentChunk)) or 0
        pending_jobs = db.scalar(select(func.count()).select_from(Job).where(Job.status.in_(["pending", "running"]))) or 0
        return StatsResponse(
            sessions_total=sessions_total,
            turns_total=turns_total,
            chunks_total=chunks_total,
            pending_jobs=pending_jobs,
        )


@app.get("/admin/index/stats", response_model=IndexStatsResponse)
def admin_index_stats() -> IndexStatsResponse:
    with session_scope() as db:
        documents_total = db.scalar(select(func.count()).select_from(Document)) or 0
        chunks_total = db.scalar(select(func.count()).select_from(DocumentChunk)) or 0
        embedded_chunks = (
            db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.embedding.is_not(None))) or 0
        )
        source_rows = db.execute(
            select(
                Document.source_type,
                func.count(Document.id.distinct()).label("documents"),
                func.count(DocumentChunk.id).label("chunks"),
                func.count(DocumentChunk.embedding).label("embedded_chunks"),
            )
            .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
            .group_by(Document.source_type)
            .order_by(Document.source_type.asc())
        ).all()
        return IndexStatsResponse(
            embedding_dimensions=settings.embedding_dimensions,
            documents_total=documents_total,
            chunks_total=chunks_total,
            embedded_chunks=embedded_chunks,
            source_stats=[
                SourceIndexStats(
                    source_type=row.source_type,
                    documents=int(row.documents or 0),
                    chunks=int(row.chunks or 0),
                    embedded_chunks=int(row.embedded_chunks or 0),
                )
                for row in source_rows
            ],
        )


@app.get("/session/{session_id}", response_model=SessionDetailResponse)
def session_detail(session_id: str) -> SessionDetailResponse:
    with session_scope() as db:
        session_record = db.get(AssistantSession, session_id)
        if session_record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        turns = db.execute(
            select(AssistantTurn).where(AssistantTurn.session_id == session_id).order_by(AssistantTurn.created_at.asc())
        ).scalars().all()
        default_selection = resolve_generation_selection(
            settings,
            requested_provider=None,
            requested_model=None,
            session_provider=None,
            session_model=None,
        )
        return SessionDetailResponse(
            session_id=session_record.id,
            user_name=session_record.user_name,
            current_page=session_record.current_page,
            last_stage=session_record.last_stage,
            confidence=session_record.confidence,
            model_info={
                "provider": session_record.generation_provider or default_selection.provider,
                "requested_model": session_record.generation_model or default_selection.requested_model,
                "resolved_model": session_record.generation_model or default_selection.resolved_model,
                "fallback_applied": False,
                "fallback_reason": None,
            },
            turns=[
                SessionTurnPayload(
                    turn_id=turn.id,
                    question=turn.question,
                    task_type=turn.task_type,
                    mode=turn.mode,
                    answer=turn.answer,
                    confidence=turn.confidence,
                    created_at=turn.created_at,
                    step_stream=[StepItem(**step) for step in (turn.step_stream or [])],
                    sources=[SourceItem(**item) for item in (turn.sources or [])],
                    unresolved_gaps=list(turn.unresolved_gaps or []),
                    suggested_followups=list(turn.suggested_followups or []),
                    action_trace=[ActionTraceItem(**item) for item in (turn.action_trace or [])],
                    operation_preview=derive_operation_preview(
                        draft_preview=DraftPreviewPayload(**turn.draft_preview) if turn.draft_preview else None,
                        write_preview=WritePreviewPayload(**turn.write_preview) if turn.write_preview else None,
                        result_fill=ResultFillPayload(**turn.result_fill) if turn.result_fill else None,
                    ),
                    operation_result=derive_operation_result(
                        write_result=WriteResultPayload(**turn.write_result) if turn.write_result else None,
                    ),
                    draft_preview=DraftPreviewPayload(**turn.draft_preview) if turn.draft_preview else None,
                    write_preview=WritePreviewPayload(**turn.write_preview) if turn.write_preview else None,
                    write_result=WriteResultPayload(**turn.write_result) if turn.write_result else None,
                    result_fill=ResultFillPayload(**turn.result_fill) if turn.result_fill else None,
                    pdf_ingest_review=PdfIngestReviewPayload(**turn.pdf_ingest_review) if turn.pdf_ingest_review else None,
                    model_info=turn.model_info,
                )
                for turn in turns
            ],
        )


@app.get("/sessions", response_model=SessionHistoryListResponse)
def sessions_list(user_name: str | None = Query(default=None)) -> SessionHistoryListResponse:
    with session_scope() as db:
        statement = select(AssistantSession).order_by(AssistantSession.updated_at.desc(), AssistantSession.created_at.desc())
        if user_name:
            statement = statement.where(AssistantSession.user_name == user_name)
        session_rows = db.execute(statement).scalars().all()
        items: list[SessionHistoryListItem] = []
        for session_record in session_rows:
            turn_rows = db.execute(
                select(AssistantTurn)
                .where(AssistantTurn.session_id == session_record.id)
                .order_by(AssistantTurn.created_at.asc())
            ).scalars().all()
            latest_question = turn_rows[-1].question if turn_rows else None
            items.append(
                SessionHistoryListItem(
                    session_id=session_record.id,
                    current_page=session_record.current_page,
                    user_name=session_record.user_name,
                    created_at=session_record.created_at,
                    updated_at=session_record.updated_at,
                    turn_count=len(turn_rows),
                    latest_question=latest_question,
                )
            )
        return SessionHistoryListResponse(sessions=items)


@app.get("/session/{session_id}/export.md")
def session_markdown_export(session_id: str, user_name: str | None = Query(default=None)) -> Response:
    with session_scope() as db:
        session_record = db.get(AssistantSession, session_id)
        if session_record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        if user_name and session_record.user_name and session_record.user_name != user_name:
            raise HTTPException(status_code=404, detail="Session not found")
        turns = db.execute(
            select(AssistantTurn).where(AssistantTurn.session_id == session_id).order_by(AssistantTurn.created_at.asc())
        ).scalars().all()
        body = build_session_markdown(session_record, turns)
        filename = build_session_export_filename(session_record)
        return Response(
            content=body,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )


@app.patch("/session/{session_id}/model")
def session_model_update(session_id: str, request: SessionModelUpdateRequest) -> dict:
    with session_scope() as db:
        session_record = db.get(AssistantSession, session_id)
        if session_record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        selection = resolve_generation_selection(
            settings,
            requested_provider=request.generation_provider,
            requested_model=request.generation_model,
            session_provider=session_record.generation_provider,
            session_model=session_record.generation_model,
        )
        session_record.generation_provider = selection.provider
        session_record.generation_model = selection.requested_model
        session_record.generation_fallback_model = fallback_model_for(selection.requested_model)
        log_audit(
            db,
            session_id=session_record.id,
            action_type="session_model_update",
            payload={
                "provider": session_record.generation_provider,
                "generation_model": session_record.generation_model,
                "fallback_model": session_record.generation_fallback_model,
            },
        )
        return {
            "status": "ok",
            "model_info": {
                "provider": session_record.generation_provider,
                "requested_model": session_record.generation_model,
                "resolved_model": session_record.generation_model,
                "fallback_model": session_record.generation_fallback_model,
            },
        }
