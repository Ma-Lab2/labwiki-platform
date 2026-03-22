from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import get_settings
from .models import Base


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_database() -> None:
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        pass
    Base.metadata.create_all(bind=engine)
    try:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS generation_provider VARCHAR(64)"))
            connection.execute(text("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS generation_model VARCHAR(255)"))
            connection.execute(text("ALTER TABLE assistant_sessions ADD COLUMN IF NOT EXISTS generation_fallback_model VARCHAR(255)"))
            connection.execute(text("ALTER TABLE assistant_turns ADD COLUMN IF NOT EXISTS action_trace JSON"))
            connection.execute(text("ALTER TABLE assistant_turns ADD COLUMN IF NOT EXISTS draft_preview JSON"))
            connection.execute(text("ALTER TABLE assistant_turns ADD COLUMN IF NOT EXISTS write_preview JSON"))
            connection.execute(text("ALTER TABLE assistant_turns ADD COLUMN IF NOT EXISTS write_result JSON"))
            connection.execute(text("ALTER TABLE assistant_turns ADD COLUMN IF NOT EXISTS model_info JSON"))
    except Exception:
        pass


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
