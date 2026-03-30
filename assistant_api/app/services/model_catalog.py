from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Any

import httpx

from ..config import Settings


FEATURED_MODELS: dict[str, list[str]] = {
    "gpt": [
        "gpt-5.4",
        "gpt-5.3-codex",
        "gpt-5.4-mini",
    ],
    "claude": [
        "claude-sonnet-4-5-20250929-thinking",
        "claude-sonnet-4-5-20250929",
        "claude-sonnet-4-6-thinking",
        "claude-sonnet-4-6",
        "claude-opus-4-1-thinking",
        "claude-opus-4-1",
    ],
    "gemini": [
        "gemini-3-flash-preview-thinking",
        "gemini-3-flash-preview",
        "gemini-3-pro-thinking",
        "gemini-3-pro",
        "gemini-3.1-pro-preview-thinking",
    ],
}

FALLBACK_CHAINS: dict[str, list[str]] = {
    "gpt-5.4": ["gpt-5.3-codex", "gpt-5.4-mini"],
    "gpt-5.3-codex": ["gpt-5.4-mini"],
    "gpt-5.4-mini": [],
    "claude-sonnet-4-6-thinking": [
        "claude-sonnet-4-6",
        "claude-sonnet-4-5-20250929-thinking",
        "claude-sonnet-4-5-20250929",
    ],
    "claude-sonnet-4-6": [
        "claude-sonnet-4-5-20250929-thinking",
        "claude-sonnet-4-5-20250929",
    ],
    "claude-sonnet-4-5-20250929-thinking": ["claude-sonnet-4-5-20250929"],
    "claude-sonnet-4-5-20250929": [],
    "claude-opus-4-1-thinking": ["claude-opus-4-1"],
    "claude-opus-4-1": [],
    "gemini-3-flash-preview-thinking": ["gemini-3-flash-preview"],
    "gemini-3-flash-preview": [],
    "gemini-3-pro-thinking": ["gemini-3-pro"],
    "gemini-3-pro": [],
    "gemini-3.1-pro-preview-thinking": ["gemini-3-pro-thinking", "gemini-3-pro"],
}

WORKFLOW_MODEL_PRIORITIES: dict[str, list[str]] = {
    "pdf_ingest_write": [
        "gpt-5.4",
        "gpt-5.3-codex",
        "claude-sonnet-4-5-20250929-thinking",
        "claude-sonnet-4-5-20250929",
        "gemini-3-flash-preview-thinking",
        "gemini-3-flash-preview",
    ],
}

_CATALOG_CACHE: dict[str, Any] = {"expires_at": 0.0, "model_ids": []}


@dataclass(frozen=True)
class ResolvedGenerationSelection:
    provider: str
    requested_model: str
    resolved_model: str
    fallback_chain: list[str]


def infer_provider_for_model(model: str, default_provider: str = "anthropic") -> str:
    lowered = model.strip().lower()
    if lowered.startswith("claude-"):
        return "anthropic"
    if lowered.startswith("gpt-") or lowered.startswith("gemini-"):
        return "openai_compatible"
    return default_provider


def infer_family_for_model(model: str) -> str:
    lowered = model.strip().lower()
    if lowered.startswith("claude-"):
        return "claude"
    if lowered.startswith("gpt-"):
        return "gpt"
    if lowered.startswith("gemini-"):
        return "gemini"
    return "other"


def default_generation_selection(settings: Settings) -> ResolvedGenerationSelection:
    if settings.generation_provider == "anthropic":
        model = settings.anthropic_model
        provider = "anthropic"
    elif settings.generation_provider in {"openai_compatible", "domestic"}:
        model = settings.openai_compatible_model or settings.openai_model
        provider = infer_provider_for_model(model, settings.generation_provider)
    else:
        model = settings.openai_model
        provider = infer_provider_for_model(model, settings.generation_provider)
    return ResolvedGenerationSelection(
        provider=provider,
        requested_model=model,
        resolved_model=model,
        fallback_chain=FALLBACK_CHAINS.get(model, []),
    )


