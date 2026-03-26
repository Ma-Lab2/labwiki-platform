from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.models import AssistantSession, AssistantTurn, Base
from app.services.session_exports import build_session_markdown


@contextmanager
def _session_scope_factory(session_factory):
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class SessionExportRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp_dir.name) / "assistant.db"
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(self.engine)
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        self.client.close()
        self.engine.dispose()
        self.tmp_dir.cleanup()

    def _patched_scope(self):
        return _session_scope_factory(self.session_factory)

    def test_sessions_endpoint_returns_current_users_history_sorted_by_recent_update(self) -> None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as db:
            older = AssistantSession(
                id="session-older",
                user_name="Alice",
                current_page="Theory:TNSA",
                updated_at=now - timedelta(hours=2),
                created_at=now - timedelta(days=1),
            )
            newer = AssistantSession(
                id="session-newer",
                user_name="Alice",
                current_page="Shot:2026-03-24-Run02-Shot003",
                updated_at=now - timedelta(minutes=5),
                created_at=now - timedelta(hours=1),
            )
            other_user = AssistantSession(
                id="session-other",
                user_name="Bob",
                current_page="Theory:RPA",
                updated_at=now - timedelta(minutes=1),
                created_at=now - timedelta(hours=3),
            )
            db.add_all([older, newer, other_user])
            db.add_all(
                [
                    AssistantTurn(
                        id="turn-older",
                        session_id=older.id,
                        question="解释 TNSA",
                        answer="older answer",
                        task_type="concept",
                        mode="qa",
                    ),
                    AssistantTurn(
                        id="turn-newer",
                        session_id=newer.id,
                        question="整理这发 shot",
                        answer="newer answer",
                        task_type="shot_record",
                        mode="qa",
                    ),
                    AssistantTurn(
                        id="turn-other",
                        session_id=other_user.id,
                        question="别人的会话",
                        answer="should stay hidden",
                        task_type="concept",
                        mode="qa",
                    ),
                ]
            )
            db.commit()

        with patch("app.main.session_scope", self._patched_scope):
            response = self.client.get("/sessions", params={"user_name": "Alice"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["session_id"] for item in payload["sessions"]], ["session-newer", "session-older"])
        self.assertEqual(payload["sessions"][0]["latest_question"], "整理这发 shot")
        self.assertEqual(payload["sessions"][0]["turn_count"], 1)
        self.assertEqual(payload["sessions"][1]["current_page"], "Theory:TNSA")

    def test_session_markdown_export_returns_downloadable_markdown(self) -> None:
        now = datetime(2026, 3, 25, 12, 30, tzinfo=timezone.utc)
        with self.session_factory() as db:
            session_record = AssistantSession(
                id="session-export",
                user_name="Alice",
                current_page="Shot:2026-03-25-Run07-Shot004",
                created_at=now - timedelta(hours=1),
                updated_at=now,
            )
            turn = AssistantTurn(
                id="turn-export",
                session_id=session_record.id,
                question="请整理当前页并保留来源",
                answer="这是整理后的说明。",
                task_type="shot_record",
                mode="qa",
                sources=[
                    {
                        "source_type": "wiki_page",
                        "source_id": "Shot:2026-03-25-Run07-Shot004",
                        "title": "Shot:2026-03-25-Run07-Shot004",
                        "url": "http://wiki.test/Shot:2026-03-25-Run07-Shot004",
                    }
                ],
                unresolved_gaps=["真空值未在页面中找到"],
                suggested_followups=["补充真空并再次生成摘要"],
                result_fill={
                    "title": "Shot 结果回填建议",
                    "field_suggestions": {
                        "Run": {
                            "value": "Run07",
                            "status": "confirmed",
                            "evidence": ["当前页 Shot:2026-03-25-Run07-Shot004"],
                        },
                        "处理结果文件": {
                            "value": "Shot-2026-03-25-Run07-Shot004-analysis.zip",
                            "status": "pending",
                            "reason": "按标题推得候选值，请学生确认。",
                            "evidence": ["当前页 Shot:2026-03-25-Run07-Shot004"],
                        },
                    },
                    "draft_text": "== 结果摘要 ==\n* Run07 效果稳定。",
                    "missing_items": [
                        {
                            "label": "判断依据",
                            "reason": "当前没有足够结构化信息。",
                            "evidence": ["当前页 Shot:2026-03-25-Run07-Shot004"],
                        }
                    ],
                    "evidence": ["当前页 Shot:2026-03-25-Run07-Shot004"],
                },
                draft_preview={
                    "preview_id": "draft-1",
                    "title": "Shot 草稿",
                    "target_page": "知识助手草稿/Shot-Run07",
                    "content": "draft body",
                    "metadata": {"kind": "draft"},
                },
                pdf_ingest_review={
                    "title": "PDF 解析与写入建议",
                    "source_attachment_id": "att-pdf",
                    "file_name": "怀柔真空管道电机控制.pdf",
                    "document_summary": "文档更像一份电机控制/操作手册。",
                    "recommended_targets": [
                        {
                            "target_type": "control",
                            "target_title": "Control:怀柔真空管道电机控制",
                            "score": 0.92,
                            "reason": "包含控制软件、控制器 IP 和轴使能步骤。",
                        }
                    ],
                    "proposed_draft_title": "知识助手草稿/PDF提取/怀柔真空管道电机控制",
                    "section_outline": [
                        {
                            "title": "操作步骤",
                            "content": "- 打开 SMC Basic Studio\n- 更改控制器 IP 为 128",
                        }
                    ],
                    "extracted_page_count": 6,
                    "staged_image_count": 6,
                    "evidence": ["PDF 文件：怀柔真空管道电机控制.pdf"],
                    "needs_confirmation": True,
                },
                write_result={
                    "status": "ok",
                    "page_title": "Shot:2026-03-25-Run07-Shot004",
                    "operation": "update",
                    "action_type": "write.commit",
                    "detail": "已写入受管事实块",
                },
                step_stream=[{"stage": "internal", "title": "不应导出", "status": "completed", "detail": "internal"}],
                action_trace=[{"action": "tool", "status": "ok", "summary": "不应导出"}],
                created_at=now,
            )
            db.add(session_record)
            db.add(turn)
            db.commit()

        with patch("app.main.session_scope", self._patched_scope):
            response = self.client.get("/session/session-export/export.md", params={"user_name": "Alice"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/markdown", response.headers["content-type"])
        self.assertIn(".md", response.headers["content-disposition"])
        body = response.text
        self.assertIn("# 智能助手聊天记录导出", body)
        self.assertIn("Shot:2026-03-25-Run07-Shot004", body)
        self.assertIn("## 第 1 轮", body)
        self.assertIn("### 用户", body)
        self.assertIn("### 助手", body)
        self.assertIn("### 来源", body)
        self.assertIn("### 结果摘要", body)
        self.assertIn("已识别字段", body)
        self.assertIn("待确认字段", body)
        self.assertIn("缺失字段", body)
        self.assertIn("真空值未在页面中找到", body)
        self.assertIn("Shot 草稿", body)
        self.assertIn("PDF 摄取建议", body)
        self.assertIn("Control:怀柔真空管道电机控制", body)
        self.assertIn("已写入受管事实块", body)
        self.assertNotIn("不应导出", body)


class SessionExportFormatterTests(unittest.TestCase):
    def test_build_session_markdown_uses_practical_export_shape(self) -> None:
        now = datetime(2026, 3, 25, 8, 0, tzinfo=timezone.utc)
        session_record = AssistantSession(
            id="session-shape",
            user_name="Alice",
            current_page="Theory:TNSA",
            created_at=now,
            updated_at=now,
        )
        turns = [
            AssistantTurn(
                id="turn-shape",
                session_id=session_record.id,
                question="解释 TNSA",
                answer="TNSA 是常见离子加速机制。",
                task_type="concept",
                mode="qa",
                created_at=now,
                sources=[
                    {
                        "source_type": "wiki_page",
                        "source_id": "Theory:TNSA",
                        "title": "Theory:TNSA",
                        "url": "http://wiki.test/Theory:TNSA",
                    }
                ],
                suggested_followups=["继续比较 RPA"],
            )
        ]

        markdown = build_session_markdown(session_record, turns)

        self.assertIn("会话 ID：`session-shape`", markdown)
        self.assertIn("Theory:TNSA", markdown)
        self.assertIn("继续比较 RPA", markdown)
        self.assertIn("TNSA 是常见离子加速机制。", markdown)


if __name__ == "__main__":
    unittest.main()
