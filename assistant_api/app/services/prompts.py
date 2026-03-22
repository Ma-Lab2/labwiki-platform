from __future__ import annotations

from typing import Any

from ..constants import TaskType
from ..providers.base import PromptEnvelope


TASK_GUIDANCE = {
    TaskType.CONCEPT.value: "优先直接回答用户问题；先给本组语境结论，再补少量依据，不要退化成教科书泛答。",
    TaskType.COMPARE.value: "必须显式对照至少两个对象，先给核心差异，再说明相同点、差异点和证据来源。",
    TaskType.LITERATURE.value: "优先区分本组已有知识与外部文献观点，不能把文献观点伪装成内部共识。",
    TaskType.LEARNING_PATH.value: "给出适合新人的学习顺序，按页面顺序回答，并用一句话说明每一步为什么看。",
    TaskType.TOOL_WORKFLOW.value: "回答要尽量贴合 TPS/RCF 的具体操作、校验和读谱流程。",
    TaskType.DRAFT.value: "回答应直接产出可整理的草案，不要先解释索引页、模板规则或检索过程。未知字段留空，不要写“待补充”“未知”“无”这类占位值；把缺失字段单独列出。",
    TaskType.WRITE_ACTION.value: "优先完成白名单结构化写入；字段不完整时必须说明缺口并停止，不得编造字段值。",
}

DOMAIN_KEYWORDS = {
    "tps": "Thomson parabola, 离子在线谱仪, 能谱, 轨迹拟合, 解谱",
    "rcf": "RCF stack, radiochromic film, 堆栈设计, 剂量层, 反演",
    "shot": "Shot 记录, 打靶流程, 周报, SOP, 安全检查",
    "laser": "TNSA, RPA, preplasma, contrast, Rayleigh length, 波前, 焦斑",
}

FEW_SHOT_EXAMPLES = {
    TaskType.CONCEPT.value: [
        "问题：什么是 TNSA？\n回答风格：先给一句本组语境定义，再说明它和本组诊断条目、实验条件的关系。",
    ],
    TaskType.COMPARE.value: [
        "问题：比较 TNSA 和 RPA。\n回答风格：分成驱动机制、实验判据、诊断信号、适用条件四段对照。",
    ],
    TaskType.TOOL_WORKFLOW.value: [
        "问题：RCF 堆栈验证怎么做？\n回答风格：按输入、校验、输出、异常处理四步说明。",
    ],
}


def _history_block(history: list[dict[str, str]]) -> str:
    if not history:
        return "无"
    rows = []
    for index, item in enumerate(history[-4:], start=1):
        rows.append(
            f"[{index}] 用户：{item.get('question', '')}\n助手：{item.get('answer', '')[:500]}"
        )
    return "\n\n".join(rows)


def _domain_keywords(question: str) -> str:
    lowered = question.lower()
    matched = [value for key, value in DOMAIN_KEYWORDS.items() if key in lowered or key in question]
    return "；".join(matched) if matched else "无"


def build_answer_prompt(
    *,
    question: str,
    task_type: str,
    detail_level: str,
    mode: str,
    current_page: str | None,
    evidence: list[dict[str, Any]],
    unresolved_gaps: list[str],
    structured_only: bool,
    conversation_history: list[dict[str, str]],
) -> PromptEnvelope:
    evidence_block = "\n\n".join(
        f"[{index + 1}] {item['title']} ({item['source_type']})\n{item.get('snippet', '')}\n{item.get('content', '')[:900]}"
        for index, item in enumerate(evidence[:6])
    ) or "无"
    task_guidance = TASK_GUIDANCE.get(task_type, "回答必须忠于证据。")
    fewshot = "\n\n".join(FEW_SHOT_EXAMPLES.get(task_type, [])) or "无"
    system_prompt = (
        "你是实验室私有 MediaWiki 的知识助手。"
        "回答必须以本组语境为先，显式说明证据边界。"
        "证据不足时必须承认不足，不能编造实验细节或内部结论。"
        "主回答先完成用户任务，不要先汇报检索过程。"
        f"{task_guidance}"
    )
    if structured_only:
        system_prompt += " 用户要求结构化定义时，只能优先使用结构化条目，不要复述索引页或导航页。"
    if current_page and any(token in question for token in ["整理", "梳理", "改写", "写成", "整理成"]) and any(
        token in question for token in ["这个页面", "当前页面", "当前页", "本页", "这页", "词条", "条目", "页面", "记录"]
    ):
        system_prompt += (
            " 当前任务是把当前页面整理成词条/条目草案。"
            "主回答必须直接输出整理结果，而不是解释检索过程、索引页用途或模板规则。"
            "优先使用当前页面证据；索引页和导航页只能作为辅助，不能喧宾夺主。"
            "如果字段不全，先给出一版保守草案，并明确哪些字段待补。"
            " 未知字段留空，不要写“待补充”“未知”“无”这类占位值；把缺失字段单独列成“缺失字段”。"
        )
    user_prompt = (
        f"当前问题：{question}\n"
        f"任务类型：{task_type}\n"
        f"解释层级：{detail_level}\n"
        f"模式：{mode}\n"
        f"当前页面：{current_page or '无'}\n"
        f"对话历史：\n{_history_block(conversation_history)}\n\n"
        f"领域关键词提示：{_domain_keywords(question)}\n"
        f"few-shot 参考：\n{fewshot}\n\n"
        f"证据缺口：{'; '.join(unresolved_gaps) if unresolved_gaps else '无'}\n\n"
        f"已检索证据：\n{evidence_block}\n\n"
        "请输出简洁但有层次的中文回答。优先回答本组上下文，不要把外部网页或论文结论说成本组既定事实。不要把“我检索到/我看到/最像的是”作为开头。"
    )
    return PromptEnvelope(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.2)


