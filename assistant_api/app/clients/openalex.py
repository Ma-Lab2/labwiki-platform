from __future__ import annotations

from typing import Any

import httpx

from ..constants import SourceType


def _rebuild_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    max_position = max(max(positions) for positions in index.values() if positions)
    words = [""] * (max_position + 1)
    for token, positions in index.items():
        for position in positions:
            words[position] = token
    return " ".join(word for word in words if word)


class OpenAlexClient:
    def __init__(self) -> None:
        self.client = httpx.Client(timeout=20.0, follow_redirects=True)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        response = self.client.get(
            "https://api.openalex.org/works",
            params={"search": query, "per-page": limit},
        )
        response.raise_for_status()
        results: list[dict[str, Any]] = []
        for item in response.json().get("results", []):
            results.append({
                "source_type": SourceType.OPENALEX.value,
                "source_id": item.get("id", ""),
                "title": item.get("display_name", ""),
                "url": item.get("primary_location", {}).get("landing_page_url") or item.get("id"),
                "snippet": _rebuild_abstract(item.get("abstract_inverted_index"))[:360],
            })
        return results
