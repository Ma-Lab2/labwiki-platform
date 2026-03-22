from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_secret(path: str | None) -> str | None:
    if not path:
        return None
    if not os.path.exists(path):
        return None
    return open(path, "r", encoding="utf-8").read().strip()


@dataclass(frozen=True)
class Settings:
    database_url: str
    postgres_password: str | None
    wiki_url: str
    wiki_api_base_url: str | None
    wiki_api_host_header: str | None
    wiki_api_path: str
    wiki_index_path: str
    wiki_user: str
    wiki_password: str | None
    wiki_verify_tls: bool
    draft_prefix: str
    enable_zotero: bool
    zotero_snapshot_dir: str
    generation_provider: str
    anthropic_base_url: str
    anthropic_api_key: str | None
    anthropic_model: str
    anthropic_timeout: int
    anthropic_max_tokens: int
    openai_base_url: str
    openai_api_key: str | None
    openai_model: str
    openai_timeout: int
    openai_max_tokens: int
    openai_compatible_base_url: str | None
    openai_compatible_api_key: str | None
    openai_compatible_model: str | None
    openai_compatible_timeout: int
    openai_compatible_max_tokens: int
    embedding_base_url: str | None
    embedding_api_key: str | None
    embedding_model: str | None
    embedding_timeout: int
    embedding_dimensions: int
    vector_store_backend: str
    retrieval_tokenizer_mode: str
    retrieval_normalization_mode: str
    web_search_provider: str
    openai_web_search_model: str | None
    tavily_api_key: str | None
    conversation_history_turns: int
    confidence_threshold: float
    loop_max_steps: int
    loop_max_external: int
    reindex_batch_size: int
    attachments_dir: str
    enable_web_search: bool
    tps_base_url: str
    rcf_base_url: str
    cors_allowed_origins: list[str]

    @property
    def wiki_api_url(self) -> str:
        base_url = self.wiki_api_base_url or self.wiki_url
        return f"{base_url.rstrip('/')}{self.wiki_api_path}"

    @property
    def openai_compatible_generation_base_url(self) -> str:
        return (
            self.openai_compatible_base_url
            or self.embedding_base_url
            or "https://api.gptgod.online/v1"
        )

    @property
    def openai_compatible_generation_api_key(self) -> str | None:
        return (
            self.openai_compatible_api_key
            or self.embedding_api_key
            or self.openai_api_key
            or self.anthropic_api_key
        )

    @property
    def model_catalog_base_url(self) -> str:
        return self.openai_compatible_generation_base_url

    @property
    def model_catalog_api_key(self) -> str | None:
        return self.openai_compatible_generation_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    postgres_password = _read_secret(os.getenv("ASSISTANT_DB_PASSWORD_FILE"))
    wiki_password = _read_secret(os.getenv("ASSISTANT_WIKI_PASSWORD_FILE"))
    raw_origins = os.getenv(
        "ASSISTANT_CORS_ALLOWED_ORIGINS",
        "https://localhost:8443,https://wiki.lab.internal"
    )
    database_url = os.getenv("ASSISTANT_DATABASE_URL")
    if not database_url:
        db_user = os.getenv("ASSISTANT_DB_USER", "labassistant")
        db_name = os.getenv("ASSISTANT_DB_NAME", "labassistant")
        db_host = os.getenv("ASSISTANT_DB_HOST", "assistant_store")
        db_port = os.getenv("ASSISTANT_DB_PORT", "5432")
        db_password = postgres_password or os.getenv("ASSISTANT_DB_PASSWORD", "labassistant")
        database_url = f"postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return Settings(
        database_url=database_url,
        postgres_password=postgres_password,
        wiki_url=os.getenv("ASSISTANT_WIKI_URL", "https://caddy_private"),
        wiki_api_base_url=os.getenv("ASSISTANT_WIKI_API_BASE_URL"),
        wiki_api_host_header=os.getenv("ASSISTANT_WIKI_API_HOST_HEADER"),
        wiki_api_path=os.getenv("ASSISTANT_WIKI_API_PATH", "/api.php"),
        wiki_index_path=os.getenv("ASSISTANT_WIKI_INDEX_PATH", "/index.php"),
        wiki_user=os.getenv("ASSISTANT_WIKI_USER", "admin"),
        wiki_password=wiki_password,
        wiki_verify_tls=_as_bool(os.getenv("ASSISTANT_WIKI_VERIFY_TLS"), False),
        draft_prefix=os.getenv("ASSISTANT_DRAFT_PREFIX", "知识助手草稿"),
        enable_zotero=_as_bool(os.getenv("ASSISTANT_ENABLE_ZOTERO"), False),
        zotero_snapshot_dir=os.getenv("ASSISTANT_ZOTERO_SNAPSHOT_DIR", "/data/zotero"),
        generation_provider=os.getenv("ASSISTANT_GENERATION_PROVIDER", "anthropic").strip().lower(),
        anthropic_base_url=os.getenv("ASSISTANT_ANTHROPIC_BASE_URL", "https://api.gptgod.online"),
        anthropic_api_key=os.getenv("ASSISTANT_ANTHROPIC_API_KEY"),
        anthropic_model=os.getenv(
            "ASSISTANT_ANTHROPIC_MODEL",
            "claude-sonnet-4-5-20250929-thinking",
        ),
        anthropic_timeout=int(os.getenv("ASSISTANT_ANTHROPIC_TIMEOUT", "180")),
        anthropic_max_tokens=int(os.getenv("ASSISTANT_ANTHROPIC_MAX_TOKENS", "2048")),
        openai_base_url=os.getenv("ASSISTANT_OPENAI_BASE_URL", "https://api.openai.com/v1"),
        openai_api_key=os.getenv("ASSISTANT_OPENAI_API_KEY"),
        openai_model=os.getenv("ASSISTANT_OPENAI_MODEL", "gpt-4.1-mini"),
        openai_timeout=int(os.getenv("ASSISTANT_OPENAI_TIMEOUT", "180")),
        openai_max_tokens=int(os.getenv("ASSISTANT_OPENAI_MAX_TOKENS", "2048")),
        openai_compatible_base_url=os.getenv("ASSISTANT_OPENAI_COMPATIBLE_BASE_URL"),
        openai_compatible_api_key=os.getenv("ASSISTANT_OPENAI_COMPATIBLE_API_KEY"),
        openai_compatible_model=os.getenv("ASSISTANT_OPENAI_COMPATIBLE_MODEL"),
        openai_compatible_timeout=int(os.getenv("ASSISTANT_OPENAI_COMPATIBLE_TIMEOUT", "180")),
        openai_compatible_max_tokens=int(os.getenv("ASSISTANT_OPENAI_COMPATIBLE_MAX_TOKENS", "2048")),
        embedding_base_url=os.getenv("ASSISTANT_EMBEDDING_BASE_URL")
        or os.getenv("ASSISTANT_OPENAI_BASE_URL")
        or "https://api.gptgod.online/v1",
        embedding_api_key=os.getenv("ASSISTANT_EMBEDDING_API_KEY")
        or os.getenv("ASSISTANT_OPENAI_API_KEY")
        or os.getenv("ASSISTANT_ANTHROPIC_API_KEY"),
        embedding_model=os.getenv("ASSISTANT_EMBEDDING_MODEL"),
        embedding_timeout=int(os.getenv("ASSISTANT_EMBEDDING_TIMEOUT", "60")),
        embedding_dimensions=int(os.getenv("ASSISTANT_EMBEDDING_DIMENSIONS", "1536")),
        vector_store_backend=os.getenv("ASSISTANT_VECTOR_STORE_BACKEND", "pgvector").strip().lower(),
        retrieval_tokenizer_mode=os.getenv("ASSISTANT_RETRIEVAL_TOKENIZER_MODE", "mixed").strip().lower(),
        retrieval_normalization_mode=os.getenv("ASSISTANT_RETRIEVAL_NORMALIZATION_MODE", "basic").strip().lower(),
        web_search_provider=os.getenv("ASSISTANT_WEB_SEARCH_PROVIDER", "none").strip().lower(),
        openai_web_search_model=os.getenv("ASSISTANT_OPENAI_WEB_SEARCH_MODEL") or os.getenv("ASSISTANT_OPENAI_MODEL"),
        tavily_api_key=os.getenv("ASSISTANT_TAVILY_API_KEY"),
        conversation_history_turns=int(os.getenv("ASSISTANT_CONVERSATION_HISTORY_TURNS", "4")),
        confidence_threshold=float(os.getenv("ASSISTANT_CONFIDENCE_THRESHOLD", "0.72")),
        loop_max_steps=int(os.getenv("ASSISTANT_LOOP_MAX_STEPS", "8")),
        loop_max_external=int(os.getenv("ASSISTANT_LOOP_MAX_EXTERNAL", "3")),
        reindex_batch_size=int(os.getenv("ASSISTANT_REINDEX_BATCH_SIZE", "50")),
        attachments_dir=os.getenv("ASSISTANT_ATTACHMENTS_DIR", "/data/attachments"),
        enable_web_search=_as_bool(os.getenv("ASSISTANT_ENABLE_WEB_SEARCH"), True),
        tps_base_url=os.getenv("ASSISTANT_TPS_BASE_URL", "http://tps_web:8000"),
        rcf_base_url=os.getenv("ASSISTANT_RCF_BASE_URL", "http://rcf_backend:8000/api/v1"),
        cors_allowed_origins=[origin.strip() for origin in raw_origins.split(",") if origin.strip()],
    )
