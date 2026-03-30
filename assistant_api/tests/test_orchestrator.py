from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.constants import AssistantMode, TaskType
from app.schemas import ChatRequest, OperationPreviewPayload, OperationResultPayload
from app.services.orchestrator import _build_chat_response, _source_priority, classify_question, run_chat_stream


class OrchestratorClassificationTests(unittest.TestCase):
    def test_newcomer_explanation_stays_concept(self) -> None:
        task_type = classify_question(
            "什么是 TNSA？请用新人能懂的话解释。",
            AssistantMode.QA,
            ["Theory:TNSA"],
        )

        self.assertEqual(task_type, TaskType.CONCEPT)

    def test_learning_path_requires_explicit_navigation_intent(self) -> None:
        task_type = classify_question(
            "如果我要学 TPS，建议按什么顺序看 wiki？",
            AssistantMode.QA,
            ["Diagnostic:TPS"],
        )

        self.assertEqual(task_type, TaskType.LEARNING_PATH)

    def test_compare_beats_concept_even_with_current_page(self) -> None:
        task_type = classify_question(
            "RPA 和 TNSA 的核心差别是什么？",
            AssistantMode.QA,
            ["Theory:离子加速机制概览"],
        )

        self.assertEqual(task_type, TaskType.COMPARE)

    def test_page_structuring_stays_draft(self) -> None:
        task_type = classify_question(
            "帮我整理这个页面的词条。",
            AssistantMode.QA,
            ["Theory:TNSA"],
        )

        self.assertEqual(task_type, TaskType.DRAFT)

    def test_managed_page_section_edit_is_write_action(self) -> None:
        task_type = classify_question(
            "给使用规则加一条：每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称与文件夹完整路径。",
            AssistantMode.QA,
            ["Shot:Shot日志入口"],
        )

        self.assertEqual(task_type, TaskType.WRITE_ACTION)

    def test_managed_page_section_edit_with_edit_verb_is_write_action(self) -> None:
        task_type = classify_question(
            "编辑一下使用规则区域：加入一条规则：必须备份原实验记录excel的实际电脑ID及文件夹位置",
            AssistantMode.QA,
            ["Shot:Shot日志入口"],
        )

        self.assertEqual(task_type, TaskType.WRITE_ACTION)


class SourcePriorityTests(unittest.TestCase):
    def test_context_is_highest_priority_for_structured_only(self) -> None:
        self.assertLess(
            _source_priority("context", structured_only=True),
            _source_priority("cargo", structured_only=True),
        )

    def test_context_is_highest_priority_for_normal_answers(self) -> None:
        self.assertLess(
            _source_priority("context", structured_only=False),
            _source_priority("cargo", structured_only=False),
        )


