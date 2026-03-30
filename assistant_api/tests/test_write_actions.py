from __future__ import annotations

import unittest

from app.services.write_actions import commit_prepared_write, prepare_write_preview


class _DisabledGenerationProvider:
    enabled = False


class _FakeLLM:
    def __init__(self) -> None:
        self.generation_provider = _DisabledGenerationProvider()


class _FakeDB:
    def add(self, _item: object) -> None:
        return


class _FakeWiki:
    def __init__(self, pages: dict[str, str] | None = None) -> None:
        self.pages = pages or {}
        self.edits: list[tuple[str, str, str]] = []

    def get_page_text(self, title: str) -> str:
        return self.pages.get(title, "")

    def edit_page(self, title: str, text: str, summary: str) -> dict[str, str]:
        self.pages[title] = text
        self.edits.append((title, text, summary))
        return {"result": "Success", "title": title}


class WritePreviewTests(unittest.TestCase):
    def test_page_structuring_request_degrades_to_term_entry_preview(self) -> None:
        preview = prepare_write_preview(
            settings=None,  # unused in current implementation
            llm=_FakeLLM(),
            wiki=_FakeWiki(),
            question="帮我整理这个页面的词条。",
            answer="TNSA 是靶背鞘层加速机制。",
            source_titles=["Theory:TNSA"],
            current_page="Theory:TNSA",
            conversation_history=[],
        )

        self.assertEqual(preview["action_type"], "create_term_entry")
        self.assertTrue(preview["target_page"].startswith("术语条目/"))
        self.assertIn("中文名", preview["metadata_json"]["missing_fields"])

    def test_weekly_log_preview_uses_append_operation(self) -> None:
        preview = prepare_write_preview(
            settings=None,  # unused in current implementation
            llm=_FakeLLM(),
            wiki=_FakeWiki(),
            question="把这个 shot 补进本周周实验日志。",
            answer="Shot 结果显示质子截止能量提升。",
            source_titles=["Shot:2026-03-20-Run01-Shot001"],
            current_page="Shot:2026-W11 周实验日志",
            conversation_history=[],
        )

        self.assertEqual(preview["action_type"], "append_weekly_shot_log")
        self.assertEqual(preview["operation"], "append")

    def test_managed_page_preview_targets_named_section(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页

== 当前索引 ==
* [[Shot:2026-W11 周实验日志]]
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="给使用规则加一条：必须备注原日志存放在实验室哪个电脑哪个文件夹位置。",
            answer="* 每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径",
            source_titles=["Shot:Shot日志入口"],
            current_page="Shot:Shot日志入口",
            conversation_history=[],
        )

        self.assertEqual(preview["action_type"], "update_managed_page_section")
        self.assertEqual(preview["target_page"], "Shot:Shot日志入口")
        self.assertEqual(preview["metadata_json"]["target_section"], "使用规则")
        self.assertIn("必须备注原日志存放在实验室哪个电脑哪个文件夹位置", preview["preview_text"])

    def test_managed_page_preview_extracts_appended_line_from_question_when_answer_is_empty(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页

== 当前索引 ==
* [[Shot:2026-W11 周实验日志]]
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="给使用规则加一条：每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径。",
            answer="",
            source_titles=["Shot:Shot日志入口"],
            current_page="Shot:Shot日志入口",
            conversation_history=[],
        )

        content_lines = preview["structured_payload"]["内容"]
        self.assertEqual(
            content_lines,
            [
                "* 每轮实验 / 每个 shot 一页",
                "* 每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径",
            ],
        )

    def test_managed_page_preview_preserves_existing_lines_when_appending(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页
* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`
* 打靶后立刻创建或补全页面

== 必填页面 ==
* [[Shot:表单新建]]
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="编辑一下使用规则区域：加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置",
            answer="* 加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置",
            source_titles=["Shot:Shot日志入口"],
            current_page="Shot:Shot日志入口",
            conversation_history=[],
        )

        self.assertEqual(
            preview["structured_payload"]["内容"],
            [
                "* 每轮实验 / 每个 shot 一页",
                "* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`",
                "* 打靶后立刻创建或补全页面",
                "* 必须备注原实验记录excel的实际电脑ID及文件夹位置",
            ],
        )

    def test_managed_page_preview_strips_instruction_prefix_from_append_question(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页

== 当前索引 ==
* [[Shot:2026-W11 周实验日志]]
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="编辑一下使用规则区域：加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置",
            answer="",
            source_titles=["Shot:Shot日志入口"],
            current_page="Shot:Shot日志入口",
            conversation_history=[],
        )

        self.assertEqual(
            preview["structured_payload"]["内容"],
            [
                "* 每轮实验 / 每个 shot 一页",
                "* 必须备注原实验记录excel的实际电脑ID及文件夹位置",
            ],
        )

    def test_managed_page_preview_cleans_existing_pollution_and_answer_meta(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页
* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`
* 打靶后立刻创建或补全页面
* 加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置
* 已完成：`使用规则` 区域已包含这条规则：
* 必须备注原实验记录excel的实际电脑ID及文件夹位置
* 可直接保留为正式规则

== 必填页面 ==
* [[Shot:表单新建]]
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="编辑一下使用规则区域：加入一条规则：必须备注原实验记录excel的实际电脑ID及文件夹位置",
            answer="""* 已完成：`使用规则` 区域已包含这条规则：
* 必须备注原实验记录excel的实际电脑ID及文件夹位置
* 可直接保留为正式规则
* 若你希望我进一步帮你润色成更规范的表述，建议可改为：
* 必须备注原实验记录 Excel 所在电脑的实际电脑 ID 及文件夹位置""",
            source_titles=["Shot:Shot日志入口"],
            current_page="Shot:Shot日志入口",
            conversation_history=[],
        )

        self.assertEqual(
            preview["structured_payload"]["内容"],
            [
                "* 每轮实验 / 每个 shot 一页",
                "* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`",
                "* 打靶后立刻创建或补全页面",
                "* 必须备注原实验记录excel的实际电脑ID及文件夹位置",
            ],
        )

    def test_managed_page_preview_deletes_requested_rule_without_using_answer_explanation(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页
* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`
* 打靶后立刻创建或补全页面
* 必须备注原实验记录excel的实际电脑ID及文件夹位置

== 必填页面 ==
* [[Shot:表单新建]]
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="把刚加的这条使用规则删掉：必须备注原实验记录excel的实际电脑ID及文件夹位置",
            answer="""可以删除。基于当前页证据，需删掉的是 **Shot:Shot日志入口** 中“使用规则”下这条：
- 必须备注原实验记录excel的实际电脑ID及文件夹位置
建议修改后该段为：
```wiki
== 使用规则 ==
* 每轮实验 / 每个 shot 一页
* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`
* 打靶后立刻创建或补全页面
```""",
            source_titles=["Shot:Shot日志入口"],
            current_page="Shot:Shot日志入口",
            conversation_history=[],
        )

        self.assertEqual(
            preview["structured_payload"]["内容"],
            [
                "* 每轮实验 / 每个 shot 一页",
                "* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`",
                "* 打靶后立刻创建或补全页面",
            ],
        )

    def test_managed_page_preview_replaces_requested_rule_with_normalized_line(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页
* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`
* 打靶后立刻创建或补全页面
* 必须备注原实验记录excel的实际电脑ID及文件夹位置

== 必填页面 ==
* [[Shot:表单新建]]
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="把使用规则里“必须备注原实验记录excel的实际电脑ID及文件夹位置”这条规则改成更正式的写法：每个 Shot 页面必须备注原实验记录 Excel 的实际电脑 ID 及文件夹完整路径。",
            answer="""可以改成更正式的写法：
* 每个 Shot 页面必须备注原实验记录 Excel 的实际电脑 ID 及文件夹完整路径。
证据边界：当前页仅能支持这条规则的正式化改写。""",
            source_titles=["Shot:Shot日志入口"],
            current_page="Shot:Shot日志入口",
            conversation_history=[],
        )

        self.assertEqual(
            preview["structured_payload"]["内容"],
            [
                "* 每轮实验 / 每个 shot 一页",
                "* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`",
                "* 打靶后立刻创建或补全页面",
                "* 每个 Shot 页面必须备注原实验记录 Excel 的实际电脑 ID 及文件夹完整路径",
            ],
        )

    def test_managed_page_preview_replace_requires_explicit_existing_rule(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页
* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`
* 打靶后立刻创建或补全页面

== 必填页面 ==
* [[Shot:表单新建]]
"""
        })

        with self.assertRaisesRegex(ValueError, "未在当前区块中找到要替换的内容"):
            prepare_write_preview(
                settings=None,
                llm=_FakeLLM(),
                wiki=wiki,
                question="把使用规则改成更正式的写法：每个 Shot 页面必须备注原实验记录 Excel 的实际电脑 ID 及文件夹完整路径。",
                answer="* 每个 Shot 页面必须备注原实验记录 Excel 的实际电脑 ID 及文件夹完整路径。",
                source_titles=["Shot:Shot日志入口"],
                current_page="Shot:Shot日志入口",
                conversation_history=[],
            )

    def test_commit_managed_page_preview_replaces_only_target_section(self) -> None:
        wiki = _FakeWiki({
            "Shot:Shot日志入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->
= Shot:Shot日志入口 =

== 使用规则 ==
* 每轮实验 / 每个 shot 一页
* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`

== 当前索引 ==
* [[Shot:2026-W11 周实验日志]]
"""
        })

        result = commit_prepared_write(
            db=_FakeDB(),
            wiki=wiki,
            target_page="Shot:Shot日志入口",
            metadata={
                "preview_kind": "write_action",
                "action_type": "update_managed_page_section",
                "operation": "replace_section_body",
                "target_section": "使用规则",
                "missing_fields": [],
                "structured_payload": {
                    "区块": "使用规则",
                    "内容": [
                        "* 每轮实验 / 每个 shot 一页",
                        "* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`",
                        "* 每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径",
                    ],
                },
            },
            session_id="session-1",
            turn_id="turn-1",
        )

        self.assertEqual(result["action_type"], "update_managed_page_section")
        self.assertEqual(result["target_section"], "使用规则")
        edited_text = wiki.pages["Shot:Shot日志入口"]
        self.assertIn("完整路径", edited_text)
        self.assertIn("== 当前索引 ==", edited_text)
        self.assertEqual(edited_text.count("== 使用规则 =="), 1)

    def test_meeting_index_preview_supports_current_entry_section(self) -> None:
        wiki = _FakeWiki({
            "Meeting:会议入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_MEETING_INDEX -->
= Meeting:会议入口 =

== 当前入口 ==
* [[Meeting:实验复盘模板]]
* [[会议纪要]]

== 说明 ==
组会、实验复盘、设备故障复盘都应从这里进入，并回链到相关项目页与 shot 页。
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="给当前入口加一条：[[Meeting:周会速记模板]]。",
            answer="* [[Meeting:周会速记模板]]",
            source_titles=["Meeting:会议入口"],
            current_page="Meeting:会议入口",
            conversation_history=[],
        )

        self.assertEqual(preview["action_type"], "update_managed_page_section")
        self.assertEqual(preview["metadata_json"]["target_section"], "当前入口")
        self.assertIn("Meeting:周会速记模板", preview["preview_text"])

    def test_faq_index_preview_supports_usage_rules_section(self) -> None:
        wiki = _FakeWiki({
            "FAQ:常见问题入口": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_FAQ_INDEX -->
= FAQ:常见问题入口 =

== 当前建议收录 ==
* 激光链常见故障

== 使用规则 ==
* 每个 FAQ 条目都要链接到对应 SOP、设备页或 shot 复盘页
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="给使用规则加一条：每条 FAQ 需要标注最后更新时间。",
            answer="* 每条 FAQ 需要标注最后更新时间",
            source_titles=["FAQ:常见问题入口"],
            current_page="FAQ:常见问题入口",
            conversation_history=[],
        )

        self.assertEqual(preview["action_type"], "update_managed_page_section")
        self.assertEqual(preview["metadata_json"]["target_section"], "使用规则")
        self.assertIn("最后更新时间", preview["preview_text"])

    def test_project_index_preview_supports_current_entry_section(self) -> None:
        wiki = _FakeWiki({
            "Project:项目总览": """<!-- LABWIKI_MANAGED_PAGE:PRIVATE_PROJECT_INDEX -->
= Project:项目总览 =

== 当前入口 ==
* [[Project:项目模板]]
* [[Project:激光质子加速]]

== 使用规则 ==
* 每个项目页都要链接相关设备、理论、SOP 和典型 shot
"""
        })

        preview = prepare_write_preview(
            settings=None,
            llm=_FakeLLM(),
            wiki=wiki,
            question="给当前入口加一条：[[Project:诊断升级计划]]。",
            answer="* [[Project:诊断升级计划]]",
            source_titles=["Project:项目总览"],
            current_page="Project:项目总览",
            conversation_history=[],
        )

        self.assertEqual(preview["action_type"], "update_managed_page_section")
        self.assertEqual(preview["metadata_json"]["target_section"], "当前入口")
        self.assertIn("Project:诊断升级计划", preview["preview_text"])


if __name__ == "__main__":
    unittest.main()
