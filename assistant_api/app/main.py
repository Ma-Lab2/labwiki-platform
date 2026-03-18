from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from .clients.openalex import OpenAlexClient
from .clients.tools import ToolClients
from .clients.wiki import MediaWikiClient
from .config import get_settings
from .constants import AssistantMode
from .db import init_database, session_scope
from .models import AssistantSession, AssistantTurn, DocumentChunk, DraftPreview, Job
from .schemas import (
    ChatRequest,
    ChatResponse,
    DraftCommitRequest,
    DraftPreviewPayload,
    DraftPreviewRequest,
    PlanResponse,
    ReindexResponse,
    StatsResponse,
    ToolExecuteRequest,
)
from .services.llm import LLMClient
from .services.drafts import create_draft_preview
from .services.orchestrator import build_plan, run_chat
from .services.reindex import create_job
from .services.audit import log_audit


settings = get_settings()
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
    with session_scope() as db:
        try:
            return run_chat(db, settings, llm, wiki, openalex, tools, request)
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error


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
    return build_plan(request.question, request.mode, request.context_pages)


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
        preview = create_draft_preview(
            db,
            settings,
            llm,
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


@app.post("/reindex/wiki", response_model=ReindexResponse)
def reindex_wiki_endpoint() -> ReindexResponse:
    with session_scope() as db:
        job = create_job(db, "reindex_wiki")
        return ReindexResponse(job_id=job.id, status=job.status)


@app.post("/reindex/zotero", response_model=ReindexResponse)
def reindex_zotero_endpoint() -> ReindexResponse:
    with session_scope() as db:
        job = create_job(db, "reindex_zotero")
        return ReindexResponse(job_id=job.id, status=job.status)


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


@app.get("/session/{session_id}")
def session_detail(session_id: str) -> dict:
    with session_scope() as db:
        session_record = db.get(AssistantSession, session_id)
        if session_record is None:
            raise HTTPException(status_code=404, detail="Session not found")
        turns = db.execute(
            select(AssistantTurn).where(AssistantTurn.session_id == session_id).order_by(AssistantTurn.created_at.asc())
        ).scalars().all()
        return {
            "session_id": session_record.id,
            "user_name": session_record.user_name,
            "current_page": session_record.current_page,
            "last_stage": session_record.last_stage,
            "confidence": session_record.confidence,
            "turns": [
                {
                    "turn_id": turn.id,
                    "question": turn.question,
                    "task_type": turn.task_type,
                    "mode": turn.mode,
                    "answer": turn.answer,
                    "confidence": turn.confidence,
                    "created_at": turn.created_at.isoformat() if turn.created_at else None,
                }
                for turn in turns
            ],
        }
