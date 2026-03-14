"""
WebSocket endpoint for computation progress.
"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/compute/{task_id}")
async def ws_compute_progress(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time computation progress."""
    # Import task store from compute module
    from api.compute import get_task_store, _tasks_lock
    tasks = get_task_store()

    with _tasks_lock:
        task = tasks.get(task_id)

    if task is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Task not found"})
        await websocket.close()
        return

    expected_token = task.get("ws_token")
    provided_token = websocket.query_params.get("token")
    if expected_token and expected_token != provided_token:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Unauthorized websocket token"})
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        while True:
            with _tasks_lock:
                task = tasks.get(task_id)
            if task is None:
                await websocket.send_json({"type": "error", "message": "Task not found"})
                break

            status = task["status"]

            if status == "running":
                await websocket.send_json({
                    "type": "progress",
                    "message": task.get("message", ""),
                    "percent": task.get("progress", 0),
                })
            elif status == "completed":
                await websocket.send_json({
                    "type": "result",
                    "data": task["result"],
                })
                break
            elif status == "error":
                await websocket.send_json({
                    "type": "error",
                    "message": task.get("error", "Unknown error"),
                })
                break

            event = task.get("update_event")
            if not event:
                await asyncio.sleep(0.5)
                continue

            event.clear()
            try:
                # Event-driven push with timeout fallback to avoid stale sockets.
                await asyncio.wait_for(event.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                continue

    except WebSocketDisconnect:
        pass
    finally:
        # Shorten expiry for completed tasks after client disconnects.
        from api.compute import TASK_TTL_DONE_SEC, _now
        with _tasks_lock:
            if task_id in tasks and tasks[task_id]["status"] != "running":
                tasks[task_id]["expires_at"] = _now() + TASK_TTL_DONE_SEC
