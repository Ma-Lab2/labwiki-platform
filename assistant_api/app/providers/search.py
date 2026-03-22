from __future__ import annotations

from typing import Any

import httpx
from openai import OpenAI

from ..constants import SourceType


class NullWebSearchProvider:
    enabled = False

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        return []


class OpenAIWebSearchProvider:
    def __init__(self, *, api_key: str, base_url: str | None, model: str) -> None:
        self.enabled = bool(api_key and model)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        response = self.client.responses.create(
            model=self.model,
            tools=[{"type": "web_search_preview"}],
            input=f"用中文返回与下列问题最相关的网页线索，优先可信来源，并总结关键信息：{query}",
        )

        annotations: list[dict[str, Any]] = []
        output_text = getattr(response, "output_text", "") or ""
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                for annotation in getattr(content, "annotations", []) or []:
                    annotations.append({
                        "url": getattr(annotation, "url", None),
                        "title": getattr(annotation, "title", None),
                    })

        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for index, annotation in enumerate(annotations):
            url = annotation.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            results.append({
                "source_type": SourceType.WEB.value,
                "source_id": url,
                "title": annotation.get("title") or f"Web result {index + 1}",
                "url": url,
                "snippet": output_text[:360],
            })
            if len(results) >= limit:
                break
        if results:
            return results
        if not output_text:
            return []
        return [{
            "source_type": SourceType.WEB.value,
            "source_id": "openai-web-search",
            "title": "网页搜索摘要",
            "url": None,
            "snippet": output_text[:360],
        }]


class TavilyWebSearchProvider:
    def __init__(self, *, api_key: str) -> None:
        self.enabled = bool(api_key)
        self.api_key = api_key
        self.client = httpx.Client(timeout=30.0)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        response = self.client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": limit,
            },
        )
        response.raise_for_status()
        results: list[dict[str, Any]] = []
        for item in response.json().get("results", []):
            results.append({
                "source_type": SourceType.WEB.value,
                "source_id": item.get("url") or item.get("title", ""),
                "title": item.get("title", ""),
                "url": item.get("url"),
                "snippet": item.get("content", "")[:360],
            })
        return results
