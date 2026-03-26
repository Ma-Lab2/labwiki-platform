from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Protocol


@dataclass(frozen=True)
class PromptEnvelope:
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: int | None = None
    user_content: list[dict[str, Any]] | None = None


class BaseGenerationProvider(Protocol):
    enabled: bool

    def generate(self, prompt: PromptEnvelope) -> str:
        ...

    def stream(self, prompt: PromptEnvelope) -> Iterator[str]:
        ...


class BaseEmbeddingProvider(Protocol):
    enabled: bool

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        ...


class BaseWebSearchProvider(Protocol):
    enabled: bool

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        ...
