from __future__ import annotations

import time

import httpx


class NullEmbeddingProvider:
    enabled = False

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        return None


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: int) -> None:
        self.enabled = bool(base_url and api_key and model)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = httpx.Client(timeout=timeout)

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        if not texts:
            return None
        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                response = self.client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": texts},
                )
                response.raise_for_status()
                return [item["embedding"] for item in response.json().get("data", [])]
            except (httpx.HTTPError, httpx.TimeoutException) as error:
                last_error = error
                if isinstance(error, httpx.HTTPStatusError):
                    status_code = error.response.status_code
                    if status_code < 500 and status_code != 429:
                        raise
                if attempt == 5:
                    raise
                time.sleep(min(2 ** (attempt - 1), 8))
        if last_error is not None:
            raise last_error
        return None
