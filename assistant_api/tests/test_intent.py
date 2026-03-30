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

    def test_managed_page_section_edit_counts_as_write_action(self) -> None:
        question = "给使用规则加一条：每个 Shot 页面必须备注原日志存放位置。"
        self.assertTrue(is_write_action_request(question, "Shot:Shot日志入口"))

    def test_managed_page_section_edit_with_edit_verb_counts_as_write_action(self) -> None:
        question = "编辑一下使用规则区域：加入一条规则：必须备份原实验记录excel的实际电脑ID及文件夹位置"
        self.assertTrue(is_write_action_request(question, "Shot:Shot日志入口"))


if __name__ == "__main__":
    unittest.main()
