from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.services.capabilities import (
    build_capability_catalog,
    commit_capability_action,
    preview_capability_action,
)


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "sqlite://",
        "postgres_password": None,
        "wiki_url": "http://wiki.test",
        "wiki_api_base_url": None,
        "wiki_api_host_header": None,
        "wiki_api_path": "/api.php",
        "wiki_index_path": "/index.php",
        "wiki_user": "admin",
        "wiki_password": "secret",
        "wiki_verify_tls": False,
        "draft_prefix": "知识助手草稿",
        "enable_zotero": False,
        "zotero_snapshot_dir": "/tmp/zotero",
        "generation_provider": "openai_compatible",
        "anthropic_base_url": "https://anthropic.example",
        "anthropic_api_key": "anthropic-key",
        "anthropic_model": "claude-sonnet-4-5-20250929-thinking",
        "anthropic_timeout": 180,
        "anthropic_max_tokens": 2048,
        "openai_base_url": "https://api.openai.com/v1",
        "openai_api_key": "openai-key",
        "openai_model": "gpt-4.1-mini",
        "openai_timeout": 180,
        "openai_max_tokens": 2048,
        "openai_compatible_base_url": "https://relay.example/v1",
        "openai_compatible_api_key": "relay-key",
        "openai_compatible_model": "gpt-5.4-mini",
        "openai_compatible_timeout": 180,
        "openai_compatible_max_tokens": 2048,
        "embedding_base_url": "https://relay.example/v1",
        "embedding_api_key": "embed-key",
        "embedding_model": "text-embedding-3-large",
        "embedding_timeout": 60,
        "embedding_dimensions": 3072,
        "vector_store_backend": "pgvector",
        "retrieval_tokenizer_mode": "mixed",
        "retrieval_normalization_mode": "basic",
        "web_search_provider": "none",
        "openai_web_search_model": None,
        "tavily_api_key": None,
        "conversation_history_turns": 4,
        "confidence_threshold": 0.72,
        "loop_max_steps": 8,
        "loop_max_external": 3,
        "reindex_batch_size": 50,
        "attachments_dir": tempfile.mkdtemp(prefix="assistant-capabilities-"),
        "enable_web_search": False,
        "tps_base_url": "http://tps",
        "rcf_base_url": "http://rcf",
        "cors_allowed_origins": ["http://127.0.0.1:8443"],
    }
    base.update(overrides)
    return Settings(**base)


class CapabilityCatalogTests(unittest.TestCase):
    def test_catalog_exposes_local_and_provider_status(self) -> None:
        settings = _settings()

        catalog = build_capability_catalog(settings)

        self.assertIn("providers", catalog)
        self.assertIn("capabilities", catalog)
        capability_ids = {item["id"] for item in catalog["capabilities"]}
        provider_ids = {item["id"] for item in catalog["providers"]}

        self.assertIn("local_knowledge", provider_ids)
        self.assertIn("native_cli", provider_ids)
        self.assertIn("draft.prepare", capability_ids)
        self.assertIn("write.prepare", capability_ids)
        self.assertIn("tool.tps.health", capability_ids)
        self.assertIn("tool.rcf.health", capability_ids)

    def test_catalog_marks_opencli_unavailable_without_binary(self) -> None:
        settings = _settings()
        with patch("app.services.capabilities.shutil.which", return_value=None):
            catalog = build_capability_catalog(settings)

        provider = next(item for item in catalog["providers"] if item["id"] == "opencli")
        self.assertFalse(provider["available"])


class CapabilityActionTests(unittest.TestCase):
    def test_preview_action_wraps_draft_preview(self) -> None:
        settings = _settings()
        fake_preview = {
            "preview_id": "draft-1",
            "title": "TNSA 草稿",
            "target_page": "知识助手草稿/TNSA",
            "content": "draft body",
            "metadata": {"kind": "draft"},
        }
        with patch("app.services.capabilities.create_draft_preview", return_value=fake_preview):
            payload = preview_capability_action(
                db=None,
                settings=settings,
                llm=None,
                wiki=None,
                tools=None,
                action_id="draft.prepare",
                request_payload={
                    "question": "整理成条目",
                    "answer": "答案",
                    "source_titles": ["Theory:TNSA"],
                },
            )

        self.assertEqual(payload["status"], "preview_ready")
        self.assertEqual(payload["preview_kind"], "draft")
        self.assertEqual(payload["preview"]["preview_id"], "draft-1")

    def test_commit_action_requires_confirmation_for_write(self) -> None:
        settings = _settings()

        with patch("app.services.capabilities.commit_write_preview", return_value={"status": "ok", "page_title": "术语条目/TNSA"}):
            payload = commit_capability_action(
                db=None,
                settings=settings,
                wiki=None,
                action_id="write.commit",
                request_payload={"preview_id": "write-1"},
                preview_loader=lambda _db, preview_id: type("Preview", (), {"id": preview_id})(),
            )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["result_kind"], "write")


if __name__ == "__main__":
    unittest.main()
