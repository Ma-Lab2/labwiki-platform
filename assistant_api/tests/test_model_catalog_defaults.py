from __future__ import annotations

import tempfile
import unittest

from app.config import Settings
from app.services.model_catalog import default_generation_selection


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


if __name__ == "__main__":
    unittest.main()
