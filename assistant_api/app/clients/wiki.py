from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from ..config import Settings


@dataclass
class WikiSearchResult:
    title: str
    snippet: str
    pageid: int | None = None


class MediaWikiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.Client(
            timeout=30.0,
            verify=settings.wiki_verify_tls,
            follow_redirects=True,
            trust_env=False,
        )
        self.csrf_token: str | None = None
        self.logged_in = False

    def _reset_auth_state(self) -> None:
        self.client.cookies.clear()
        self.csrf_token = None
        self.logged_in = False

    @staticmethod
    def _error_code(payload: dict[str, Any]) -> str:
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return ""
        return str(error.get("code") or "").strip().lower()

    def _perform_csrf_action(self, operation) -> dict[str, Any]:
        self.login()
        if not self.csrf_token:
            raise RuntimeError("CSRF token not available")
        payload = operation()
        if self._error_code(payload) == "badtoken":
            self._reset_auth_state()
            self.login()
            if not self.csrf_token:
                raise RuntimeError("CSRF token not available")
            payload = operation()
        return payload

    def _request_headers(self) -> dict[str, str] | None:
        if not self.settings.wiki_api_host_header:
            return None
        return {"Host": self.settings.wiki_api_host_header}

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        response = self.client.get(
            self.settings.wiki_api_url,
            params={"format": "json", **params},
            headers=self._request_headers(),
        )
        response.raise_for_status()
        return response.json()

    def _post(self, data: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(
            self.settings.wiki_api_url,
            data={"format": "json", **data},
            headers=self._request_headers(),
        )
        response.raise_for_status()
        return response.json()

    def login(self) -> None:
        if self.logged_in:
            return

        if not self.settings.wiki_password:
            raise RuntimeError("ASSISTANT_WIKI_PASSWORD_FILE is not configured or readable")

        token_data = self._get({"action": "query", "meta": "tokens", "type": "login"})
        login_token = token_data["query"]["tokens"]["logintoken"]
        login_data = self._post({
            "action": "clientlogin",
            "username": self.settings.wiki_user,
            "password": self.settings.wiki_password,
            "logintoken": login_token,
            "loginreturnurl": self.settings.wiki_url,
        })
        if login_data.get("clientlogin", {}).get("status") not in {"PASS", "UI"}:
            raise RuntimeError(f"MediaWiki login failed: {login_data}")

        csrf_data = self._get({"action": "query", "meta": "tokens", "type": "csrf"})
        self.csrf_token = csrf_data["query"]["tokens"]["csrftoken"]
        self.logged_in = True

    def page_url(self, title: str) -> str:
        return f"{self.settings.wiki_url.rstrip('/')}{self.settings.wiki_index_path}?title={quote(title)}"

    def search_pages(self, query: str, limit: int = 8) -> list[WikiSearchResult]:
        self.login()
        data = self._get({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": limit,
            "srprop": "snippet",
        })
        results: list[WikiSearchResult] = []
        for item in data.get("query", {}).get("search", []):
            results.append(
                WikiSearchResult(
                    title=item["title"],
                    snippet=item.get("snippet", ""),
                    pageid=item.get("pageid"),
                )
            )
        return results

    def get_page_text(self, title: str) -> str:
        self.login()
        data = self._get({
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvslots": "main",
            "rvprop": "content",
        })
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            revisions = page.get("revisions", [])
            if not revisions:
                return ""
            main_slot = revisions[0].get("slots", {}).get("main", {})
            return (
                main_slot.get("content")
                or main_slot.get("*")
                or revisions[0].get("*", "")
            )
        return ""

    def iter_all_pages(self, namespaces: list[int]) -> list[str]:
        self.login()
        titles: list[str] = []
        for namespace in namespaces:
            apcontinue: str | None = None
            while True:
                params = {
                    "action": "query",
                    "list": "allpages",
                    "apnamespace": namespace,
                    "aplimit": "max",
                }
                if apcontinue:
                    params["apcontinue"] = apcontinue
                data = self._get(params)
                for item in data.get("query", {}).get("allpages", []):
                    titles.append(item["title"])
                apcontinue = data.get("continue", {}).get("apcontinue")
                if not apcontinue:
                    break
        return titles

    def cargo_query(self, tables: str, fields: str, where: str = "1=1", limit: int = 25) -> list[dict[str, Any]]:
        self.login()
        data = self._get({
            "action": "cargoquery",
            "tables": tables,
            "fields": fields,
            "where": where,
            "limit": limit,
        })
        return data.get("cargoquery", [])

    def edit_page(self, title: str, text: str, summary: str) -> dict[str, Any]:
        payload = self._perform_csrf_action(lambda: self._post({
            "action": "edit",
            "title": title,
            "text": text,
            "summary": summary,
            "token": self.csrf_token,
        }))
        if self._error_code(payload):
            raise RuntimeError(f"MediaWiki edit failed: {payload}")
        return payload

    def upload_file(
        self,
        filename: str,
        content: bytes,
        comment: str,
        *,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        def _send() -> dict[str, Any]:
            response = self.client.post(
                self.settings.wiki_api_url,
                data={
                    "format": "json",
                    "action": "upload",
                    "filename": filename,
                    "comment": comment,
                    "ignorewarnings": 1,
                    "token": self.csrf_token,
                },
                files={
                    "file": (
                        filename,
                        content,
                        content_type or "application/octet-stream",
                    )
                },
                headers=self._request_headers(),
            )
            response.raise_for_status()
            return response.json()

        payload = self._perform_csrf_action(_send)
        result = payload.get("upload", {}).get("result")
        if result != "Success":
            raise RuntimeError(f"MediaWiki upload failed: {payload}")
        return payload
