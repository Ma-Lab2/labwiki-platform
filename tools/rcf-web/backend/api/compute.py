"""
Compute API routes - energy scan and linear design.
"""

import asyncio
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Any

from fastapi import APIRouter, BackgroundTasks

from schemas.compute import (
    EnergyScanRequest, EnergyScanResponse, RCFResult,
    LinearDesignRequest, LinearDesignResponse,
    AsyncTaskResponse
)
from schemas.stack import StackLayer
from services.energy_scan import run_energy_scan
from services.linear_design import run_linear_design

router = APIRouter(prefix="/compute", tags=["compute"])

# In-memory task store for async computations
_tasks: Dict[str, Dict[str, Any]] = {}
_tasks_lock = Lock()

TASK_TTL_RUNNING_SEC = int(os.getenv("TASK_TTL_RUNNING_SEC", "21600"))  # 6h
TASK_TTL_DONE_SEC = int(os.getenv("TASK_TTL_DONE_SEC", "3600"))         # 1h
TASK_CLEANUP_INTERVAL_SEC = int(os.getenv("TASK_CLEANUP_INTERVAL_SEC", "60"))


def _now() -> float:
    return time.time()


def _utc_from_ts(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def get_task_store() -> Dict[str, Dict[str, Any]]:
    """Get the shared task store."""
    return _tasks


def _signal_update(task: Dict[str, Any]):
    """Wake up websocket listeners for this task."""
    event = task.get("update_event")
    loop = task.get("loop")
    if not event or not loop:
        return
    try:
        loop.call_soon_threadsafe(event.set)
    except RuntimeError:
        # Event loop may already be closed during shutdown.
        pass


def create_async_task(loop: asyncio.AbstractEventLoop) -> tuple[str, str, float]:
    """Create and register an async compute task with ws token + ttl."""
    task_id = str(uuid.uuid4())
    ws_token = secrets.token_urlsafe(24)
    now = _now()
    expires_at = now + TASK_TTL_RUNNING_SEC

    task = {
        "status": "running",
        "progress": 0.0,
        "message": "",
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_at,
        "ws_token": ws_token,
        "update_event": asyncio.Event(),
        "loop": loop,
    }

    with _tasks_lock:
        _tasks[task_id] = task

    return task_id, ws_token, expires_at


def _set_task_progress(task_id: str, msg: str, pct: float):
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            return
        task["message"] = msg
        task["progress"] = pct
        task["updated_at"] = _now()
        _signal_update(task)


def _complete_task(task_id: str, result: Dict[str, Any]):
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            return
        now = _now()
        task["status"] = "completed"
        task["result"] = result
        task["progress"] = 100.0
        task["updated_at"] = now
        task["expires_at"] = now + TASK_TTL_DONE_SEC
        _signal_update(task)


def _fail_task(task_id: str, error: str):
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            return
        now = _now()
        task["status"] = "error"
        task["error"] = error
        task["updated_at"] = now
        task["expires_at"] = now + TASK_TTL_DONE_SEC
        _signal_update(task)


def cleanup_expired_tasks() -> int:
    """Remove tasks past expiry. Returns number of removed tasks."""
    now = _now()
    removed = 0

    with _tasks_lock:
        for task_id, task in list(_tasks.items()):
            if task.get("expires_at", 0) <= now:
                del _tasks[task_id]
                removed += 1

    return removed


async def task_cleanup_loop():
    """Background cleanup loop for async task store."""
    while True:
        cleanup_expired_tasks()
        await asyncio.sleep(TASK_CLEANUP_INTERVAL_SEC)


def _layers_to_dicts(layers):
    """Convert StackLayer list to list of dicts."""
    return [
        {
            "material_name": l.material_name,
            "thickness": l.thickness,
            "thickness_type": l.thickness_type,
            "is_detector": l.is_detector,
            "layer_id": l.layer_id,
        }
        for l in layers
    ]


@router.post("/energy-scan", response_model=EnergyScanResponse)
async def energy_scan_sync(request: EnergyScanRequest):
    """Synchronous energy scan (for small stacks, <5s)."""
    layers = _layers_to_dicts(request.layers)
    result = await asyncio.to_thread(
        run_energy_scan,
        layers=layers,
        energy_min=request.energy_min,
        energy_max=request.energy_max,
        energy_step=request.energy_step,
        incidence_angle=request.incidence_angle,
        ion_key=request.ion_key,
    )
    return EnergyScanResponse(
        rcf_results=[RCFResult(**r) for r in result["rcf_results"]],
        res_ene_matrix=result["res_ene_matrix"],
        energy_range=result["energy_range"],
    )


@router.post("/energy-scan/async", response_model=AsyncTaskResponse)
async def energy_scan_async(request: EnergyScanRequest, background_tasks: BackgroundTasks):
    """Async energy scan - returns task_id, use WebSocket for progress."""
    loop = asyncio.get_running_loop()
    task_id, ws_token, expires_ts = create_async_task(loop)

    def _run():
        def progress_cb(msg, pct):
            _set_task_progress(task_id, msg, pct)

        try:
            layers = _layers_to_dicts(request.layers)
            result = run_energy_scan(
                layers=layers,
                energy_min=request.energy_min,
                energy_max=request.energy_max,
                energy_step=request.energy_step,
                incidence_angle=request.incidence_angle,
                ion_key=request.ion_key,
                progress_cb=progress_cb,
            )
            _complete_task(task_id, result)
        except Exception as e:
            _fail_task(task_id, str(e))

    background_tasks.add_task(asyncio.to_thread, _run)
    return AsyncTaskResponse(
        task_id=task_id,
        ws_token=ws_token,
        expires_at=_utc_from_ts(expires_ts),
    )


@router.post("/linear-design", response_model=LinearDesignResponse)
async def linear_design_sync(request: LinearDesignRequest):
    """Synchronous linear design."""
    detectors = _layers_to_dicts(request.detectors)
    result = await asyncio.to_thread(
        run_linear_design,
        detectors=detectors,
        al_thick_1=request.al_thick_1,
        energy_interval=request.energy_interval,
        al_thick_min=request.al_thick_min,
        al_thick_max=request.al_thick_max,
        al_interval=request.al_interval,
        incidence_angle=request.incidence_angle,
    )
    return LinearDesignResponse(
        energy_sequence=result["energy_sequence"],
        al_thickness_sequence=result["al_thickness_sequence"],
        full_stack=[StackLayer(**s) for s in result["full_stack"]],
        messages=result["messages"],
    )


@router.post("/linear-design/async", response_model=AsyncTaskResponse)
async def linear_design_async(request: LinearDesignRequest, background_tasks: BackgroundTasks):
    """Async linear design - returns task_id."""
    loop = asyncio.get_running_loop()
    task_id, ws_token, expires_ts = create_async_task(loop)

    def _run():
        def progress_cb(msg, pct):
            _set_task_progress(task_id, msg, pct)

        try:
            detectors = _layers_to_dicts(request.detectors)
            result = run_linear_design(
                detectors=detectors,
                al_thick_1=request.al_thick_1,
                energy_interval=request.energy_interval,
                al_thick_min=request.al_thick_min,
                al_thick_max=request.al_thick_max,
                al_interval=request.al_interval,
                incidence_angle=request.incidence_angle,
                progress_cb=progress_cb,
            )
            _complete_task(task_id, result)
        except Exception as e:
            _fail_task(task_id, str(e))

    background_tasks.add_task(asyncio.to_thread, _run)
    return AsyncTaskResponse(
        task_id=task_id,
        ws_token=ws_token,
        expires_at=_utc_from_ts(expires_ts),
    )