class RunChatStreamWriteActionTests(unittest.TestCase):
    def test_write_action_stream_skips_answer_stream_when_preview_ready(self) -> None:
        settings = SimpleNamespace(conversation_history_turns=6, enable_zotero=False)
        request = ChatRequest(
            question="编辑一下使用规则区域：加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置",
            mode=AssistantMode.QA,
            context_pages=["Shot:Shot日志入口"],
            user_name="Admin",
        )

        class _FakeLLM:
            model_info = {
                "requested_model": "gpt-5.4",
                "resolved_model": "gpt-5.4",
                "provider": "openai_compatible",
                "fallback_applied": False,
                "fallback_reason": None,
            }

            def with_generation_config(self, _selection: object) -> "_FakeLLM":
                return self

        class _FakePreview:
            def model_dump(self) -> dict[str, object]:
                return {
                    "preview_id": "preview-1",
                    "action_type": "update_managed_page_section",
                    "operation": "replace_section_body",
                    "target_page": "Shot:Shot日志入口",
                    "target_section": "使用规则",
                    "preview_text": "目标页面：Shot:Shot日志入口",
                    "structured_payload": {"区块": "使用规则"},
                    "missing_fields": [],
                    "metadata": None,
                }

        class _FakeTurn:
            id = "turn-1"

        class _FakeResponse:
            def model_dump(self) -> dict[str, object]:
                return {"session_id": "session-1", "answer": "已生成写入预览：Shot:Shot日志入口 / 使用规则。请确认后再提交。"}

        class _FakeExecutor:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                return

            def execute(self, *_args: object, **_kwargs: object) -> dict[str, object]:
                return {
                    "steps": [{"stage": "write_preview", "title": "生成写入预览", "status": "complete", "detail": "ok"}],
                    "action_trace": [],
                    "evidence": [],
                    "external_hits": 0,
                    "unresolved_gaps": [],
                    "write_preview_data": {
                        "target_page": "Shot:Shot日志入口",
                        "target_section": "使用规则",
                        "metadata_json": {"missing_fields": []},
                    },
                    "write_result_data": None,
                    "answer": "",
                }

            def stream_answer(self, _state: dict[str, object]) -> object:
                raise AssertionError("write-action stream should not call stream_answer once preview is ready")

            def finalize(self, state: dict[str, object], _request: ChatRequest) -> dict[str, object]:
                state["answer"] = "已生成写入预览：Shot:Shot日志入口 / 使用规则。请确认后再提交。"
                return state

        with (
            patch("app.services.orchestrator._session_for_request", return_value=SimpleNamespace(id="session-1", current_page=None)),
            patch("app.services.orchestrator._conversation_history_for_session", return_value=[]),
            patch("app.services.orchestrator._apply_generation_selection", return_value=None),
            patch("app.services.orchestrator.classify_question", return_value=TaskType.WRITE_ACTION),
            patch("app.services.orchestrator.plan_sources", return_value=(["context"], False)),
            patch("app.services.orchestrator.AgentExecutor", _FakeExecutor),
            patch("app.services.orchestrator._persist_chat_state", return_value=(_FakeTurn(), _FakePreview(), None, None, _FakePreview(), None, None, None)),
            patch("app.services.orchestrator._build_chat_response", return_value=_FakeResponse()),
        ):
            events = list(run_chat_stream(object(), settings, _FakeLLM(), object(), object(), object(), request))

        event_names = [item["event"] for item in events]
        self.assertIn("operation_preview", event_names)
        self.assertIn("write_preview", event_names)
        self.assertIn("done", event_names)
        self.assertNotIn("token", event_names)


class BuildChatResponseOperationTests(unittest.TestCase):
    def test_build_chat_response_includes_operation_preview_and_result(self) -> None:
        response = _build_chat_response(
            session_record=SimpleNamespace(id="session-1"),
            turn=SimpleNamespace(id="turn-1"),
            state={
                "task_type": TaskType.WRITE_ACTION.value,
                "answer": "已生成写入预览",
                "steps": [],
                "evidence": [],
                "confidence": 0.8,
                "unresolved_gaps": [],
                "suggested_followups": [],
                "action_trace": [],
            },
            operation_preview=OperationPreviewPayload(
                preview_id="preview-1",
                kind="managed_section_edit",
                operation="replace_section_body",
                target_page="Shot:Shot日志入口",
                target_section="使用规则",
                title="Shot:Shot日志入口",
                content="目标页面：Shot:Shot日志入口",
                structured_payload={"区块": "使用规则"},
                missing_fields=[],
                metadata=None,
            ),
            operation_result=OperationResultPayload(
                status="success",
                kind="managed_section_edit",
                operation="replace_section_body",
                page_title="Shot:Shot日志入口",
                target_section="使用规则",
                detail="受控提交已执行。",
                metadata=None,
            ),
            draft_preview=None,
            write_preview=None,
            write_result=None,
            result_fill=None,
            pdf_ingest_review=None,
        )

        self.assertIsNotNone(response.operation_preview)
        self.assertEqual(response.operation_preview.kind, "managed_section_edit")
        self.assertIsNotNone(response.operation_result)
        self.assertEqual(response.operation_result.target_section, "使用规则")


if __name__ == "__main__":
    unittest.main()