def build_draft_prompt(
    *,
    question: str,
    answer: str,
    source_titles: list[str],
    draft_prefix: str,
    conversation_history: list[dict[str, str]],
) -> PromptEnvelope:
    system_prompt = (
        "你负责把知识助手回答整理成 MediaWiki 草稿页。"
        "只输出一个 JSON 对象，字段必须只有 title 和 content。"
        "title 不要带草稿前缀。"
    )
    user_prompt = (
        f"草稿前缀：{draft_prefix}\n"
        f"原始问题：{question}\n"
        f"当前回答：{answer}\n"
        f"来源标题：{', '.join(source_titles) if source_titles else '待补充'}\n"
        f"最近对话历史：\n{_history_block(conversation_history)}\n\n"
        "请给出一个适合课题组私有 wiki 的草稿标题和页面正文。"
    )
    return PromptEnvelope(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.1)


def build_agent_planner_prompt(
    *,
    question: str,
    task_type: str,
    detail_level: str,
    mode: str,
    current_page: str | None,
    conversation_history: list[dict[str, str]],
    steps: list[dict[str, str]],
    evidence: list[dict[str, Any]],
    unresolved_gaps: list[str],
    tool_specs: list[Any],
) -> PromptEnvelope:
    tool_block = "\n".join(
        f"- {item.name}: {item.description}; 输入示意={item.input_schema}"
        for item in tool_specs
    )
    evidence_block = "\n".join(
        f"- {item['title']} [{item['source_type']}] {item.get('snippet', '')[:180]}"
        for item in evidence[:8]
    ) or "无"
    step_block = "\n".join(
        f"- {item['title']} ({item['status']}): {item['detail']}"
        for item in steps[-8:]
    ) or "无"
    system_prompt = (
        "你是实验室私有 wiki 助手的受控 agent planner。"
        "你的职责不是直接写最终回答，而是决定下一步最合适的工具动作。"
        "你必须在给定工具白名单内行动，不能发明不存在的工具。"
        "除非证据已经足够，否则优先补证据再结束。"
        "写操作只能通过 prepare_write_preview / commit_write 在白名单范围内执行。"
        "字段不完整时不能 commit_write。"
        "只输出一个 JSON 对象，字段固定为 thought、action、action_input、stop_reason。"
    )
    if current_page and any(token in question for token in ["整理", "梳理", "改写", "写成", "整理成"]) and any(
        token in question for token in ["这个页面", "当前页面", "当前页", "本页", "这页", "词条", "条目", "页面", "记录"]
    ):
        system_prompt += (
            " 对于把当前页整理成词条/条目/页面的请求，当前页是最高优先级证据。"
            "不要把索引页解释当成最终回答。"
            "如果当前页已经可读，应优先结束到 answer 或 prepare_draft_preview，而不是继续泛化检索。"
        )
    user_prompt = (
        f"问题：{question}\n"
        f"任务类型：{task_type}\n"
        f"解释层级：{detail_level}\n"
        f"模式：{mode}\n"
        f"当前页面：{current_page or '无'}\n"
        f"最近对话：\n{_history_block(conversation_history)}\n\n"
        f"当前步骤：\n{step_block}\n\n"
        f"当前证据：\n{evidence_block}\n\n"
        f"证据缺口：{'; '.join(unresolved_gaps) if unresolved_gaps else '无'}\n\n"
        f"可用工具：\n{tool_block}\n\n"
        "请只返回 JSON，例如："
        '{"thought":"需要先补本地证据","action":"search_local","action_input":{"query":"...","source_types":["cargo","wiki"],"limit":6},"stop_reason":null}'
    )
    return PromptEnvelope(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0, max_tokens=700)
