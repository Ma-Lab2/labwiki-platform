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
    wiki_api_path: str
    wiki_index_path: str
    wiki_user: str
    wiki_password: str | None
    wiki_verify_tls: bool
    draft_prefix: str
    zotero_snapshot_dir: str
    llm_backend: str
    openai_base_url: str | None
    openai_api_key: str | None
    openai_model: str
    simadvisor_executor_path: str
    simadvisor_default_model: str
    simadvisor_fallback_model: str
    simadvisor_review_model: str
    simadvisor_timeout: int
    embedding_model: str | None
    embedding_dimensions: int
    confidence_threshold: float
    loop_max_steps: int
    loop_max_external: int
    reindex_batch_size: int
    enable_web_search: bool
    tps_base_url: str
    rcf_base_url: str
    cors_allowed_origins: list[str]

    @property
    def wiki_api_url(self) -> str:
        return f"{self.wiki_url.rstrip('/')}{self.wiki_api_path}"


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
        wiki_api_path=os.getenv("ASSISTANT_WIKI_API_PATH", "/api.php"),
        wiki_index_path=os.getenv("ASSISTANT_WIKI_INDEX_PATH", "/index.php"),
        wiki_user=os.getenv("ASSISTANT_WIKI_USER", "admin"),
        wiki_password=wiki_password,
        wiki_verify_tls=_as_bool(os.getenv("ASSISTANT_WIKI_VERIFY_TLS"), False),
        draft_prefix=os.getenv("ASSISTANT_DRAFT_PREFIX", "知识助手草稿"),
        zotero_snapshot_dir=os.getenv("ASSISTANT_ZOTERO_SNAPSHOT_DIR", "/data/zotero"),
        llm_backend=os.getenv("ASSISTANT_LLM_BACKEND", "openai"),
        openai_base_url=os.getenv("ASSISTANT_OPENAI_BASE_URL"),
        openai_api_key=os.getenv("ASSISTANT_OPENAI_API_KEY"),
        openai_model=os.getenv("ASSISTANT_OPENAI_MODEL", "gpt-4.1-mini"),
        simadvisor_executor_path=os.getenv(
            "ASSISTANT_SIMADVISOR_EXECUTOR",
            "/mnt/c/Songtan/Gewu/skills/L2-methodology/sim-advisor/executor.py",
        ),
        simadvisor_default_model=os.getenv(
            "ASSISTANT_SIMADVISOR_DEFAULT_MODEL",
            "claude-sonnet-4-5-20250929-thinking",
        ),
        simadvisor_fallback_model=os.getenv(
            "ASSISTANT_SIMADVISOR_FALLBACK_MODEL",
            "gemini-3.1-pro-preview-all",
        ),
        simadvisor_review_model=os.getenv(
            "ASSISTANT_SIMADVISOR_REVIEW_MODEL",
            "claude-opus-4-6",
        ),
        simadvisor_timeout=int(os.getenv("ASSISTANT_SIMADVISOR_TIMEOUT", "180")),
        embedding_model=os.getenv("ASSISTANT_EMBEDDING_MODEL"),
        embedding_dimensions=int(os.getenv("ASSISTANT_EMBEDDING_DIMENSIONS", "1536")),
        confidence_threshold=float(os.getenv("ASSISTANT_CONFIDENCE_THRESHOLD", "0.72")),
        loop_max_steps=int(os.getenv("ASSISTANT_LOOP_MAX_STEPS", "8")),
        loop_max_external=int(os.getenv("ASSISTANT_LOOP_MAX_EXTERNAL", "3")),
        reindex_batch_size=int(os.getenv("ASSISTANT_REINDEX_BATCH_SIZE", "50")),
        enable_web_search=_as_bool(os.getenv("ASSISTANT_ENABLE_WEB_SEARCH"), True),
        tps_base_url=os.getenv("ASSISTANT_TPS_BASE_URL", "http://tps_web:8000"),
        rcf_base_url=os.getenv("ASSISTANT_RCF_BASE_URL", "http://rcf_backend:8000/api/v1"),
        cors_allowed_origins=[origin.strip() for origin in raw_origins.split(",") if origin.strip()],
    )
