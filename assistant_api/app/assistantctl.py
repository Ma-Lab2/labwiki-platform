from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://localhost:8443/tools/assistant/api"


def _build_http_opener() -> urllib.request.OpenerDirector:
    # Local assistant entrypoints should bypass shell/browser proxy settings.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with _build_http_opener().open(request, timeout=180) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _build_chat_payload(
    *,
    question: str,
    mode: str,
    session_id: str | None,
    context_pages: list[str],
    model: str | None,
) -> dict[str, Any]:
    payload = {
        "question": question,
        "mode": mode,
        "detail_level": "intro",
        "session_id": session_id,
        "context_pages": context_pages,
    }
    if model:
        payload["generation_model"] = model
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="assistantctl")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Assistant API base URL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--model")
    ask.add_argument("--session-id")
    ask.add_argument("--context-page", action="append", dest="context_pages", default=[])

    draft = subparsers.add_parser("draft")
    draft.add_argument("question")
    draft.add_argument("--model")
    draft.add_argument("--session-id")
    draft.add_argument("--context-page", action="append", dest="context_pages", default=[])

    stream = subparsers.add_parser("stream")
    stream.add_argument("question")
    stream.add_argument("--model")
    stream.add_argument("--session-id")
    stream.add_argument("--context-page", action="append", dest="context_pages", default=[])

    tools = subparsers.add_parser("tools")
    tools_sub = tools.add_subparsers(dest="tools_command", required=True)
    tools_sub.add_parser("list")

    session = subparsers.add_parser("session")
    session_sub = session.add_subparsers(dest="session_command", required=True)
    show = session_sub.add_parser("show")
    show.add_argument("session_id")

    confirm = subparsers.add_parser("confirm")
    confirm.add_argument("preview_id")
    confirm.add_argument("--action-id", default="write.commit")

    args = parser.parse_args(argv)
    base_url = args.base_url.rstrip("/")

    try:
        if args.command == "ask":
            payload = _build_chat_payload(
                question=args.question,
                mode="qa",
                session_id=args.session_id,
                context_pages=args.context_pages,
                model=args.model,
            )
            _print_json(_request_json("POST", f"{base_url}/chat", payload))
            return 0

        if args.command == "draft":
            payload = _build_chat_payload(
                question=args.question,
                mode="draft",
                session_id=args.session_id,
                context_pages=args.context_pages,
                model=args.model,
            )
            _print_json(_request_json("POST", f"{base_url}/chat", payload))
            return 0

        if args.command == "stream":
            payload = _build_chat_payload(
                question=args.question,
                mode="qa",
                session_id=args.session_id,
                context_pages=args.context_pages,
                model=args.model,
            )
            req = urllib.request.Request(
                f"{base_url}/chat/stream",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
                method="POST",
            )
            with _build_http_opener().open(req, timeout=180) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").rstrip()
                    if line:
                        print(line)
            return 0

        if args.command == "tools" and args.tools_command == "list":
            _print_json(_request_json("GET", f"{base_url}/capabilities"))
            return 0

        if args.command == "session" and args.session_command == "show":
            _print_json(_request_json("GET", f"{base_url}/session/{args.session_id}"))
            return 0

        if args.command == "confirm":
            _print_json(
                _request_json(
                    "POST",
                    f"{base_url}/actions/commit",
                    {"action_id": args.action_id, "preview_id": args.preview_id},
                )
            )
            return 0
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        sys.stderr.write(body + "\n")
        return 1
    except Exception as error:  # pragma: no cover - CLI shell path
        sys.stderr.write(f"{error}\n")
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
