"""
PyTPS Web - FastAPI backend entry point.
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import files, settings, analysis, export
from backend.ws.handler import WebSocketManager
from backend.services.session import SessionManager
from backend.core.TSettings import TPSinit
from backend.config import DATA_DIR, SESSION_MAX_AGE

# Load defaults
_default_params = TPSinit(os.path.join(DATA_DIR, "PyTPS_init.ini"))

# Session & WebSocket managers
session_manager = SessionManager(_default_params)
ws_manager = WebSocketManager(session_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[PyTPS Web] Server starting...")
    yield
    print("[PyTPS Web] Server shutting down...")


app = FastAPI(
    title="PyTPS Web",
    description="Thomson Parabola Spectrometer Web Analysis",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for dev (Vite dev server on :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(files.router)
app.include_router(settings.router)
app.include_router(analysis.router)
app.include_router(export.router)


# WebSocket endpoint
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await ws_manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_json()
            await ws_manager.handle_message(websocket, session_id, data)
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)


# Health check
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "sessions": session_manager.active_count(),
    }


# Serve frontend static files (production mode)
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
