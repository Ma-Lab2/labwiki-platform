from __future__ import annotations

import time

from sqlalchemy import select

from .clients.openalex import OpenAlexClient
from .clients.tools import ToolClients
from .clients.wiki import MediaWikiClient
from .config import get_settings
from .db import init_database, session_scope
from .models import Job
from .services.audit import log_audit
from .services.llm import LLMClient
from .services.reindex import reindex_wiki, reindex_zotero


def run_worker_loop(poll_interval: int = 5) -> None:
    settings = get_settings()
    init_database()
    llm = LLMClient(settings)
    wiki = MediaWikiClient(settings)
    OpenAlexClient()
    ToolClients(settings)

    while True:
        with session_scope() as db:
            job = db.execute(
                select(Job).where(Job.status == "pending").order_by(Job.created_at.asc()).limit(1)
            ).scalar_one_or_none()
            if not job:
                time.sleep(poll_interval)
                continue
            job.status = "running"
            db.flush()
            log_audit(db, action_type="job_started", payload={"job_id": job.id, "job_type": job.job_type})
            try:
                if job.job_type == "reindex_wiki":
                    job.result = reindex_wiki(db, settings, llm)
                elif job.job_type == "reindex_zotero":
                    job.result = reindex_zotero(db, settings, llm)
                else:
                    raise RuntimeError(f"Unsupported job type: {job.job_type}")
                job.status = "completed"
                log_audit(
                    db,
                    action_type="job_completed",
                    payload={"job_id": job.id, "job_type": job.job_type, "result": job.result},
                )
            except Exception as error:
                job.status = "failed"
                job.error = str(error)
                log_audit(
                    db,
                    action_type="job_failed",
                    payload={"job_id": job.id, "job_type": job.job_type, "detail": str(error)},
                )
        time.sleep(poll_interval)


if __name__ == "__main__":
    run_worker_loop()
