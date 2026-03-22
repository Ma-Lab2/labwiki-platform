from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.agent_loop import AgentExecutor


class _FakeLLM:
    def answer_from_evidence(self, **_: object) -> str:
        return "fallback"


class AgentLoopWritePreviewTests(unittest.TestCase):
    def test_prepare_write_preview_error_is_recorded_without_raising(self) -> None:
        executor = object.__new__(AgentExecutor)
        executor.settings = object()
        executor.llm = _FakeLLM()
        executor.wiki = object()

        state = {
            "question": "请帮我把 Mechanism 相关页面串起来。",
            "answer": "",
            "task_type": "answer",
            "detail_level": "intro",
            "mode": "qa",
            "context_pages": ["机制条目索引"],
            "evidence": [{"title": "机制条目索引"}],
            "unresolved_gaps": [],
            "conversation_history": [],
            "action_trace": [],
            "steps": [],
        }

        with patch(
            "app.services.agent_loop.prepare_write_preview",
            side_effect=ValueError("当前问题不属于受支持的写操作类型"),
        ):
            executor._tool_prepare_write_preview(state)

        self.assertNotIn("write_preview_data", state)
        self.assertEqual(state["action_trace"][-1]["action"], "prepare_write_preview")
        self.assertEqual(state["action_trace"][-1]["status"], "error")
        self.assertEqual(state["steps"][-1]["status"], "error")


if __name__ == "__main__":
    unittest.main()
