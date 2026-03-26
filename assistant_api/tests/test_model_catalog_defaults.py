from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from app.config import Settings
from app.services.model_catalog import (
    build_model_catalog,
    default_generation_selection,
    resolve_workflow_generation_selection,
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
        "attachments_dir": tempfile.mkdtemp(prefix="assistant-model-defaults-"),
        "enable_web_search": False,
        "tps_base_url": "http://tps",
        "rcf_base_url": "http://rcf",
        "cors_allowed_origins": ["http://127.0.0.1:8443"],
    }
    base.update(overrides)
    return Settings(**base)


class ModelCatalogDefaultSelectionTests(unittest.TestCase):
    def test_claude_is_preferred_when_anthropic_key_exists(self) -> None:
        settings = _settings(generation_provider="openai_compatible")

        selection = default_generation_selection(settings)

        self.assertEqual(selection.provider, "anthropic")
        self.assertEqual(selection.requested_model, "claude-sonnet-4-5-20250929-thinking")

    def test_configured_provider_is_used_when_claude_is_unavailable(self) -> None:
        settings = _settings(
            generation_provider="openai_compatible",
            anthropic_api_key=None,
        )

        selection = default_generation_selection(settings)

        self.assertEqual(selection.provider, "openai_compatible")
        self.assertEqual(selection.requested_model, "gpt-5.4-mini")

    @patch("app.services.model_catalog.fetch_remote_model_ids")
    def test_pdf_ingest_promotes_mini_to_gpt_5_4_when_available(self, fetch_remote_model_ids) -> None:
        settings = _settings(
            generation_provider="openai_compatible",
            anthropic_api_key=None,
        )
        fetch_remote_model_ids.return_value = ["gpt-5.4", "gpt-5.3-codex", "gpt-5.4-mini"]

        selection = resolve_workflow_generation_selection(
            settings,
            requested_provider="openai_compatible",
            requested_model="gpt-5.4-mini",
            session_provider=None,
            session_model=None,
            workflow_hint="pdf_ingest_write",
        )

        self.assertEqual(selection.provider, "openai_compatible")
        self.assertEqual(selection.requested_model, "gpt-5.4")
        self.assertEqual(selection.fallback_chain, ["gpt-5.3-codex", "gpt-5.4-mini"])

    @patch("app.services.model_catalog.fetch_remote_model_ids")
    def test_pdf_ingest_can_fall_back_to_claude_when_gpt_is_missing(self, fetch_remote_model_ids) -> None:
        settings = _settings(
            generation_provider="openai_compatible",
            anthropic_api_key=None,
        )
        fetch_remote_model_ids.return_value = [
            "claude-sonnet-4-5-20250929-thinking",
            "claude-sonnet-4-5-20250929",
            "gpt-5.4-mini",
        ]

        selection = resolve_workflow_generation_selection(
            settings,
            requested_provider="openai_compatible",
            requested_model="gpt-5.4-mini",
            session_provider=None,
            session_model=None,
            workflow_hint="pdf_ingest_write",
        )

        self.assertEqual(selection.provider, "anthropic")
        self.assertEqual(selection.requested_model, "claude-sonnet-4-5-20250929-thinking")

    @patch("app.services.model_catalog.fetch_remote_model_ids")
    def test_pdf_ingest_can_fall_back_to_gemini_when_gpt_and_claude_are_missing(self, fetch_remote_model_ids) -> None:
        settings = _settings(
            generation_provider="openai_compatible",
            anthropic_api_key=None,
        )
        fetch_remote_model_ids.return_value = [
            "gemini-3-flash-preview-thinking",
            "gemini-3-flash-preview",
            "gpt-5.4-mini",
        ]

        selection = resolve_workflow_generation_selection(
            settings,
            requested_provider="openai_compatible",
            requested_model="gpt-5.4-mini",
            session_provider=None,
            session_model=None,
            workflow_hint="pdf_ingest_write",
        )

        self.assertEqual(selection.provider, "openai_compatible")
        self.assertEqual(selection.requested_model, "gemini-3-flash-preview-thinking")

    @patch("app.services.model_catalog.fetch_remote_model_ids")
    def test_pdf_ingest_keeps_non_mini_selection(self, fetch_remote_model_ids) -> None:
        settings = _settings()
        fetch_remote_model_ids.return_value = ["gpt-5.4", "gpt-5.3-codex", "gpt-5.4-mini"]

        selection = resolve_workflow_generation_selection(
            settings,
            requested_provider="anthropic",
            requested_model="claude-sonnet-4-5-20250929-thinking",
            session_provider=None,
            session_model=None,
            workflow_hint="pdf_ingest_write",
        )

        self.assertEqual(selection.provider, "anthropic")
        self.assertEqual(selection.requested_model, "claude-sonnet-4-5-20250929-thinking")

    @patch("app.services.model_catalog.fetch_remote_model_ids")
    def test_featured_gpt_catalog_prefers_full_models_before_mini(self, fetch_remote_model_ids) -> None:
        settings = _settings(
            generation_provider="openai_compatible",
            anthropic_api_key=None,
        )
        fetch_remote_model_ids.return_value = ["gpt-5.3-codex", "gpt-5.4", "gpt-5.4-mini"]

        payload = build_model_catalog(settings)
        gpt_group = next(group for group in payload["groups"] if group["id"] == "gpt")

        self.assertEqual(
            [item["id"] for item in gpt_group["items"]],
            ["gpt-5.4", "gpt-5.3-codex", "gpt-5.4-mini"],
        )


if __name__ == "__main__":
    unittest.main()
