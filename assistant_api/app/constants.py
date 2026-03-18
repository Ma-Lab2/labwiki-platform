from __future__ import annotations

from enum import Enum


class AssistantMode(str, Enum):
    QA = "qa"
    COMPARE = "compare"
    DRAFT = "draft"


class AssistantDetailLevel(str, Enum):
    INTRO = "intro"
    INTERMEDIATE = "intermediate"
    RESEARCH = "research"


class TaskType(str, Enum):
    CONCEPT = "concept"
    COMPARE = "compare"
    LITERATURE = "literature"
    LEARNING_PATH = "learning_path"
    TOOL_WORKFLOW = "tool_workflow"
    DRAFT = "draft"


class SourceType(str, Enum):
    CARGO = "cargo"
    WIKI = "wiki"
    ZOTERO = "zotero"
    OPENALEX = "openalex"
    TOOL = "tool"
    CONTEXT = "context"


class ToolName(str, Enum):
    TPS = "tps"
    RCF = "rcf"


READ_ONLY_TOOL_ACTIONS: dict[ToolName, set[str]] = {
    ToolName.TPS: {"health", "browse", "list", "solve", "batch", "compare"},
    ToolName.RCF: {"health", "energy-scan", "linear-design", "validate-stack"},
}


STRUCTURED_SOURCE_TYPES = {SourceType.CARGO.value, SourceType.WIKI.value, SourceType.ZOTERO.value}
