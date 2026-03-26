from __future__ import annotations

from collections.abc import Iterator

from anthropic import Anthropic
from openai import OpenAI

from .base import PromptEnvelope


class NullGenerationProvider:
    enabled = False

    def generate(self, prompt: PromptEnvelope) -> str:
        return ""

    def stream(self, prompt: PromptEnvelope) -> Iterator[str]:
        if False:
            yield ""


class AnthropicGenerationProvider:
    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: int, max_tokens: int) -> None:
        self.enabled = bool(api_key)
        self.model = model
        self.default_max_tokens = max_tokens
        self.timeout = timeout
        self.client = Anthropic(api_key=api_key, base_url=base_url.rstrip("/"), timeout=timeout)

    def generate(self, prompt: PromptEnvelope) -> str:
        content = self._build_user_content(prompt)
        message = self.client.messages.create(
            model=self.model,
            max_tokens=prompt.max_tokens or self.default_max_tokens,
            system=prompt.system_prompt,
            messages=[{"role": "user", "content": content}],
            temperature=prompt.temperature,
            timeout=self.timeout,
        )
        return "".join(
            block.text for block in message.content
            if getattr(block, "type", None) == "text"
        ).strip()

    def stream(self, prompt: PromptEnvelope) -> Iterator[str]:
        content = self._build_user_content(prompt)
        with self.client.messages.stream(
            model=self.model,
            max_tokens=prompt.max_tokens or self.default_max_tokens,
            system=prompt.system_prompt,
            messages=[{"role": "user", "content": content}],
            temperature=prompt.temperature,
            timeout=self.timeout,
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield text

    @staticmethod
    def _build_user_content(prompt: PromptEnvelope):
        if not prompt.user_content:
            return prompt.user_prompt
        blocks = []
        for item in prompt.user_content:
            if item.get("type") == "image":
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": item["mime_type"],
                        "data": item["data"],
                    },
                })
            else:
                blocks.append({
                    "type": "text",
                    "text": item.get("text", ""),
                })
        return blocks


class _OpenAIChatGenerationProvider:
    def __init__(self, *, api_key: str, base_url: str | None, model: str, timeout: int, max_tokens: int) -> None:
        self.enabled = bool(api_key)
        self.model = model
        self.default_max_tokens = max_tokens
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def generate(self, prompt: PromptEnvelope) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": self._build_user_content(prompt)},
            ],
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens or self.default_max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    def stream(self, prompt: PromptEnvelope) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt.system_prompt},
                {"role": "user", "content": self._build_user_content(prompt)},
            ],
            temperature=prompt.temperature,
            max_tokens=prompt.max_tokens or self.default_max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta

    @staticmethod
    def _build_user_content(prompt: PromptEnvelope):
        if not prompt.user_content:
            return prompt.user_prompt
        blocks = []
        for item in prompt.user_content:
            if item.get("type") == "image":
                blocks.append({
                    "type": "image_url",
                    "image_url": {
                        "url": "data:" + item["mime_type"] + ";base64," + item["data"],
                    },
                })
            else:
                blocks.append({
                    "type": "text",
                    "text": item.get("text", ""),
                })
        return blocks


class OpenAIGenerationProvider(_OpenAIChatGenerationProvider):
    pass


class OpenAICompatibleGenerationProvider(_OpenAIChatGenerationProvider):
    pass
