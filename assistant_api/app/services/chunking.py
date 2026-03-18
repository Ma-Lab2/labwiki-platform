from __future__ import annotations

import re


HEADING_PATTERN = re.compile(r"(?m)^(=+)\s*(.+?)\s*\1\s*$")


def chunk_wiki_text(text: str) -> list[dict[str, str]]:
    if not text.strip():
        return []

    matches = list(HEADING_PATTERN.finditer(text))
    if not matches:
        normalized = " ".join(text.split())
        return [{
            "heading": "全文",
            "content": text.strip(),
            "snippet": normalized[:280],
        }]

    chunks: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        normalized = " ".join(body.split())
        chunks.append({
            "heading": match.group(2).strip(),
            "content": body,
            "snippet": normalized[:280],
        })
    return chunks

