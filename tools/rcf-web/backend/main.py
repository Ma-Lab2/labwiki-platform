"""
RCF-Web Backend - FastAPI Application Entry Point

RCF Stack Spectrometer Design Tool - Web Version
"""

import os
import sys
import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from api.compute import router as compute_router
from api.materials import router as materials_router
from api.stack import router as stack_router
from api.websocket import router as ws_router
from api.compute import task_cleanup_loop
from services.material_service import load_all_pstar_materials, load_uploaded_materials


def _get_allowed_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load PSTAR materials on startup."""
    cleanup_task = asyncio.create_task(task_cleanup_loop())
    pstar_count = load_all_pstar_materials()
    upload_count = load_uploaded_materials()
    print(f"Loaded {pstar_count} PSTAR materials + {upload_count} uploaded materials at startup")

    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(
    title="RCF-Web API",
    description="RCF Stack Spectrometer Design Tool - Web API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(compute_router, prefix="/api/v1")
app.include_router(materials_router, prefix="/api/v1")
app.include_router(stack_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
