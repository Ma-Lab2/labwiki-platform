from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from ..config import Settings
from ..providers import (
    AnthropicGenerationProvider,
    NullEmbeddingProvider,
    NullGenerationProvider,
    NullWebSearchProvider,
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleGenerationProvider,
    OpenAIGenerationProvider,
    OpenAIWebSearchProvider,
    TavilyWebSearchProvider,
)
from .model_catalog import should_fallback_generation_error
from ..services.prompts import build_answer_prompt, build_draft_prompt
from .model_catalog import default_generation_selection


@dataclass(frozen=True)
class GenerationRuntimeConfig:
    provider: str
    requested_model: str
    resolved_model: str
    fallback_chain: list[str]


class LLMClient:
    generation_retry_limit = 2

    def __init__(
        self,
        settings: Settings,
        *,
        generation_config: GenerationRuntimeConfig | None = None,
        embedding_provider: Any | None = None,
        web_search_provider: Any | None = None,
    ) -> None:
        self.settings = settings
        default_selection = default_generation_selection(settings)
        default_model = default_selection.requested_model
        self.generation_config = generation_config or GenerationRuntimeConfig(
            provider=default_selection.provider,
            requested_model=default_model,
            resolved_model=default_model,
            fallback_chain=default_selection.fallback_chain,
        )
        self.embedding_provider = embedding_provider or self._build_embedding_provider()
        self.web_search_provider = web_search_provider or self._build_web_search_provider()
        self.generation_provider = self._build_generation_provider_for(
            provider=self.generation_config.provider,
            model=self.generation_config.resolved_model,
        )
        self.embedding_enabled = self.embedding_provider.enabled
        self.fallback_applied = self.generation_config.requested_model != self.generation_config.resolved_model
        self.fallback_reason: str | None = None

    def _default_requested_model(self) -> str:
        return default_generation_selection(self.settings).requested_model

    def _build_generation_provider_for(self, *, provider: str, model: str):
        if provider == "anthropic" and self.settings.anthropic_api_key:
            return AnthropicGenerationProvider(
                api_key=self.settings.anthropic_api_key,
                base_url=self.settings.anthropic_base_url,
                model=model,
                timeout=self.settings.anthropic_timeout,
                max_tokens=self.settings.anthropic_max_tokens,
            )
        if provider == "openai" and self.settings.openai_api_key:
            return OpenAIGenerationProvider(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                model=model,
                timeout=self.settings.openai_timeout,
                max_tokens=self.settings.openai_max_tokens,
            )
        if provider in {"openai_compatible", "domestic"} and self.settings.openai_compatible_generation_api_key:
            return OpenAICompatibleGenerationProvider(
                api_key=self.settings.openai_compatible_generation_api_key,
                base_url=self.settings.openai_compatible_generation_base_url,
                model=model,
                timeout=self.settings.openai_compatible_timeout,
                max_tokens=self.settings.openai_compatible_max_tokens,
            )
        return NullGenerationProvider()

    def _build_embedding_provider(self):
        if (
            self.settings.embedding_base_url
            and self.settings.embedding_api_key
            and self.settings.embedding_model
        ):
            return OpenAICompatibleEmbeddingProvider(
                base_url=self.settings.embedding_base_url,
                api_key=self.settings.embedding_api_key,
                model=self.settings.embedding_model,
                timeout=self.settings.embedding_timeout,
            )
        return NullEmbeddingProvider()

    def _build_web_search_provider(self):
        if not self.settings.enable_web_search:
            return NullWebSearchProvider()
        provider = self.settings.web_search_provider
        if provider == "openai" and self.settings.openai_api_key and self.settings.openai_web_search_model:
            return OpenAIWebSearchProvider(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
                model=self.settings.openai_web_search_model,
            )
        if provider == "tavily" and self.settings.tavily_api_key:
            return TavilyWebSearchProvider(api_key=self.settings.tavily_api_key)
        return NullWebSearchProvider()

    def with_generation_config(self, generation_config: GenerationRuntimeConfig) -> "LLMClient":
        return LLMClient(
            self.settings,
            generation_config=generation_config,
            embedding_provider=self.embedding_provider,
            web_search_provider=self.web_search_provider,
        )

    def answer_from_evidence(
        self,
        *,
        question: str,
        task_type: str,
        detail_level: str,
        mode: str,
        current_page: str | None = None,
        evidence: list[dict[str, Any]],
        unresolved_gaps: list[str],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        if self.generation_provider.enabled:
            try:
                return "".join(
                    self.answer_stream(
                        question=question,
                        task_type=task_type,
                        detail_level=detail_level,
                        mode=mode,
                        current_page=current_page,
                        evidence=evidence,
                        unresolved_gaps=unresolved_gaps,
                        conversation_history=conversation_history,
                    )
                ).strip()
            except Exception:
                return self._fallback_answer(question, detail_level, evidence, unresolved_gaps, conversation_history or [])
        return self._fallback_answer(question, detail_level, evidence, unresolved_gaps, conversation_history or [])

    def answer_stream(
        self,
        *,
        question: str,
        task_type: str,
        detail_level: str,
        mode: str,
        current_page: str | None = None,
        evidence: list[dict[str, Any]],
        unresolved_gaps: list[str],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        structured_only = any(
            hint in question for hint in [
                "结构化定义",
                "结构化条目",
                "只给出本组结构化定义",
                "只保留本组结构化定义",
                "只保留结构化定义",
                "只给定义",
            ]
        )
        if self.generation_provider.enabled:
            prompt = build_answer_prompt(
                question=question,
                task_type=task_type,
                detail_level=detail_level,
                mode=mode,
                current_page=current_page,
                evidence=evidence,
                unresolved_gaps=unresolved_gaps,
                structured_only=structured_only,
                conversation_history=conversation_history or [],
            )
            try:
                yield from self.stream_prompt(prompt)
                return
            except Exception:
                yield self._fallback_answer(question, detail_level, evidence, unresolved_gaps, conversation_history or [])
                return
        yield self._fallback_answer(question, detail_level, evidence, unresolved_gaps, conversation_history or [])

    def draft_from_answer(
        self,
        *,
        question: str,
        answer: str,
        source_titles: list[str],
        draft_prefix: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict[str, str]:
        if self.generation_provider.enabled:
            prompt = build_draft_prompt(
                question=question,
                answer=answer,
                source_titles=source_titles,
                draft_prefix=draft_prefix,
                conversation_history=conversation_history or [],
            )
            raw = self.generate_prompt(prompt)
            try:
                payload = self._load_json_object(raw)
                return {
                    "title": payload.get("title") or self._fallback_draft_title(question),
                    "content": payload.get("content") or answer,
                }
            except json.JSONDecodeError:
                return {
                    "title": self._fallback_draft_title(question),
                    "content": answer,
                }

        title = self._fallback_draft_title(question)
        content = (
            f"== 触发问题 ==\n{question}\n\n"
            f"== 助手整理结果 ==\n{answer}\n\n"
            f"== 来源 ==\n* " + "\n* ".join(source_titles or ["待补充"])
        )
        return {"title": title, "content": content}

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        return self.embedding_provider.embed(texts)

    def search_web(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self.web_search_provider.enabled:
            return []
        return self.web_search_provider.search(query, limit=limit)

    def generate_prompt(self, prompt: Any) -> str:
        return self._call_with_generation_fallback(lambda provider: provider.generate(prompt))

    def stream_prompt(self, prompt: Any) -> Iterator[str]:
        attempts = 0
        while True:
            emitted = False
            try:
                for chunk in self.generation_provider.stream(prompt):
                    emitted = True
                    yield chunk
                return
            except Exception as error:
                if emitted:
                    raise
                if self._try_generation_fallback(error):
                    continue
                if self._is_retryable_generation_error(error) and attempts < self.generation_retry_limit:
                    attempts += 1
                    continue
                raise

    def _call_with_generation_fallback(self, callback):
        attempts = 0
        while True:
            try:
                return callback(self.generation_provider)
            except Exception as error:
                if self._try_generation_fallback(error):
                    continue
                if self._is_retryable_generation_error(error) and attempts < self.generation_retry_limit:
                    attempts += 1
                    continue
                raise

    def _try_generation_fallback(self, error: Exception) -> bool:
        if not should_fallback_generation_error(error):
            return False
        if not self.generation_config.fallback_chain:
            return False
        next_model = self.generation_config.fallback_chain[0]
        self.generation_provider = self._build_generation_provider_for(
            provider=self.generation_config.provider,
            model=next_model,
        )
        self.generation_config = GenerationRuntimeConfig(
            provider=self.generation_config.provider,
            requested_model=self.generation_config.requested_model,
            resolved_model=next_model,
            fallback_chain=self.generation_config.fallback_chain[1:],
        )
        self.fallback_applied = True
        self.fallback_reason = str(error)
        return self.generation_provider.enabled

    @staticmethod
    def _is_retryable_generation_error(error: Exception) -> bool:
        message = str(error).lower()
        tokens = [
            "timed out",
            "timeout",
            "429",
            "rate limit",
            "too many requests",
            "bad gateway",
            "gateway timeout",
            "internal server error",
            "temporarily unavailable",
            "server disconnected",
            "connection error",
        ]
        return isinstance(error, TimeoutError) or any(token in message for token in tokens)

    @property
    def model_info(self) -> dict[str, Any]:
        return {
            "requested_model": self.generation_config.requested_model,
            "resolved_model": self.generation_config.resolved_model,
            "provider": self.generation_config.provider,
            "fallback_applied": self.fallback_applied,
            "fallback_reason": self.fallback_reason,
        }

    @staticmethod
    def _load_json_object(raw: str) -> dict[str, Any]:
        candidate = raw.strip()
        if candidate.startswith("```"):
            candidate = "\n".join(
                line for line in candidate.splitlines()
                if not line.strip().startswith("```")
            ).strip()
        return json.loads(candidate)

    @staticmethod
    def _fallback_answer(
        question: str,
        detail_level: str,
        evidence: list[dict[str, Any]],
        unresolved_gaps: list[str],
        conversation_history: list[dict[str, str]],
    ) -> str:
        if not evidence:
            return "当前没有命中足够的站内证据。请先补充关联页面、术语或文献，再让助手继续整理。"
        snippets = []
        for item in evidence[:4]:
            detail = item.get("snippet") or item.get("content", "")[:140]
            snippets.append(f"《{item['title']}》指出：{detail}")
        history_text = ""
        if conversation_history:
            history_text = f"\n\n最近上下文提示：上一轮主要在讨论“{conversation_history[-1].get('question', '')}”。"
        gap_text = ""
        if unresolved_gaps:
            gap_text = "\n\n仍待补证的部分：\n- " + "\n- ".join(unresolved_gaps)
        return (
            f"针对“{question}”，当前检索到的本组材料更支持以下判断。\n\n"
            + "\n".join(f"{index + 1}. {snippet}" for index, snippet in enumerate(snippets))
            + gap_text
            + history_text
            + f"\n\n解释层级：{detail_level}。如果需要，我可以继续把这些结果整理成草稿预览。"
        )

    @staticmethod
    def _fallback_draft_title(question: str) -> str:
        compact = question.replace("：", " ").replace(":", " ").strip()
        return compact[:42] or "知识助手草稿"
