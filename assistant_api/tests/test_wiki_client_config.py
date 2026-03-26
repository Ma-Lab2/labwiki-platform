import unittest
from unittest.mock import Mock, patch

from app.clients.wiki import MediaWikiClient
from app.config import Settings


def make_settings(**overrides):
    base = {
        "database_url": "postgresql+psycopg://user:pass@db:5432/app",
        "postgres_password": None,
        "wiki_url": "http://192.168.1.2:8443",
        "wiki_api_base_url": "http://caddy_private",
        "wiki_api_host_header": "192.168.1.2",
        "wiki_api_path": "/api.php",
        "wiki_index_path": "/index.php",
        "wiki_user": "admin",
        "wiki_password": "secret",
        "wiki_verify_tls": False,
        "draft_prefix": "知识助手草稿",
        "attachments_dir": "/data/attachments",
        "enable_zotero": False,
        "zotero_snapshot_dir": "/data/zotero",
        "generation_provider": "openai_compatible",
        "anthropic_base_url": "https://example.invalid",
        "anthropic_api_key": None,
        "anthropic_model": "claude-sonnet-4-5",
        "anthropic_timeout": 180,
        "anthropic_max_tokens": 2048,
        "openai_base_url": "https://api.openai.com/v1",
        "openai_api_key": None,
        "openai_model": "gpt-4.1-mini",
        "openai_timeout": 180,
        "openai_max_tokens": 2048,
        "openai_compatible_base_url": "https://api.gptgod.online/v1",
        "openai_compatible_api_key": "dummy",
        "openai_compatible_model": "gpt-5.4-mini",
        "openai_compatible_timeout": 180,
        "openai_compatible_max_tokens": 2048,
        "embedding_base_url": "https://api.gptgod.online/v1",
        "embedding_api_key": "dummy",
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
        "enable_web_search": True,
        "tps_base_url": "http://tps_web:8000",
        "rcf_base_url": "http://rcf_backend:8000/api/v1",
        "cors_allowed_origins": ["http://192.168.1.2:8443"],
    }
    base.update(overrides)
    return Settings(**base)


class WikiClientConfigTest(unittest.TestCase):
    def test_wiki_api_url_uses_internal_base_override(self):
        settings = make_settings()
        self.assertEqual(settings.wiki_api_url, "http://caddy_private/api.php")

    def test_mediawiki_client_uses_host_header_override_for_api_calls(self):
        settings = make_settings()
        client = MediaWikiClient(settings)
        fake_response = Mock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {"query": {"tokens": {"logintoken": "token"}}}

        with patch.object(client.client, "get", return_value=fake_response) as mock_get:
            client._get({"action": "query"})

        kwargs = mock_get.call_args.kwargs
        self.assertEqual(kwargs["headers"]["Host"], "192.168.1.2")
        self.assertEqual(kwargs["params"]["action"], "query")
        self.assertEqual(kwargs["params"]["format"], "json")

    def test_page_url_still_uses_public_wiki_url(self):
        settings = make_settings()
        client = MediaWikiClient(settings)
        self.assertEqual(
            client.page_url("Theory:TNSA"),
            "http://192.168.1.2:8443/index.php?title=Theory%3ATNSA",
        )

    def test_upload_file_retries_once_when_mediawiki_returns_badtoken(self):
        settings = make_settings()
        client = MediaWikiClient(settings)
        issued_tokens: list[str] = []

        def fake_login():
            token = f"csrf-{len(issued_tokens) + 1}"
            issued_tokens.append(token)
            client.csrf_token = token
            client.logged_in = True

        badtoken_response = Mock()
        badtoken_response.raise_for_status.return_value = None
        badtoken_response.json.return_value = {"error": {"code": "badtoken", "info": "Invalid CSRF token."}}

        success_response = Mock()
        success_response.raise_for_status.return_value = None
        success_response.json.return_value = {"upload": {"result": "Success"}}

        with patch.object(client, "login", side_effect=fake_login) as mock_login, \
                patch.object(client.client, "post", side_effect=[badtoken_response, success_response]) as mock_post:
            payload = client.upload_file("fixture.pdf", b"pdf", "Upload regression fixture", content_type="application/pdf")

        self.assertEqual(payload["upload"]["result"], "Success")
        self.assertEqual(mock_login.call_count, 2)
        self.assertEqual(
            [call.kwargs["data"]["token"] for call in mock_post.call_args_list],
            ["csrf-1", "csrf-2"],
        )

    def test_edit_page_retries_once_when_mediawiki_returns_badtoken(self):
        settings = make_settings()
        client = MediaWikiClient(settings)
        issued_tokens: list[str] = []

        def fake_login():
            token = f"csrf-{len(issued_tokens) + 1}"
            issued_tokens.append(token)
            client.csrf_token = token
            client.logged_in = True

        with patch.object(client, "login", side_effect=fake_login) as mock_login, \
                patch.object(
                    client,
                    "_post",
                    side_effect=[
                        {"error": {"code": "badtoken", "info": "Invalid CSRF token."}},
                        {"edit": {"result": "Success"}},
                    ],
                ) as mock_post:
            payload = client.edit_page("Control:回归测试", "正文", "回归测试")

        self.assertEqual(payload["edit"]["result"], "Success")
        self.assertEqual(mock_login.call_count, 2)
        self.assertEqual(
            [call.args[0]["token"] for call in mock_post.call_args_list],
            ["csrf-1", "csrf-2"],
        )


if __name__ == "__main__":
    unittest.main()
