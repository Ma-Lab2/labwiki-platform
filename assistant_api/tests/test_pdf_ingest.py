from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import main
from app.models import Base, DraftPreview
from app.services.attachments import store_attachment
from app.services.pdf_ingest import prepare_pdf_ingest_review
from app.schemas import ChatRequest


ROOT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_PDF = ROOT_DIR / "怀柔真空管道电机控制.pdf"


class _DisabledGenerationProvider:
    enabled = False


class _DisabledLLM:
    def __init__(self) -> None:
        self.generation_provider = _DisabledGenerationProvider()


class _EnabledGenerationProvider:
    enabled = True


class _StructuredLLM:
    def __init__(self, raw_payload: dict[str, object]) -> None:
        self.generation_provider = _EnabledGenerationProvider()
        self._raw_payload = raw_payload

    def generate_prompt(self, prompt) -> str:
        return json.dumps(self._raw_payload, ensure_ascii=False)


class _Settings:
    def __init__(self, attachments_dir: Path) -> None:
        self.attachments_dir = str(attachments_dir)
        self.draft_prefix = "知识助手草稿"


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


class PdfIngestServiceTests(unittest.TestCase):
    def test_prepare_pdf_ingest_review_fallback_extracts_control_manual_shape(self) -> None:
        self.assertTrue(SAMPLE_PDF.exists(), f"missing sample pdf: {SAMPLE_PDF}")
        with tempfile.TemporaryDirectory() as tmp_dir:
            attachments_dir = Path(tmp_dir)
            attachment = store_attachment(
                attachments_dir=attachments_dir,
                filename=SAMPLE_PDF.name,
                content_type="application/pdf",
                content=SAMPLE_PDF.read_bytes(),
            )
            request = ChatRequest(
                question="请读取这个 PDF，告诉我里面的内容，并建议可以写入哪个区域。",
                context_pages=["首页"],
                attachments=[attachment],
                workflow_hint="pdf_ingest_write",
                user_name="Alice",
            )

            result = prepare_pdf_ingest_review(
                settings=_Settings(attachments_dir),
                llm=_DisabledLLM(),
                attachments_dir=attachments_dir,
                request=request,
            )

        self.assertEqual(result["source_attachment_id"], attachment.id)
        self.assertEqual(result["extracted_page_count"], 6)
        self.assertEqual(result["staged_image_count"], 6)
        self.assertEqual(result["recommended_targets"][0]["target_type"], "control")
        self.assertTrue(result["recommended_targets"][0]["target_title"].startswith("Control:"))
        self.assertIn("电机控制", result["document_summary"])
        self.assertIn("SMC Basic Studio", result["document_summary"])
        self.assertTrue(any(section["title"] == "操作步骤" for section in result["section_outline"]))

    def test_prepare_pdf_ingest_review_normalizes_target_prefixes_from_model_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            attachments_dir = Path(tmp_dir)
            attachment = store_attachment(
                attachments_dir=attachments_dir,
                filename=SAMPLE_PDF.name,
                content_type="application/pdf",
                content=SAMPLE_PDF.read_bytes(),
            )
            request = ChatRequest(
                question="请分析 PDF 并建议写入区域。",
                context_pages=["首页"],
                attachments=[attachment],
                workflow_hint="pdf_ingest_write",
                user_name="Alice",
            )

            result = prepare_pdf_ingest_review(
                settings=_Settings(attachments_dir),
                llm=_StructuredLLM(
                    {
                        "title": "怀柔真空管道电机控制",
                        "document_summary": "这是一份控制操作说明。",
                        "recommended_targets": [
                            {
                                "target_type": "control",
                                "target_title": "怀柔真空管道电机控制流程",
                                "score": 0.96,
                                "reason": "控制软件和控制器配置步骤。",
                            },
                            {
                                "target_type": "device_entry",
                                "target_title": "怀柔真空管道电机控制系统",
                                "score": 0.86,
                                "reason": "设备结构和系统用途。",
                            },
                        ],
                        "section_outline": [
                            {"title": "操作步骤", "content": "1. 打开软件\n2. 设置 IP"}
                        ],
                        "proposed_draft_title": "知识助手草稿/PDF提取/怀柔真空管道电机控制",
                        "extracted_page_count": 6,
                        "staged_image_count": 6,
                        "evidence": ["PDF 文件：怀柔真空管道电机控制.pdf"],
                        "needs_confirmation": True,
                    }
                ),
                attachments_dir=attachments_dir,
                request=request,
            )

        self.assertEqual(result["recommended_targets"][0]["target_title"], "Control:怀柔真空管道电机控制流程")
        self.assertEqual(result["recommended_targets"][1]["target_title"], "设备条目/怀柔真空管道电机控制系统")


class PdfIngestRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.attachments_dir = Path(self.tmp_dir.name) / "attachments"
        self.attachments_dir.mkdir(parents=True, exist_ok=True)
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

    def test_pdf_draft_preview_builds_draft_page_with_all_page_images(self) -> None:
        self.assertTrue(SAMPLE_PDF.exists(), f"missing sample pdf: {SAMPLE_PDF}")
        attachment = store_attachment(
            attachments_dir=self.attachments_dir,
            filename=SAMPLE_PDF.name,
            content_type="application/pdf",
            content=SAMPLE_PDF.read_bytes(),
        )
        review = prepare_pdf_ingest_review(
            settings=_Settings(self.attachments_dir),
            llm=_DisabledLLM(),
            attachments_dir=self.attachments_dir,
            request=ChatRequest(
                question="请读取这个 PDF，告诉我里面的内容，并建议可以写入哪个区域。",
                context_pages=["首页"],
                attachments=[attachment],
                workflow_hint="pdf_ingest_write",
                user_name="Alice",
            ),
        )

        with patch("app.main.session_scope", self._patched_scope), \
                patch("app.main.settings", _Settings(self.attachments_dir)):
            response = self.client.post(
                "/pdf/draft/preview",
                json={
                    "session_id": "session-pdf",
                    "turn_id": "turn-pdf",
                    "attachment_id": attachment.id,
                    "review": review,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["target_page"].startswith("知识助手草稿/PDF提取/怀柔真空管道电机控制"))
        self.assertIn("建议正式归档区域", payload["content"])
        self.assertIn("Control:", payload["content"])
        self.assertIn("[[File:PDF提取-怀柔真空管道电机控制", payload["content"])
        self.assertEqual(len(payload["metadata"]["pdf_ingest_images"]), 6)

    def test_draft_commit_uploads_pdf_ingest_images_before_editing_page(self) -> None:
        image_dir = self.attachments_dir / "staged"
        image_dir.mkdir(parents=True, exist_ok=True)
        image_one = image_dir / "page-01.png"
        image_two = image_dir / "page-02.png"
        image_one.write_bytes(b"png-page-01")
        image_two.write_bytes(b"png-page-02")

        with self.session_factory() as db:
            preview = DraftPreview(
                id="preview-pdf",
                session_id="session-pdf",
                turn_id="turn-pdf",
                title="怀柔真空管道电机控制",
                target_page="知识助手草稿/PDF提取/怀柔真空管道电机控制",
                content=(
                    "== 全部页图 ==\n"
                    "[[File:PDF提取-怀柔真空管道电机控制-p01-att1234.png|thumb|第 1 页]]\n"
                    "[[File:PDF提取-怀柔真空管道电机控制-p02-att1234.png|thumb|第 2 页]]"
                ),
                metadata_json={
                    "kind": "pdf_ingest_draft",
                    "pdf_ingest_images": [
                        {
                            "file_title": "PDF提取-怀柔真空管道电机控制-p01-att1234.png",
                            "blob_path": str(image_one),
                            "mime_type": "image/png",
                            "page_number": 1,
                        },
                        {
                            "file_title": "PDF提取-怀柔真空管道电机控制-p02-att1234.png",
                            "blob_path": str(image_two),
                            "mime_type": "image/png",
                            "page_number": 2,
                        },
                    ],
                },
            )
            db.add(preview)
            db.commit()

        uploaded: list[str] = []

        def _fake_upload(filename: str, content: bytes, comment: str, content_type: str | None = None):
            uploaded.append(filename)
            return {"result": "Success", "filename": filename}

        with patch("app.main.session_scope", self._patched_scope), \
                patch.object(main.wiki, "upload_file", side_effect=_fake_upload) as mock_upload, \
                patch.object(main.wiki, "edit_page", return_value={"edit": {"result": "Success"}}) as mock_edit:
            response = self.client.post("/draft/commit", json={"preview_id": "preview-pdf"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(uploaded, [
            "PDF提取-怀柔真空管道电机控制-p01-att1234.png",
            "PDF提取-怀柔真空管道电机控制-p02-att1234.png",
        ])
        self.assertEqual(mock_upload.call_count, 2)
        self.assertEqual(mock_edit.call_count, 1)
        self.assertEqual(response.json()["page_title"], "知识助手草稿/PDF提取/怀柔真空管道电机控制")

    def test_pdf_control_preview_builds_formal_control_page_and_blocks_sensitive_lines(self) -> None:
        with self.session_factory() as db:
            preview = DraftPreview(
                id="preview-draft-control",
                session_id="session-pdf",
                turn_id="turn-pdf",
                title="怀柔真空管道电机控制",
                target_page="知识助手草稿/PDF提取/怀柔真空管道电机控制",
                content="== 文档摘要 ==\n这是一份控制手册。",
                metadata_json={
                    "kind": "pdf_ingest_draft",
                    "source_attachment_id": "att-pdf-1",
                    "review_snapshot": {
                        "file_name": "怀柔真空管道电机控制.pdf",
                        "document_summary": "这是一份真空管道电机控制和软件配置说明。",
                        "recommended_targets": [
                            {
                                "target_type": "control",
                                "target_title": "Control:怀柔真空管道电机控制流程",
                                "reason": "更像控制/运行手册。",
                            },
                        ],
                        "section_outline": [
                            {
                                "title": "操作步骤",
                                "content": "1. 打开 SMC Basic Studio\n2. 设置控制器 IP 为 128\n3. 输入账号 admin 和密码 123456",
                            },
                            {
                                "title": "关键参数与软件",
                                "content": "软件：SMC Basic Studio\n下载地址：http://192.168.0.8/setup",
                            },
                        ],
                        "evidence": ["PDF 文件：怀柔真空管道电机控制.pdf"],
                    },
                    "pdf_ingest_images": [
                        {
                            "file_title": "PDF提取-怀柔真空管道电机控制-p01-att1234.png",
                            "blob_path": "/tmp/page-01.png",
                            "mime_type": "image/png",
                            "page_number": 1,
                        }
                    ],
                },
            )
            db.add(preview)
            db.commit()

        with patch("app.main.session_scope", self._patched_scope), \
                patch.object(main.wiki, "get_page_text", side_effect=lambda title: {
                    "Control:怀柔真空管道电机控制流程": "",
                    "Control:控制与运行总览": (
                        "= Control:控制与运行总览 =\n\n"
                        "== 当前入口 ==\n"
                        "* [[Control:中央控制平台]]\n"
                    ),
                }.get(title, "")):
            response = self.client.post(
                "/pdf/control/preview",
                json={"draft_preview_id": "preview-draft-control"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["target_page"], "Control:怀柔真空管道电机控制流程")
        self.assertEqual(payload["overview_page"], "Control:控制与运行总览")
        self.assertIn("== 页面定位 ==", payload["content"])
        self.assertIn("[[Control:控制与运行总览]]", payload["content"])
        self.assertIn("[[知识助手草稿/PDF提取/怀柔真空管道电机控制]]", payload["content"])
        self.assertNotIn("密码 123456", payload["content"])
        self.assertNotIn("http://192.168.0.8/setup", payload["content"])
        self.assertIn("[[Control:怀柔真空管道电机控制流程]]", payload["overview_update"])
        self.assertEqual(len(payload["blocked_items"]), 2)
        self.assertEqual(
            [item["label"] for item in payload["blocked_items"]],
            ["操作步骤", "关键参数与软件"],
        )

    def test_pdf_control_commit_updates_formal_page_and_control_index(self) -> None:
        with self.session_factory() as db:
            preview = DraftPreview(
                id="preview-formal-control",
                session_id="session-pdf",
                turn_id="turn-pdf",
                title="Control:怀柔真空管道电机控制流程",
                target_page="Control:怀柔真空管道电机控制流程",
                content="<!-- LABASSISTANT_CONTROL_START -->\n== 页面定位 ==\n控制说明\n<!-- LABASSISTANT_CONTROL_END -->",
                metadata_json={
                    "kind": "pdf_control_formal_preview",
                    "overview_page": "Control:控制与运行总览",
                    "overview_content": (
                        "= Control:控制与运行总览 =\n\n"
                        "== 助手整理专题 ==\n"
                        "* [[Control:怀柔真空管道电机控制流程]]：真空管道电机控制和软件配置说明。\n"
                    ),
                    "blocked_items": [
                        {
                            "label": "关键参数与软件",
                            "reason": "疑似受限信息",
                            "content": "下载地址：http://192.168.0.8/setup",
                        }
                    ],
                },
            )
            db.add(preview)
            db.commit()

        with patch("app.main.session_scope", self._patched_scope), \
                patch.object(main.wiki, "edit_page", return_value={"edit": {"result": "Success"}}) as mock_edit:
            response = self.client.post("/pdf/control/commit", json={"preview_id": "preview-formal-control"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_edit.call_count, 2)
        first_call = mock_edit.call_args_list[0]
        second_call = mock_edit.call_args_list[1]
        self.assertEqual(first_call.args[0], "Control:怀柔真空管道电机控制流程")
        self.assertEqual(second_call.args[0], "Control:控制与运行总览")
        self.assertEqual(response.json()["page_title"], "Control:怀柔真空管道电机控制流程")
        self.assertEqual(response.json()["overview_page"], "Control:控制与运行总览")
        self.assertEqual(response.json()["blocked_count"], 1)


if __name__ == "__main__":
    unittest.main()
