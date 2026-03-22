from __future__ import annotations

import unittest

from app.services.intent import is_page_structuring_request, is_write_action_request


class IntentHeuristicsTests(unittest.TestCase):
    def test_current_page_structuring_request_is_not_treated_as_direct_write(self) -> None:
        question = "帮我整理这个页面的词条"
        self.assertTrue(is_page_structuring_request(question, "Theory:TNSA"))
        self.assertFalse(is_write_action_request(question))

    def test_explicit_write_request_requires_write_verbs(self) -> None:
        question = "帮我直接写入一个术语词条，记录 TNSA 的定义"
        self.assertTrue(is_write_action_request(question))
        self.assertFalse(is_page_structuring_request(question, "Theory:TNSA"))


if __name__ == "__main__":
    unittest.main()
