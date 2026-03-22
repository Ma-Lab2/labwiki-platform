from __future__ import annotations


PAGE_REF_TOKENS = ("这个页面", "当前页面", "当前页", "本页", "这页")
STRUCTURING_TOKENS = ("整理", "梳理", "改写", "写成", "整理成", "归纳成", "总结成")
STRUCTURED_TARGET_TOKENS = ("词条", "条目", "页面", "记录", "术语页", "术语条目", "知识页")
COMPARE_TOKENS = ("对照", "比较", "区别", "差异", "差别", "一致点", "不同点")
LEARNING_PATH_TOKENS = ("学习路径", "先看哪几页", "先读哪些页面", "按什么顺序", "从哪开始", "从哪里开始", "阅读顺序", "串起来")
LEARNING_PATH_HINTS = ("新来的", "新人", "入门", "怎么学")
TOOL_KEYWORDS = ("tps", "rcf")
TOOL_WORKFLOW_TOKENS = ("流程", "操作", "使用", "归档", "判靶", "检查", "解谱", "能谱", "堆栈", "没出谱", "结果图", "参数快照")
PAGE_SUMMARY_TOKENS = ("总结", "概括", "压缩", "提炼", "5句", "五句", "重点")


def is_compare_request(question: str) -> bool:
    return any(token in question for token in COMPARE_TOKENS)


def is_learning_path_request(question: str) -> bool:
    return any(token in question for token in LEARNING_PATH_TOKENS) or (
        any(token in question for token in LEARNING_PATH_HINTS)
        and any(token in question for token in ("先看", "先读", "顺序", "从哪", "页面", "wiki"))
    )


def is_tool_workflow_request(question: str) -> bool:
    lowered = question.lower()
    has_tool = any(token in lowered for token in TOOL_KEYWORDS) or any(token in question for token in ("解谱", "能谱", "堆栈"))
    if not has_tool:
        return False
    if is_learning_path_request(question):
        return False
    return any(token in question for token in TOOL_WORKFLOW_TOKENS)


def is_current_page_request(question: str, current_page: str | None = None) -> bool:
    if any(token in question for token in PAGE_REF_TOKENS):
        return True
    return bool(current_page and any(token in question for token in STRUCTURING_TOKENS + PAGE_SUMMARY_TOKENS))


def is_write_action_request(question: str) -> bool:
    lowered = question.lower()
    if any(token in question for token in ["草稿", "先不要写回", "仅预览"]) or "draft" in lowered:
        return False
    write_tokens = ["新建", "新增", "创建", "添加", "补一条", "补充", "写入", "更新", "追加", "记到", "记录到", "直接写入", "直接创建"]
    targets = ["术语", "词条", "设备", "诊断", "文献导读", "shot", "Shot:", "周实验日志", "周日志", "日志"]
    return any(token in question for token in write_tokens) and any(token in question or token in lowered for token in targets)


def is_page_structuring_request(question: str, current_page: str | None = None) -> bool:
    if current_page and any(token in question for token in STRUCTURING_TOKENS) and any(token in question for token in STRUCTURED_TARGET_TOKENS):
        return True
    return any(token in question for token in PAGE_REF_TOKENS) and any(token in question for token in STRUCTURING_TOKENS) and any(
        token in question for token in STRUCTURED_TARGET_TOKENS
    )


def is_page_summary_request(question: str, current_page: str | None = None) -> bool:
    if not is_current_page_request(question, current_page):
        return False
    return any(token in question for token in PAGE_SUMMARY_TOKENS)
