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
        "preview_text": preview_text,
        "structured_payload": normalized["structured_payload"],
        "metadata_json": {
            "preview_kind": "write_action",
            "action_type": action_type,
            "operation": operation,
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
