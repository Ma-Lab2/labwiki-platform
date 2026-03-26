from __future__ import annotations

import tempfile
import unittest
import base64
from pathlib import Path

from app.schemas import ChatRequest
from app.services.attachments import (
    AttachmentStorageError,
    build_attachment_prompt_parts,
    load_attachment_file,
    store_attachment,
)


class ChatRequestAttachmentTests(unittest.TestCase):
    def test_chat_request_accepts_attachment_items(self) -> None:
        request = ChatRequest(
            question="请结合这个文件解释当前页面内容",
            attachments=[
                {
                    "id": "att-001",
                    "kind": "document",
                    "name": "shot-note.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 1024,
                }
            ],
        )

        self.assertEqual(len(request.attachments), 1)
        self.assertEqual(request.attachments[0].id, "att-001")
        self.assertEqual(request.attachments[0].kind, "document")


class AttachmentStorageTests(unittest.TestCase):
    def test_store_attachment_persists_metadata_and_blob(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = store_attachment(
                attachments_dir=Path(tmp_dir),
                filename="beam-profile.png",
                content_type="image/png",
                content=b"png-bytes",
            )

            self.assertEqual(payload.kind, "image")
            self.assertEqual(payload.mime_type, "image/png")
            self.assertEqual(payload.name, "beam-profile.png")
            self.assertEqual(payload.size_bytes, 9)
            self.assertTrue((Path(tmp_dir) / payload.id / "blob").exists())
            self.assertTrue((Path(tmp_dir) / payload.id / "meta.json").exists())

    def test_store_attachment_rejects_unsupported_mime_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(AttachmentStorageError):
                store_attachment(
                    attachments_dir=Path(tmp_dir),
                    filename="archive.zip",
                    content_type="application/zip",
                    content=b"zip",
                )

    def test_build_attachment_prompt_parts_includes_inline_image_payload(self) -> None:
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+k7N8AAAAASUVORK5CYII="
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = store_attachment(
                attachments_dir=Path(tmp_dir),
                filename="shot-summary.png",
                content_type="image/png",
                content=png_bytes,
            )

            parts = build_attachment_prompt_parts(
                attachments_dir=Path(tmp_dir),
                attachments=[payload],
            )

            self.assertEqual(parts[0]["type"], "text")
            self.assertIn("shot-summary.png", parts[0]["text"])
            self.assertEqual(parts[1]["type"], "image")
            self.assertEqual(parts[1]["mime_type"], "image/png")
            self.assertTrue(parts[1]["data"])

    def test_load_attachment_file_returns_metadata_and_blob_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            payload = store_attachment(
                attachments_dir=Path(tmp_dir),
                filename="paper.pdf",
                content_type="application/pdf",
                content=b"%PDF-test",
            )

            item, blob_path = load_attachment_file(
                attachments_dir=Path(tmp_dir),
                attachment_id=payload.id,
            )

            self.assertEqual(item.id, payload.id)
            self.assertEqual(item.mime_type, "application/pdf")
            self.assertEqual(blob_path.read_bytes(), b"%PDF-test")


if __name__ == "__main__":
    unittest.main()
