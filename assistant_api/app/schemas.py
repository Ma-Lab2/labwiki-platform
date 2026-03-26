from __future__ import annotations

from datetime import datetime
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


class ActionTraceItem(BaseModel):
    action: str
    status: str
    summary: str
    action_input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None


class AttachmentItem(BaseModel):
    id: str
    kind: str
    name: str
    mime_type: str
    size_bytes: int


class MissingItemPayload(BaseModel):
    label: str
    reason: str | None = None
    evidence: list[str] = Field(default_factory=list)


class PdfIngestTargetPayload(BaseModel):
    target_type: str
    target_title: str
    score: float | None = None
    reason: str | None = None


class PdfIngestSectionPayload(BaseModel):
    title: str
    content: str


class PdfIngestReviewPayload(BaseModel):
    title: str
    source_attachment_id: str
    file_name: str
    document_summary: str
    recommended_targets: list[PdfIngestTargetPayload] = Field(default_factory=list)
    proposed_draft_title: str
    section_outline: list[PdfIngestSectionPayload] = Field(default_factory=list)
    extracted_page_count: int = 0
    staged_image_count: int = 0
    evidence: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True


class PdfControlBlockedItemPayload(BaseModel):
    label: str
    reason: str
    content: str


class PdfControlPreviewPayload(BaseModel):
    preview_id: str
    target_page: str
    overview_page: str
    content: str
    overview_update: str
    blocked_items: list[PdfControlBlockedItemPayload] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class ResultFillPayload(BaseModel):
    title: str
    field_suggestions: dict[str, Any] = Field(default_factory=dict)
    draft_text: str
    missing_items: list[str | MissingItemPayload] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class DraftPreviewPayload(BaseModel):
    preview_id: str
    title: str
    target_page: str
    content: str
    metadata: dict[str, Any] | None = None


class WritePreviewPayload(BaseModel):
    preview_id: str
    action_type: str
    operation: str
    target_page: str
    preview_text: str
    structured_payload: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class WriteResultPayload(BaseModel):
    status: str
    page_title: str
    operation: str | None = None
    action_type: str | None = None
    detail: str | None = None


class ModelInfoPayload(BaseModel):
    requested_model: str
    resolved_model: str
    provider: str
    fallback_applied: bool = False
    fallback_reason: str | None = None


class ModelCatalogItem(BaseModel):
    id: str
    label: str
    provider: str
    family: str
    featured: bool = False
    recommended: bool = False


class ModelCatalogGroup(BaseModel):
    id: str
    label: str
    items: list[ModelCatalogItem] = Field(default_factory=list)


class ModelCatalogResponse(BaseModel):
    groups: list[ModelCatalogGroup]
    default_model: str
    default_provider: str
    include_all: bool = False


class CapabilityProviderItem(BaseModel):
    id: str
    label: str
    available: bool
    transport: str
    description: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityItem(BaseModel):
    id: str
    label: str
    provider: str
    mode: str
    description: str
    requires_confirmation: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityCatalogResponse(BaseModel):
    providers: list[CapabilityProviderItem] = Field(default_factory=list)
    capabilities: list[CapabilityItem] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(min_length=3)
    mode: AssistantMode = Field(default=AssistantMode.QA)
    detail_level: AssistantDetailLevel = Field(default=AssistantDetailLevel.INTRO)
    session_id: str | None = None
    workflow_hint: str | None = None
    context_pages: list[str] = Field(default_factory=list)
    attachments: list[AttachmentItem] = Field(default_factory=list)
    user_name: str | None = None
    generation_provider: str | None = None
    generation_model: str | None = None


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
    action_trace: list[ActionTraceItem] = Field(default_factory=list)
    draft_preview: DraftPreviewPayload | None = None
    write_preview: WritePreviewPayload | None = None
    write_result: WriteResultPayload | None = None
    result_fill: ResultFillPayload | None = None
    pdf_ingest_review: PdfIngestReviewPayload | None = None
    model_info: ModelInfoPayload | None = None


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
    generation_provider: str | None = None
    generation_model: str | None = None


class DraftCommitRequest(BaseModel):
    preview_id: str


class PdfDraftPreviewRequest(BaseModel):
    attachment_id: str = Field(min_length=1)
    session_id: str | None = None
    turn_id: str | None = None
    review: PdfIngestReviewPayload


class PdfControlPreviewRequest(BaseModel):
    draft_preview_id: str = Field(min_length=1)


class PdfControlCommitRequest(BaseModel):
    preview_id: str = Field(min_length=1)


class PdfControlCommitResponse(BaseModel):
    status: str
    page_title: str
    overview_page: str
    blocked_count: int = 0


class WritePreviewRequest(BaseModel):
    question: str = Field(min_length=3)
    answer: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    context_pages: list[str] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)
    user_name: str | None = None
    generation_provider: str | None = None
    generation_model: str | None = None


class WriteCommitRequest(BaseModel):
    preview_id: str


class ActionPreviewRequest(BaseModel):
    action_id: str = Field(min_length=1)
    question: str | None = None
    answer: str | None = None
    session_id: str | None = None
    turn_id: str | None = None
    context_pages: list[str] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    generation_provider: str | None = None
    generation_model: str | None = None


class ActionPreviewResponse(BaseModel):
    status: str
    provider: str
    action_id: str
    preview_kind: str
    requires_confirmation: bool = False
    preview: dict[str, Any] | None = None
    result: dict[str, Any] | None = None


class ActionCommitRequest(BaseModel):
    action_id: str = Field(min_length=1)
    preview_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionCommitResponse(BaseModel):
    status: str
    result_kind: str
    action_id: str
    result: dict[str, Any]


class SessionModelUpdateRequest(BaseModel):
    generation_provider: str | None = None
    generation_model: str = Field(min_length=1)


class ReindexResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SourceIndexStats(BaseModel):
    source_type: str
    documents: int
    chunks: int
    embedded_chunks: int


class IndexStatsResponse(BaseModel):
    embedding_dimensions: int
    documents_total: int
    chunks_total: int
    embedded_chunks: int
    source_stats: list[SourceIndexStats]


class SessionTurnPayload(BaseModel):
    turn_id: str
    question: str
    task_type: str
    mode: str
    answer: str | None = None
    confidence: float | None = None
    created_at: datetime | None = None
    step_stream: list[StepItem] = Field(default_factory=list)
    sources: list[SourceItem] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)
    suggested_followups: list[str] = Field(default_factory=list)
    action_trace: list[ActionTraceItem] = Field(default_factory=list)
    draft_preview: DraftPreviewPayload | None = None
    write_preview: WritePreviewPayload | None = None
    write_result: WriteResultPayload | None = None
    result_fill: ResultFillPayload | None = None
    pdf_ingest_review: PdfIngestReviewPayload | None = None
    model_info: ModelInfoPayload | None = None


class SessionDetailResponse(BaseModel):
    session_id: str
    user_name: str | None = None
    current_page: str | None = None
    last_stage: str | None = None
    confidence: float | None = None
    model_info: ModelInfoPayload | None = None
    turns: list[SessionTurnPayload] = Field(default_factory=list)


class SessionHistoryListItem(BaseModel):
    session_id: str
    current_page: str | None = None
    user_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    turn_count: int = 0
    latest_question: str | None = None


class SessionHistoryListResponse(BaseModel):
    sessions: list[SessionHistoryListItem] = Field(default_factory=list)


class StatsResponse(BaseModel):
    sessions_total: int
    turns_total: int
    chunks_total: int
    pending_jobs: int
