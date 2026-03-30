from __future__ import annotations

import unittest
from unittest.mock import patch

from app.constants import AssistantDetailLevel, AssistantMode
from app.schemas import ChatRequest
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

    def test_write_action_stops_at_preview_until_user_confirms(self) -> None:
        executor = object.__new__(AgentExecutor)

        state = {
            "question": "给使用规则加一条：每个 Shot 页面必须备注原日志存放位置。",
            "task_type": "write_action",
            "detail_level": "intro",
            "mode": "qa",
            "context_pages": ["Shot:Shot日志入口"],
            "evidence": [{"title": "Shot:Shot日志入口", "source_type": "context"}],
            "external_hits": 0,
            "structured_only": False,
            "write_preview_data": {
                "action_type": "update_managed_page_section",
                "metadata_json": {
                    "missing_fields": [],
                    "target_section": "使用规则",
                },
            },
            "write_result_data": None,
            "answer": "",
        }

        decision = executor._fallback_action(state)

        self.assertEqual(decision["action"], "answer")
        self.assertEqual(decision["stop_reason"], "write_preview_ready")

    def test_finalize_write_preview_uses_preview_not_committed_wording(self) -> None:
        executor = object.__new__(AgentExecutor)

        state = {
            "question": "给使用规则加一条：每个 Shot 页面必须备注原日志存放位置。",
            "task_type": "write_action",
            "detail_level": "intro",
            "mode": "qa",
            "context_pages": ["Shot:Shot日志入口"],
            "evidence": [{"title": "Shot:Shot日志入口", "source_type": "context"}],
            "external_hits": 0,
            "unresolved_gaps": [],
            "answer": "已完成规则添加",
            "steps": [],
            "write_preview_data": {
                "target_page": "Shot:Shot日志入口",
                "target_section": "使用规则",
                "metadata_json": {"missing_fields": []},
            },
            "write_result_data": None,
        }
        request = ChatRequest(
            question=state["question"],
            mode=AssistantMode.QA,
            detail_level=AssistantDetailLevel.INTRO,
            context_pages=["Shot:Shot日志入口"],
        )

        finalized = executor.finalize(state, request)

        self.assertIn("已生成写入预览", finalized["answer"])
        self.assertIn("请确认后再提交", finalized["answer"])


if __name__ == "__main__":
    unittest.main()
