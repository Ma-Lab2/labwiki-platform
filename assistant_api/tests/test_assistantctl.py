from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from app import assistantctl


class AssistantCtlTests(unittest.TestCase):
    @patch("app.assistantctl._request_json", return_value={"answer": "ok"})
    def test_ask_defaults_to_product_base_url(self, request_json) -> None:
        with redirect_stdout(io.StringIO()):
            exit_code = assistantctl.main(["ask", "什么是 TNSA？"])

        self.assertEqual(exit_code, 0)
        request_json.assert_called_once()
        method, url, payload = request_json.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(url, "http://localhost:8443/tools/assistant/api/chat")
        self.assertEqual(payload["mode"], "qa")
        self.assertEqual(payload["question"], "什么是 TNSA？")

    @patch("app.assistantctl._request_json", return_value={"draft_preview": {"title": "术语条目/TNSA"}})
    def test_draft_command_uses_draft_mode(self, request_json) -> None:
        with redirect_stdout(io.StringIO()):
            exit_code = assistantctl.main(["draft", "把当前页整理成词条草案", "--context-page", "Theory:TNSA"])

        self.assertEqual(exit_code, 0)
        request_json.assert_called_once()
        method, url, payload = request_json.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(url, "http://localhost:8443/tools/assistant/api/chat")
        self.assertEqual(payload["mode"], "draft")
        self.assertEqual(payload["detail_level"], "intro")
        self.assertEqual(payload["context_pages"], ["Theory:TNSA"])
        self.assertEqual(payload["question"], "把当前页整理成词条草案")

    @patch("app.assistantctl.urllib.request.build_opener")
    def test_request_json_bypasses_environment_proxies(self, build_opener) -> None:
        response = Mock()
        response.read.return_value = json.dumps({"answer": "ok"}).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=None)

        opener = Mock()
        opener.open.return_value = response
        build_opener.return_value = opener

        payload = assistantctl._request_json("GET", "http://localhost:8443/tools/assistant/api/health")

        self.assertEqual(payload, {"answer": "ok"})
        build_opener.assert_called_once()
        proxy_handler = build_opener.call_args.args[0]
        self.assertIsInstance(proxy_handler, assistantctl.urllib.request.ProxyHandler)
        self.assertEqual(proxy_handler.proxies, {})
        opener.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
