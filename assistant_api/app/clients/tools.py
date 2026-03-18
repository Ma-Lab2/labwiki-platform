from __future__ import annotations

from typing import Any

import httpx

from ..config import Settings
from ..constants import READ_ONLY_TOOL_ACTIONS, ToolName


class ToolClients:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.Client(timeout=90.0)

    def tps_execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action not in READ_ONLY_TOOL_ACTIONS[ToolName.TPS]:
            raise ValueError(f"Unsupported TPS action: {action}")
        if action == "health":
            response = self.client.get(f"{self.settings.tps_base_url}/api/health")
        elif action == "browse":
            response = self.client.get(f"{self.settings.tps_base_url}/api/files/browse", params=payload)
        elif action == "list":
            response = self.client.get(f"{self.settings.tps_base_url}/api/files/list", params=payload)
        elif action == "solve":
            response = self.client.post(f"{self.settings.tps_base_url}/api/analysis/solve", json=payload)
        elif action == "batch":
            response = self.client.post(f"{self.settings.tps_base_url}/api/analysis/batch", json=payload)
        elif action == "compare":
            response = self.client.post(f"{self.settings.tps_base_url}/api/analysis/compare", json=payload)
        response.raise_for_status()
        return response.json()

    def rcf_execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action not in READ_ONLY_TOOL_ACTIONS[ToolName.RCF]:
            raise ValueError(f"Unsupported RCF action: {action}")
        if action == "health":
            response = self.client.get(f"{self.settings.rcf_base_url}/health")
        elif action == "energy-scan":
            response = self.client.post(f"{self.settings.rcf_base_url}/compute/energy-scan", json=payload)
        elif action == "linear-design":
            response = self.client.post(f"{self.settings.rcf_base_url}/compute/linear-design", json=payload)
        elif action == "validate-stack":
            response = self.client.post(f"{self.settings.rcf_base_url}/stack/validate", json=payload)
        response.raise_for_status()
        return response.json()
