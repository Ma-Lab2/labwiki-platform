from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .constants import AssistantDetailLevel, AssistantMode, TaskType, ToolName


class StepItem(BaseModel):
    stage: str
    title: str
    status: str
    detail: str


class SourceItem(BaseModel):
    source_type: str
    source_id: str
    title: str
    url: str | None = None
    snippet: str | None = None


class DraftPreviewPayload(BaseModel):
    preview_id: str
    title: str
    target_page: str
    content: str
    metadata: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=3)
    mode: AssistantMode = Field(default=AssistantMode.QA)
    detail_level: AssistantDetailLevel = Field(default=AssistantDetailLevel.INTRO)
    session_id: str | None = None
    context_pages: list[str] = Field(default_factory=list)
    user_name: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    turn_id: str
    task_type: TaskType
    answer: str
    step_stream: list[StepItem]
    sources: list[SourceItem]
    confidence: float
    unresolved_gaps: list[str]
    suggested_followups: list[str]
    draft_preview: DraftPreviewPayload | None = None


class PlanResponse(BaseModel):
    task_type: TaskType
    planned_sources: list[str]
    needs_external_search: bool
    will_generate_draft_preview: bool


class ToolExecuteRequest(BaseModel):
    tool: ToolName
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class DraftPreviewRequest(BaseModel):
    question: str
    answer: str
    mode: AssistantMode = AssistantMode.DRAFT
    session_id: str | None = None
    turn_id: str | None = None
    source_titles: list[str] = Field(default_factory=list)


class DraftCommitRequest(BaseModel):
    preview_id: str


class ReindexResponse(BaseModel):
    job_id: str
    status: str


class StatsResponse(BaseModel):
    sessions_total: int
    turns_total: int
    chunks_total: int
    pending_jobs: int