def resolve_generation_selection(
    settings: Settings,
    *,
    requested_provider: str | None,
    requested_model: str | None,
    session_provider: str | None,
    session_model: str | None,
) -> ResolvedGenerationSelection:
    if requested_model:
        model = requested_model.strip()
        provider = infer_provider_for_model(model, requested_provider or session_provider or settings.generation_provider)
    elif session_model:
        model = session_model.strip()
        provider = session_provider or infer_provider_for_model(model, settings.generation_provider)
    else:
        default = default_generation_selection(settings)
        model = default.requested_model
        provider = default.provider
    return ResolvedGenerationSelection(
        provider=provider,
        requested_model=model,
        resolved_model=model,
        fallback_chain=FALLBACK_CHAINS.get(model, []),
    )


def resolve_workflow_generation_selection(
    settings: Settings,
    *,
    requested_provider: str | None,
    requested_model: str | None,
    session_provider: str | None,
    session_model: str | None,
    workflow_hint: str | None,
) -> ResolvedGenerationSelection:
    selection = resolve_generation_selection(
        settings,
        requested_provider=requested_provider,
        requested_model=requested_model,
        session_provider=session_provider,
        session_model=session_model,
    )
    workflow = (workflow_hint or "").strip()
    priorities = WORKFLOW_MODEL_PRIORITIES.get(workflow, [])
    if not priorities:
        return selection
    current_model = (selection.requested_model or "").strip().lower()
    if current_model and not current_model.endswith("-mini"):
        return selection

    available_ids = set(fetch_remote_model_ids(settings))
    for model in priorities:
        if available_ids and model not in available_ids:
            continue
        if model == selection.requested_model:
            return selection
        provider = infer_provider_for_model(model, selection.provider)
        return ResolvedGenerationSelection(
            provider=provider,
            requested_model=model,
            resolved_model=model,
            fallback_chain=FALLBACK_CHAINS.get(model, []),
        )
    return selection


def fetch_remote_model_ids(settings: Settings, *, force_refresh: bool = False) -> list[str]:
    now = time()
    if not force_refresh and _CATALOG_CACHE["expires_at"] > now and _CATALOG_CACHE["model_ids"]:
        return list(_CATALOG_CACHE["model_ids"])
    api_key = settings.model_catalog_api_key
    if not api_key:
        return []
    url = settings.model_catalog_base_url.rstrip("/") + "/models"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=45,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return []
    model_ids = sorted({item.get("id", "") for item in response.json().get("data", []) if item.get("id")})
    _CATALOG_CACHE["model_ids"] = model_ids
    _CATALOG_CACHE["expires_at"] = now + 300
    return list(model_ids)


def build_model_catalog(settings: Settings, *, include_all: bool = False) -> dict[str, Any]:
    available_ids = fetch_remote_model_ids(settings)
    available = set(available_ids)
    use_static_featured = not available_ids
    groups: list[dict[str, Any]] = []
    for family, featured in FEATURED_MODELS.items():
        if use_static_featured:
            featured_models = list(featured)
            chosen_models = featured_models
        else:
            family_models = sorted(model for model in available if infer_family_for_model(model) == family)
            featured_models = [model for model in featured if model in available]
            chosen_models = family_models if include_all else featured_models
        items = [{
            "id": model,
            "label": model,
            "provider": infer_provider_for_model(model),
            "family": family,
            "featured": model in featured_models,
            "recommended": model == (featured_models[0] if featured_models else None),
        } for model in chosen_models]
        groups.append({
            "id": family,
            "label": family.upper() if family == "gpt" else family.capitalize(),
            "items": items,
        })
    default = default_generation_selection(settings)
    return {
        "groups": groups,
        "default_model": default.requested_model,
        "default_provider": default.provider,
        "include_all": include_all,
    }


def fallback_model_for(model: str) -> str | None:
    chain = FALLBACK_CHAINS.get(model, [])
    return chain[0] if chain else None


def should_fallback_generation_error(error: Exception) -> bool:
    message = str(error).lower()
    tokens = [
        "credit balance is too low",
        "insufficient balance",
        "insufficient_quota",
        "model not found",
        "does not exist",
        "access denied",
        "disabled",
        "not available for your account",
    ]
    return any(token in message for token in tokens)
