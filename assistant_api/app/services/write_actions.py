from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ..clients.wiki import MediaWikiClient
from ..config import Settings
from ..models import DraftPreview
from ..providers.base import PromptEnvelope
from .audit import log_audit
from .drafts import save_draft_preview
from .intent import is_page_structuring_request, is_write_action_request
from .llm import LLMClient


WRITE_ACTION_CONFIG: dict[str, dict[str, Any]] = {
    "create_term_entry": {
        "prefix": "术语条目/",
        "template": "术语条目",
        "operation": "upsert",
        "required_fields": ["中文名", "摘要"],
        "field_order": ["中文名", "英文名", "缩写", "摘要", "别名", "关联页面", "来源"],
    },
    "create_device_entry": {
        "prefix": "设备条目/",
        "template": "设备条目",
        "operation": "upsert",
        "required_fields": ["设备名称", "用途"],
        "field_order": ["设备名称", "系统归属", "关键参数", "用途", "运行页", "来源"],
    },
    "create_diagnostic_entry": {
        "prefix": "诊断条目/",
        "template": "诊断条目",
        "operation": "upsert",
        "required_fields": ["诊断名称", "测量对象", "主要输出"],
        "field_order": ["诊断名称", "测量对象", "主要输出", "易错点", "工具入口", "来源"],
    },
    "create_literature_guide": {
        "prefix": "文献导读/",
        "template": "文献导读",
        "operation": "upsert",
        "required_fields": ["标题", "摘要"],
        "field_order": ["标题", "作者", "年份", "DOI", "摘要", "相关页面", "来源"],
    },
    "create_or_update_shot_record": {
        "prefix": "Shot:",
        "template": "Shot记录",
        "operation": "upsert",
        "required_fields": ["Shot编号", "日期", "Run", "实验目标"],
        "field_order": [
            "Shot编号", "日期", "Run", "时间", "实验目标", "页面状态", "能量", "脉宽", "对比度测量", "聚焦条件",
            "波前状态", "靶类型", "靶厚编号", "靶位置信息", "TPS", "TPS工具入口", "TPS参数快照", "TPS结果图",
            "RCF", "RCF工具入口", "RCF参数快照", "RCF结果截图", "真空", "控制平台日志编号", "主要观测",
            "候选机制判断", "对应理论页", "判断依据", "原始数据主目录", "处理结果文件", "负责人", "截止日期",
            "项目页", "周实验日志", "会议复盘", "补充备注",
        ],
    },
    "append_weekly_shot_log": {
        "prefix": "Shot:",
        "template": None,
        "operation": "append",
        "required_fields": ["目标页面", "区块", "追加内容"],
        "allowed_sections": ["Shot 列表", "本周结果", "共性问题", "下周动作"],
    },
    "update_managed_page_section": {
        "prefix": "",
        "template": None,
        "operation": "replace_section_body",
        "required_fields": ["目标页面", "区块", "内容"],
    },
}

WEEKLY_LOG_SKELETON = """= {title} =

* 周次：
* 值班：
* 目标：

== Shot 列表 ==

== 本周结果 ==

== 共性问题 ==

== 下周动作 ==
"""

MANAGED_PAGE_SECTION_CONFIG: dict[str, dict[str, Any]] = {
    "Shot:Shot日志入口": {
        "marker": "PRIVATE_SHOT_INDEX",
        "allowed_sections": ["使用规则", "当前索引", "维护规则"],
    },
    "Shot:周实验日志": {
        "marker": "PRIVATE_SHOT_WEEKLY_LOG",
        "allowed_sections": ["本周条目", "本周总结"],
    },
    "Shot:表单新建": {
        "marker": "PRIVATE_SHOT_FORM_ENTRY",
        "allowed_sections": ["使用规则", "相关页面"],
    },
    "Meeting:会议入口": {
        "marker": "PRIVATE_MEETING_INDEX",
        "allowed_sections": ["当前入口", "说明"],
    },
    "FAQ:常见问题入口": {
        "marker": "PRIVATE_FAQ_INDEX",
        "allowed_sections": ["当前建议收录", "使用规则"],
    },
    "Project:项目总览": {
        "marker": "PRIVATE_PROJECT_INDEX",
        "allowed_sections": ["当前入口", "使用规则"],
    },
}



