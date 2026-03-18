from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SimAdvisorResult:
    success: bool
    model: str
    elapsed_s: float
    content: str | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


class SimAdvisorGateway:
    def __init__(self, executor_path: str, default_model: str, timeout: int = 180) -> None:
        self.executor_path = executor_path
        self.default_model = default_model
        self.timeout = timeout

        if not Path(self.executor_path).exists():
            raise FileNotFoundError(f"SimAdvisor executor not found: {self.executor_path}")

    def chat(
        self,
        *,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.2,
        context_files: list[str] | None = None,
        auto_route: bool = False,
        timeout: int | None = None,
        max_tokens: int | None = None,
    ) -> SimAdvisorResult:
        payload: dict[str, Any] = {
            "tool": "chat",
            "arguments": {
                "prompt": prompt,
                "model": model or self.default_model,
                "temperature": temperature,
                "auto_route": auto_route,
            },
        }
        if context_files:
            payload["arguments"]["context_files"] = context_files
        if max_tokens is not None:
            payload["arguments"]["max_tokens"] = max_tokens

        started = time.time()
        effective_timeout = timeout or self.timeout
        try:
            process = subprocess.run(
                ["python", self.executor_path, "--call", json.dumps(payload, ensure_ascii=False)],
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            elapsed = round(time.time() - started, 2)
            return SimAdvisorResult(
                success=False,
                model=payload["arguments"]["model"],
                elapsed_s=elapsed,
                error=f"SimAdvisor subprocess timeout after {effective_timeout}s",
            )
        elapsed = round(time.time() - started, 2)

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        if process.returncode != 0:
            return SimAdvisorResult(
                success=False,
                model=payload["arguments"]["model"],
                elapsed_s=elapsed,
                error=stderr or stdout or f"SimAdvisor exited with code {process.returncode}",
            )

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return SimAdvisorResult(
                success=False,
                model=payload["arguments"]["model"],
                elapsed_s=elapsed,
                error=f"Invalid JSON response: {stdout[:400]}",
            )

        return SimAdvisorResult(
            success=bool(data.get("success")),
            model=data.get("model") or payload["arguments"]["model"],
            elapsed_s=elapsed,
            content=data.get("content"),
            error=data.get("error"),
            raw=data,
        )