def infer_write_action_type(question: str) -> str | None:
    lowered = question.lower()
    if "周实验日志" in question or "周日志" in question:
        return "append_weekly_shot_log"
    if "shot:" in lowered or "shot记录" in question or "shot 页面" in question or "打靶记录" in question:
        return "create_or_update_shot_record"
    if "文献导读" in question:
        return "create_literature_guide"
    if "设备条目" in question or "设备词条" in question or ("设备" in question and "词条" in question):
        return "create_device_entry"
    if "术语条目" in question or "术语词条" in question or ("术语" in question or "词条" in question):
        return "create_term_entry"
    if "诊断条目" in question or "诊断页" in question or "诊断词条" in question:
        return "create_diagnostic_entry"
    if "设备" in question:
        return "create_device_entry"
    if "术语" in question or "词条" in question:
        return "create_term_entry"
    if "诊断" in question:
        return "create_diagnostic_entry"
    return None


def _extract_section_body(existing_text: str, section: str) -> str:
    pattern = re.compile(rf"(?s)^==\s*{re.escape(section)}\s*==\s*\n(.*?)(?=^==\s|\Z)", re.MULTILINE)
    match = pattern.search(existing_text)
    if not match:
        raise ValueError(f"无法定位区块：{section}")
    return match.group(1).strip()


def _replace_section_body(existing_text: str, section: str, new_body: str) -> str:
    pattern = re.compile(rf"(?s)^(==\s*{re.escape(section)}\s*==\s*\n)(.*?)(?=^==\s|\Z)", re.MULTILINE)
    match = pattern.search(existing_text)
    if not match:
        raise ValueError(f"无法定位区块：{section}")
    replacement = match.group(1) + new_body.strip() + "\n\n"
    return existing_text[:match.start()] + replacement + existing_text[match.end():]


def _normalize_section_lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).rstrip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [line.rstrip() for line in value.splitlines() if line.strip()]
    return []


def _normalize_managed_section_append_line(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    bullet_match = re.match(r"^(\*|-|\d+\.)\s+", raw)
    bullet = bullet_match.group(1) if bullet_match else "*"
    content = raw[bullet_match.end():].strip() if bullet_match else raw
    for _ in range(4):
        updated = re.sub(
            r"^(?:请\s*)?(?:编辑一下|编辑|修改一下|修改|更新一下|更新)\s*(?:使用规则(?:区域|区块)?|当前入口|说明|相关页面|本周总结|本周条目|当前索引|维护规则)?\s*[:：]\s*",
            "",
            content,
        ).strip()
        updated = re.sub(
            r"^(?:请\s*)?(?:加一条|补一条|新增一条|新增|加入一条规则|加入一条|追加一条|增加一条|添加一条规则|添加一条)\s*[:：]?\s*",
            "",
            updated,
        ).strip()
        updated = re.sub(r"^(?:规则|条目)\s*[:：]\s*", "", updated).strip()
        if updated == content:
            break
        content = updated
    content = content.strip("。；;，, ")
    if not content:
        return ""
    return f"{bullet} {content}"


def _is_managed_section_meta_line(value: str) -> bool:
    content = re.sub(r"^(\*|-|\d+\.)\s+", "", str(value or "").strip()).strip()
    if not content:
        return True
    meta_prefixes = (
        "已完成",
        "已按当前页面内容更新",
        "可直接保留",
        "若你希望",
        "如果你",
        "说明",
        "证据边界",
        "当前页面内容里已经出现了这条规则",
        "无法进一步确认",
        "建议可改为",
        "可整理后的",
        "现有证据显示",
        "wikitext",
        "wiki",
        "文本",
        "复制",
    )
    return any(content.startswith(prefix) for prefix in meta_prefixes)


def _clean_managed_section_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        normalized = _normalize_managed_section_append_line(line)
        if not normalized or _is_managed_section_meta_line(normalized):
            continue
        if normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def _is_append_like_request(question: str) -> bool:
    hints = ["加一条", "新增", "补一条", "补充", "加入", "追加", "增加"]
    return any(hint in question for hint in hints)


def _is_delete_like_request(question: str) -> bool:
    hints = ["删掉", "删除", "去掉", "移除", "取消这条", "去除"]
    return any(hint in question for hint in hints)


def _is_replace_like_request(question: str) -> bool:
    hints = ["改成", "改为", "改写", "替换成", "改写成", "重写成", "更正式的写法", "改一下措辞", "改得更正式"]
    return any(hint in question for hint in hints)


def _extract_managed_section_append_lines(question: str) -> list[str]:
    candidate = ""
    for pattern in (
        r"[:：]\s*([^\n]+?)\s*$",
        r"(?:加一条|补一条|新增一条|新增|加入一条规则|加入一条|追加一条|增加一条)([^\n]+?)\s*$",
    ):
        match = re.search(pattern, question)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                break
    if not candidate:
        return []
    normalized = _normalize_managed_section_append_line(candidate)
    return [normalized] if normalized else []


def _extract_managed_section_delete_lines(question: str) -> list[str]:
    candidate = ""
    for pattern in (
        r"[:：]\s*([^\n]+?)\s*$",
        r"(?:删掉|删除|去掉|移除)\s*(?:这条规则|这条|该规则|该条)?\s*[:：]?\s*([^\n]+?)\s*$",
    ):
        match = re.search(pattern, question)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                break
    if not candidate:
        return []
    normalized = _normalize_managed_section_append_line(candidate)
    return [normalized] if normalized else []


def _extract_managed_section_replace_payload(question: str, answer: str) -> tuple[list[str], list[str]]:
    new_lines = _extract_managed_section_append_lines(question)
    if not new_lines:
        answer_lines = _clean_managed_section_lines(_normalize_section_lines(answer))
        if answer_lines:
            new_lines = [answer_lines[-1]]
    if not new_lines:
        return [], []

    candidate = ""
    for pattern in (
        r"(?:把|将).*?[“\"]([^”\"]+)[”\"]\s*(?:这条规则|这条|该规则|该条)?\s*(?:改成|改为|改写成|改写|替换成|重写成)",
        r"(?:把|将)\s*“([^”]+)”\s*(?:这条规则|这条|该规则|该条)?\s*(?:改成|改为|改写成|改写|替换成|重写成)",
        r"(?:把|将)\s*\"([^\"]+)\"\s*(?:这条规则|这条|该规则|该条)?\s*(?:改成|改为|改写成|改写|替换成|重写成)",
        r"(?:把|将)\s*(.+?)\s*(?:这条规则|这条|该规则|该条)\s*(?:改成|改为|改写成|改写|替换成|重写成)",
        r"(?:把|将)\s*(.+?)\s*(?:改成|改为|改写成|改写|替换成|重写成)",
    ):
        match = re.search(pattern, question)
        if match:
            candidate = match.group(1).strip()
            if candidate:
                break
    if not candidate:
        return [], new_lines
    candidate = re.sub(
        r"^(?:使用规则(?:区域|区块)?|当前入口|说明|相关页面|本周总结|本周条目|当前索引|维护规则)\s*[里内]\s*",
        "",
        candidate,
    ).strip("“”\"' ")
    normalized_old_line = _normalize_managed_section_append_line(candidate)
    return ([normalized_old_line] if normalized_old_line else []), new_lines


def _infer_managed_page_section(question: str, current_page: str, existing_text: str) -> str:
    config = MANAGED_PAGE_SECTION_CONFIG.get(current_page)
    if not config:
        raise ValueError("当前页面不支持助手区块填充")
    matched = [section for section in config["allowed_sections"] if section in question]
    if len(matched) == 1:
        return matched[0]
    if len(matched) > 1:
        raise ValueError("当前请求命中了多个可编辑区块，请明确要修改哪个区块")
    raise ValueError(
        "当前页支持助手区块填充，但这次没有识别出目标区块；请直接说明区块名，例如“给使用规则加一条”。"
    )


def _build_managed_section_lines(
    *,
    question: str,
    answer: str,
    existing_text: str,
    section: str,
) -> list[str]:
    existing_lines = _clean_managed_section_lines(_normalize_section_lines(_extract_section_body(existing_text, section)))
    if _is_append_like_request(question):
        question_lines = _extract_managed_section_append_lines(question)
        answer_lines = _clean_managed_section_lines(_normalize_section_lines(answer))
        proposed_lines = question_lines or answer_lines
        if not proposed_lines:
            raise ValueError("缺少可写入的区块内容")
        merged = list(existing_lines)
        for line in proposed_lines:
            if line not in merged:
                merged.append(line)
        return merged
    if _is_delete_like_request(question):
        delete_lines = _extract_managed_section_delete_lines(question)
        if not delete_lines:
            raise ValueError("缺少要删除的区块内容")
        return [line for line in existing_lines if line not in delete_lines]
    if _is_replace_like_request(question):
        old_lines, new_lines = _extract_managed_section_replace_payload(question, answer)
        if not new_lines:
            raise ValueError("缺少可写入的区块内容")
        if not old_lines:
            raise ValueError("缺少要替换的原区块内容")
        replaced: list[str] = []
        used_old = set()
        for line in existing_lines:
            if line in old_lines and line not in used_old:
                for new_line in new_lines:
                    if new_line not in replaced:
                        replaced.append(new_line)
                used_old.add(line)
            elif line not in replaced:
                replaced.append(line)
        if not used_old:
            raise ValueError("未在当前区块中找到要替换的内容")
        return replaced
    proposed_lines = _normalize_section_lines(answer)
    if not proposed_lines:
        raise ValueError("缺少可写入的区块内容")
    return proposed_lines


def _sanitize_title(text: str, fallback: str) -> str:
    cleaned = re.sub(r"[\[\]#<>|{}]", " ", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or fallback


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return value


def _extract_page_candidates(question: str, current_page: str | None) -> dict[str, str]:
    candidates: dict[str, str] = {}
    patterns = {
        "shot": r"(Shot:[0-9]{4}-[0-9]{2}-[0-9]{2}-Run[0-9A-Za-z_-]+-Shot[0-9A-Za-z_-]+)",
        "weekly": r"(Shot:[0-9]{4}-W[0-9]{2}\s*周实验日志)",
        "term": r"(术语条目/[^\s，。；;]+)",
        "device": r"(设备条目/[^\s，。；;]+)",
        "diagnostic": r"(诊断条目/[^\s，。；;]+)",
        "literature": r"(文献导读/[^\s，。；;]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, question)
        if match:
            candidates[key] = match.group(1).strip()
    if current_page:
        if current_page.startswith("Shot:") and "周实验日志" in current_page:
            candidates.setdefault("weekly", current_page)
        elif current_page.startswith("Shot:"):
            candidates.setdefault("shot", current_page)
    return candidates


def _extract_primary_name(question: str, action_type: str) -> str:
    patterns: dict[str, list[str]] = {
        "create_term_entry": [
            r"解释\s*([A-Za-z0-9_\-+/\.一-龥]+)",
            r"术语条目[，,:： ]*([A-Za-z0-9_\-+/\.一-龥]+)",
            r"术语[，,:： ]*([A-Za-z0-9_\-+/\.一-龥]+)",
        ],
        "create_device_entry": [
            r"记录\s*([A-Za-z0-9_\-+/\.一-龥]+?)\s*的用途",
            r"设备(?:条目|词条)?[，,:： ]*([A-Za-z0-9_\-+/\.一-龥]+)",
        ],
        "create_diagnostic_entry": [
            r"诊断(?:条目|词条)?[，,:： ]*([A-Za-z0-9_\-+/\.一-龥]+)",
        ],
        "create_literature_guide": [
            r"文献导读[，,:： ]*([A-Za-z0-9_\-+/\.一-龥]+)",
        ],
    }
    for pattern in patterns.get(action_type, []):
        match = re.search(pattern, question)
        if match:
            candidate = match.group(1).strip(" ，,。；;：:()（）")
            if candidate:
                return candidate
    return ""


def _coerce_list(value: Any) -> str:
    if isinstance(value, list):
        return ";".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()


def _render_template_page(template_name: str, field_order: list[str], structured_payload: dict[str, Any]) -> str:
    lines = ["{{" + template_name]
    for field_name in field_order:
        value = structured_payload.get(field_name)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            rendered = _coerce_list(value)
        else:
            rendered = str(value).strip()
        lines.append(f"|{field_name}={rendered}")
    lines.append("}}")
    return "\n".join(lines)


def _append_to_weekly_log(existing_text: str, section: str, append_text: str, title: str) -> str:
    text = existing_text.strip()
    if not text:
        text = WEEKLY_LOG_SKELETON.format(title=title)
    heading = f"== {section} =="
    if heading not in text:
        raise ValueError(f"周日志页缺少区块：{section}")
    block = append_text.strip()
    if not block:
        raise ValueError("追加内容为空")
    if not block.startswith("*") and not block.startswith("-"):
        block = "* " + block
    pattern = re.compile(rf"(?ms)^(==\s*{re.escape(section)}\s*==\s*\n)(.*?)(?=^==\s|$)")
    match = pattern.search(text)
    if not match:
        raise ValueError(f"无法定位周日志区块：{section}")
    prefix, body = match.groups()
    body = body.rstrip()
    new_body = f"{body}\n{block}\n" if body else f"{block}\n"
    return text[:match.start()] + prefix + new_body + text[match.end():]


def _build_write_prompt(
    *,
    question: str,
    answer: str,
    action_type: str,
    current_page: str | None,
    source_titles: list[str],
    conversation_history: list[dict[str, str]],
) -> PromptEnvelope:
    history_text = "\n\n".join(
        f"[{index}] 用户：{item.get('question', '')}\n助手：{item.get('answer', '')[:240]}"
        for index, item in enumerate(conversation_history[-4:], start=1)
    ) or "无"
    config = WRITE_ACTION_CONFIG[action_type]
    if action_type == "append_weekly_shot_log":
        schema_hint = (
            '{"action_type":"append_weekly_shot_log","target_page":"Shot:2026-W11 周实验日志","operation":"append",'
            '"missing_fields":[],"section":"本周结果","structured_payload":{"目标页面":"Shot:2026-W11 周实验日志","区块":"本周结果","追加内容":["* ..."]},'
            '"preview_summary":"..."}'
        )
    else:
        fields = ", ".join(config["field_order"])
        schema_hint = (
            '{"action_type":"' + action_type + '","target_page":"...","operation":"create|update","missing_fields":[],'
            '"structured_payload":{"字段名":"字段值"},"preview_summary":"..."}'
            f"。字段名只能来自：{fields}"
        )

    system_prompt = (
        "你负责把实验室用户的自然语言写入请求整理成可确认执行的结构化 wiki 写操作。"
        "只输出一个 JSON 对象。"
        "如果信息不足，不要编造，必须把缺失项写到 missing_fields。"
        "structured_payload 只能保留和目标模板匹配的字段。"
    )
    user_prompt = (
        f"目标动作：{action_type}\n"
        f"当前页面：{current_page or '无'}\n"
        f"用户请求：{question}\n"
        f"当前回答：{answer or '无'}\n"
        f"来源标题：{', '.join(source_titles) if source_titles else '无'}\n"
        f"最近对话：\n{history_text}\n\n"
        f"请输出 JSON，格式示意：{schema_hint}\n"
        "operation 必须是 create、update 或 append 之一。"
        "target_page 必须是实际页面名。"
        "preview_summary 用中文简短说明将执行什么。"
    )
    return PromptEnvelope(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.1)


def _fallback_write_plan(
    *,
    question: str,
    action_type: str,
    current_page: str | None,
    source_titles: list[str],
) -> dict[str, Any]:
    config = WRITE_ACTION_CONFIG[action_type]
    candidates = _extract_page_candidates(question, current_page)
    payload: dict[str, Any] = {}
    missing_fields: list[str] = []
    target_page: str

    if action_type == "create_term_entry":
        term_name = _extract_primary_name(question, action_type)
        if term_name:
            payload["中文名"] = term_name
        payload["摘要"] = question
        payload["来源"] = source_titles
        if not payload.get("中文名"):
            missing_fields.append("中文名")
        target_page = candidates.get("term") or f"{config['prefix']}{_sanitize_title(payload.get('中文名', ''), '新术语')}"
    elif action_type == "create_device_entry":
        device_name = _extract_primary_name(question, action_type)
        if device_name:
            payload["设备名称"] = device_name
        payload["用途"] = question
        payload["来源"] = source_titles
        if not payload.get("设备名称"):
            missing_fields.append("设备名称")
        target_page = candidates.get("device") or f"{config['prefix']}{_sanitize_title(payload.get('设备名称', ''), '新设备')}"
    elif action_type == "create_diagnostic_entry":
        name = _extract_primary_name(question, action_type)
        if name:
            payload["诊断名称"] = name
        payload["主要输出"] = question
        payload["来源"] = source_titles
        for field_name in ["诊断名称", "测量对象", "主要输出"]:
            if not payload.get(field_name):
                missing_fields.append(field_name)
        target_page = candidates.get("diagnostic") or f"{config['prefix']}{_sanitize_title(payload.get('诊断名称', ''), '新诊断')}"
    elif action_type == "create_literature_guide":
        payload["标题"] = question
        payload["摘要"] = question
        payload["来源"] = source_titles
        target_page = candidates.get("literature") or f"{config['prefix']}{_sanitize_title(question, '新文献导读')}"
    elif action_type == "create_or_update_shot_record":
        shot_page = candidates.get("shot")
        if shot_page:
            payload["Shot编号"] = shot_page
        payload["实验目标"] = question
        payload["来源"] = source_titles
        for field_name in config["required_fields"]:
            if not payload.get(field_name):
                missing_fields.append(field_name)
        target_page = shot_page or "Shot:待补全-RunXX-ShotYYY"
    else:
        weekly_page = candidates.get("weekly")
        payload["目标页面"] = weekly_page or ""
        payload["区块"] = "本周结果"
        payload["追加内容"] = [question]
        if not weekly_page:
            missing_fields.append("目标页面")
        target_page = weekly_page or "Shot:YYYY-Www 周实验日志"

    existing_text = ""
    try:
        existing_text = current_page and target_page == current_page and "" or ""
    except Exception:
        existing_text = ""
    operation = config["operation"]
    if operation == "upsert":
        operation = "create"
    return {
        "action_type": action_type,
        "target_page": target_page,
        "operation": operation,
        "missing_fields": missing_fields,
        "structured_payload": payload,
        "preview_summary": "已根据当前请求生成结构化写入预览。",
        "existing_text": existing_text,
    }


def _load_json_payload(raw: str) -> dict[str, Any]:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = "\n".join(
            line for line in candidate.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    return json.loads(candidate)


def _normalize_write_plan(
    plan: dict[str, Any],
    *,
    question: str,
    action_type: str,
    current_page: str | None,
    source_titles: list[str],
) -> dict[str, Any]:
    config = WRITE_ACTION_CONFIG[action_type]
    candidates = _extract_page_candidates(question, current_page)
    payload = {
        key: _normalize_value(value)
        for key, value in (plan.get("structured_payload") or {}).items()
        if value not in (None, "", [])
    }
    allowed_missing = set(config["required_fields"])
    if action_type == "append_weekly_shot_log":
        allowed_missing.update({"目标页面", "区块", "追加内容"})
    missing_fields = [
        field for field in plan.get("missing_fields", [])
        if isinstance(field, str) and field.strip() in allowed_missing
    ]
    target_page = str(plan.get("target_page") or "").strip()

    if action_type == "append_weekly_shot_log":
        target_page = target_page or str(payload.get("目标页面") or candidates.get("weekly") or "").strip()
        if target_page:
            payload["目标页面"] = target_page
        section = str(plan.get("section") or payload.get("区块") or "").strip()
        if section:
            payload["区块"] = section
        append_text = payload.get("追加内容")
        if isinstance(append_text, str):
            payload["追加内容"] = [append_text]
        elif isinstance(append_text, list):
            payload["追加内容"] = [str(item).strip() for item in append_text if str(item).strip()]
        else:
            payload["追加内容"] = []
        if not payload["追加内容"]:
            payload["追加内容"] = [question]
        if not payload.get("目标页面"):
            missing_fields.append("目标页面")
        if payload.get("区块") not in config["allowed_sections"]:
            if payload.get("区块"):
                missing_fields.append("区块")
            payload["区块"] = payload.get("区块") or "本周结果"
        target_page = payload.get("目标页面") or target_page
    else:
        primary_field = config["field_order"][0]
        if action_type == "create_or_update_shot_record":
            target_page = target_page or str(payload.get("Shot编号") or candidates.get("shot") or "").strip()
            if target_page:
                payload["Shot编号"] = target_page
            if not re.match(r"^Shot:[0-9]{4}-[0-9]{2}-[0-9]{2}-Run[0-9A-Za-z_-]+-Shot[0-9A-Za-z_-]+$", target_page):
                missing_fields.append("Shot编号")
        else:
            base_name = str(payload.get(primary_field) or "").strip()
            generic_names = {"条目", "词条", "设备", "术语", "诊断", "文献导读"}
            if not base_name or base_name in generic_names:
                extracted_name = _extract_primary_name(question, action_type)
                if extracted_name:
                    payload[primary_field] = extracted_name
                    base_name = extracted_name
            if not target_page and base_name:
                target_page = f"{config['prefix']}{_sanitize_title(base_name, '新页面')}"
            elif target_page and not target_page.startswith(config["prefix"]):
                target_page = f"{config['prefix']}{_sanitize_title(base_name or target_page, '新页面')}"
        if payload.get("来源") in (None, "", []):
            payload["来源"] = source_titles
        if action_type == "create_term_entry" and not payload.get("摘要"):
            payload["摘要"] = question.strip()
        if action_type == "create_device_entry":
            if not payload.get("设备名称"):
                payload["设备名称"] = _extract_primary_name(question, action_type)
            if not payload.get("用途"):
                payload["用途"] = question.strip()
        if action_type == "create_diagnostic_entry" and not payload.get("主要输出"):
            payload["主要输出"] = question.strip()
        if action_type == "create_literature_guide" and not payload.get("摘要"):
            payload["摘要"] = question.strip()
        for field_name in config["required_fields"]:
            if not payload.get(field_name):
                missing_fields.append(field_name)

    missing_fields = list(
        dict.fromkeys(
            field for field in missing_fields
            if field and not payload.get(field)
        )
    )
    preview_summary = str(plan.get("preview_summary") or "已生成可确认的写入预览。").strip()
    return {
        "action_type": action_type,
        "target_page": target_page,
        "operation": str(plan.get("operation") or config["operation"]).strip(),
        "missing_fields": missing_fields,
        "structured_payload": payload,
        "preview_summary": preview_summary,
    }


def _render_write_preview_text(action_type: str, target_page: str, structured_payload: dict[str, Any]) -> str:
    config = WRITE_ACTION_CONFIG[action_type]
    if action_type == "append_weekly_shot_log":
        lines = [
            f"目标页面：{target_page}",
            f"区块：{structured_payload.get('区块', '')}",
            "",
            "追加内容：",
        ]
        lines.extend(str(item) for item in structured_payload.get("追加内容", []))
        return "\n".join(lines).strip()
    if action_type == "update_managed_page_section":
        lines = [
            f"目标页面：{target_page}",
            f"区块：{structured_payload.get('区块', '')}",
            "",
        ]
        lines.extend(str(item) for item in structured_payload.get("内容", []))
        return "\n".join(lines).strip()
    return _render_template_page(config["template"], config["field_order"], structured_payload)


def prepare_write_preview(
    settings: Settings,
    llm: LLMClient,
    wiki: MediaWikiClient,
    *,
    question: str,
    answer: str,
    source_titles: list[str],
    current_page: str | None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if current_page in MANAGED_PAGE_SECTION_CONFIG:
        existing_text = wiki.get_page_text(current_page)
        if "LABWIKI_MANAGED_PAGE:" in existing_text:
            section = _infer_managed_page_section(question, current_page, existing_text)
            content_lines = _build_managed_section_lines(
                question=question,
                answer=answer,
                existing_text=existing_text,
                section=section,
            )
            preview_text = _render_write_preview_text(
                "update_managed_page_section",
                current_page,
                {"区块": section, "内容": content_lines},
            )
            return {
                "action_type": "update_managed_page_section",
                "operation": "replace_section_body",
                "target_page": current_page,
                "target_section": section,
                "preview_text": preview_text,
                "structured_payload": {
                    "目标页面": current_page,
                    "区块": section,
                    "内容": content_lines,
                },
                "metadata_json": {
                    "preview_kind": "write_action",
                    "action_type": "update_managed_page_section",
                    "operation": "replace_section_body",
                    "target_section": section,
                    "missing_fields": [],
                    "structured_payload": {
                        "目标页面": current_page,
                        "区块": section,
                        "内容": content_lines,
                    },
                    "preview_summary": f"已生成 {current_page} / {section} 的区块更新预览。",
                    "source_titles": source_titles,
                },
            }
    action_type = infer_write_action_type(question)
    if action_type is None and is_page_structuring_request(question, current_page) and any(
        token in question for token in ["词条", "条目", "术语页", "术语条目"]
    ):
        action_type = "create_term_entry"
    if action_type is None:
        raise ValueError("当前问题不属于受支持的写操作类型")

    if llm.generation_provider.enabled:
        prompt = _build_write_prompt(
            question=question,
            answer=answer,
            action_type=action_type,
            current_page=current_page,
            source_titles=source_titles,
            conversation_history=conversation_history or [],
        )
        try:
            raw = llm.generate_prompt(prompt)
            plan = _load_json_payload(raw)
        except Exception:
            plan = _fallback_write_plan(
                question=question,
                action_type=action_type,
                current_page=current_page,
                source_titles=source_titles,
            )
    else:
        plan = _fallback_write_plan(
            question=question,
            action_type=action_type,
            current_page=current_page,
            source_titles=source_titles,
        )

    normalized = _normalize_write_plan(
        plan,
        question=question,
        action_type=action_type,
        current_page=current_page,
        source_titles=source_titles,
    )
    target_page = normalized["target_page"]
    if not target_page:
        raise ValueError("写操作预览未生成目标页面")
    existing_text = wiki.get_page_text(target_page)
    operation = "append" if action_type == "append_weekly_shot_log" else ("update" if existing_text.strip() else "create")
    preview_text = _render_write_preview_text(action_type, target_page, normalized["structured_payload"])
    return {
        "action_type": action_type,
        "operation": operation,
        "target_page": target_page,
        "target_section": normalized.get("target_section"),
        "preview_text": preview_text,
        "structured_payload": normalized["structured_payload"],
        "metadata_json": {
            "preview_kind": "write_action",
            "action_type": action_type,
            "operation": operation,
            "target_section": normalized.get("target_section"),
            "missing_fields": normalized["missing_fields"],
            "structured_payload": normalized["structured_payload"],
            "preview_summary": normalized["preview_summary"],
            "source_titles": source_titles,
        },
    }


def create_write_preview(
    db: Session,
    settings: Settings,
    llm: LLMClient,
    wiki: MediaWikiClient,
    *,
    session_id: str | None,
    turn_id: str | None,
    question: str,
    answer: str,
    source_titles: list[str],
    current_page: str | None,
    conversation_history: list[dict[str, str]] | None = None,
) -> DraftPreview:
    prepared = prepare_write_preview(
        settings,
        llm,
        wiki,
        question=question,
        answer=answer,
        source_titles=source_titles,
        current_page=current_page,
        conversation_history=conversation_history or [],
    )
    preview = save_draft_preview(
        db,
        session_id=session_id,
        turn_id=turn_id,
        title=prepared["action_type"],
        target_page=prepared["target_page"],
        content=prepared["preview_text"],
        metadata_json=prepared["metadata_json"],
    )
    log_audit(
        db,
        session_id=session_id,
        turn_id=turn_id,
        action_type="write_preview",
        payload={"preview_id": preview.id, "target_page": preview.target_page, "action_type": prepared["action_type"]},
    )
    return preview


def _render_commit_content(action_type: str, preview: DraftPreview) -> str:
    metadata = preview.metadata_json or {}
    payload = metadata.get("structured_payload") or {}
    if action_type == "append_weekly_shot_log":
        existing_text = metadata.get("existing_text") or ""
        return _append_to_weekly_log(existing_text, payload["区块"], "\n".join(payload["追加内容"]), preview.target_page)
    config = WRITE_ACTION_CONFIG[action_type]
    return _render_template_page(config["template"], config["field_order"], payload)


def _validate_and_render_write(
    wiki: MediaWikiClient,
    *,
    target_page: str,
    metadata: dict[str, Any],
) -> tuple[str, str]:
    missing_fields = metadata.get("missing_fields") or []
    if missing_fields:
        raise ValueError(f"仍有缺失字段，不能执行写入：{', '.join(missing_fields)}")

    action_type = str(metadata.get("action_type") or "")
    if action_type not in WRITE_ACTION_CONFIG:
        raise ValueError(f"不支持的写操作类型：{action_type}")

    if action_type == "append_weekly_shot_log":
        if not re.match(r"^Shot:[0-9]{4}-W[0-9]{2}\s*周实验日志$", target_page):
            raise ValueError("周日志目标页格式不合法")
        payload = metadata.get("structured_payload") or {}
        section = payload.get("区块")
        if section not in WRITE_ACTION_CONFIG[action_type]["allowed_sections"]:
            raise ValueError("周日志写入区块不在白名单内")
        current_text = wiki.get_page_text(target_page)
        rendered = _append_to_weekly_log(current_text, section, "\n".join(payload.get("追加内容", [])), target_page)
        summary = f"Assistant append weekly log section: {section}"
        return rendered, summary
    if action_type == "update_managed_page_section":
        config = MANAGED_PAGE_SECTION_CONFIG.get(target_page)
        if not config:
            raise ValueError("当前页面不在托管页白名单内")
        current_text = wiki.get_page_text(target_page)
        expected_marker = f"LABWIKI_MANAGED_PAGE:{config['marker']}"
        if expected_marker not in current_text:
            raise ValueError("当前页面缺少托管页标记，不能执行区块写入")
        payload = metadata.get("structured_payload") or {}
        section = str(metadata.get("target_section") or payload.get("区块") or "").strip()
        if section not in config["allowed_sections"]:
            raise ValueError("目标区块不在当前托管页白名单内")
        content_lines = _normalize_section_lines(payload.get("内容"))
        if not content_lines:
            raise ValueError("区块内容为空")
        rendered = _replace_section_body(current_text, section, "\n".join(content_lines))
        summary = f"Assistant update managed page section: {section}"
        return rendered, summary

    allowed_prefix = WRITE_ACTION_CONFIG[action_type]["prefix"]
    if not target_page.startswith(allowed_prefix):
        raise ValueError("写操作目标页面不在允许范围内")

    payload = metadata.get("structured_payload") or {}
    config = WRITE_ACTION_CONFIG[action_type]
    rendered = _render_template_page(config["template"], config["field_order"], payload)
    summary = f"Assistant {metadata.get('operation', 'update')} structured page"
    return rendered, summary


def commit_prepared_write(
    db: Session,
    wiki: MediaWikiClient,
    *,
    target_page: str,
    metadata: dict[str, Any],
    session_id: str | None = None,
    turn_id: str | None = None,
) -> dict[str, Any]:
    rendered, summary = _validate_and_render_write(
        wiki,
        target_page=target_page,
        metadata=metadata,
    )
    wiki.edit_page(target_page, rendered, summary)
    result = {
        "status": "ok",
        "page_title": target_page,
        "operation": metadata.get("operation"),
        "action_type": metadata.get("action_type"),
        "target_section": metadata.get("target_section"),
        "detail": "write committed",
    }
    log_audit(
        db,
        session_id=session_id,
        turn_id=turn_id,
        action_type="write_commit",
        payload=result,
    )
    return result


def commit_write_preview(
    db: Session,
    wiki: MediaWikiClient,
    *,
    preview: DraftPreview,
) -> dict[str, Any]:
    metadata = preview.metadata_json or {}
    if metadata.get("preview_kind") != "write_action":
        raise ValueError("该预览不是写操作预览")
    result = commit_prepared_write(
        db,
        wiki,
        target_page=preview.target_page,
        metadata=metadata,
        session_id=preview.session_id,
        turn_id=preview.turn_id,
    )
    result["preview_id"] = preview.id
    return result
