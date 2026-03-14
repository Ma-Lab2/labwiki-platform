"""
handler.py - WebSocket connection management and message dispatch.
"""

import json
import os
import base64
import asyncio
import logging
import traceback
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict

logger = logging.getLogger(__name__)

from backend.services.session import SessionManager
from backend.services.solver import solve_single, solve_batch
from backend.services.renderer import render_image_base64, render_batch_spectrum, spectrum_to_json
from backend.services.comparison import generate_comparison_image
from backend.services.watcher import DirectoryWatcher
from backend.core.TSettings import TPS, TPSinit
from backend.core.TFit import FitSpectrum
from backend.core.TPSParabola import CutoffLine
from backend.config import DATA_DIR


class WebSocketManager:
    """Manages WebSocket connections and dispatches messages."""

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.connections: Dict[str, WebSocket] = {}
        self.watchers: Dict[str, DirectoryWatcher] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.connections[session_id] = websocket
        session = self.session_manager.get_or_create(session_id)

        # Send initial state
        await self._send(websocket, {
            "type": "connected",
            "session_id": session.session_id,
            "params": session.params,
        })

    def disconnect(self, session_id: str):
        self.connections.pop(session_id, None)
        # Stop watcher if active
        watcher = self.watchers.pop(session_id, None)
        if watcher:
            watcher.stop()

    async def handle_message(self, websocket: WebSocket, session_id: str, data: dict):
        """Dispatch incoming WebSocket messages."""
        msg_type = data.get("type", "")

        try:
            if msg_type == "select_image":
                await self._handle_select_image(websocket, session_id, data)
            elif msg_type == "update_param":
                await self._handle_update_param(websocket, session_id, data)
            elif msg_type == "update_params":
                await self._handle_update_params(websocket, session_id, data)
            elif msg_type == "set_cursor":
                await self._handle_set_cursor(websocket, session_id, data)
            elif msg_type == "toggle_parabola":
                await self._handle_toggle_parabola(websocket, session_id, data)
            elif msg_type == "apply_filter":
                await self._handle_apply_filter(websocket, session_id, data)
            elif msg_type == "start_watch":
                await self._handle_start_watch(websocket, session_id, data)
            elif msg_type == "stop_watch":
                await self._handle_stop_watch(session_id)
            elif msg_type == "batch_analyze":
                await self._handle_batch(websocket, session_id, data)
            elif msg_type == "compare":
                await self._handle_compare(websocket, session_id, data)
            elif msg_type == "fit":
                await self._handle_fit(websocket, session_id, data)
            elif msg_type == "export_spectrum":
                await self._handle_export_spectrum(websocket, session_id)
            else:
                await self._send(websocket, {"type": "error", "message": f"Unknown type: {msg_type}"})
        except Exception as e:
            traceback.print_exc()
            await self._send(websocket, {
                "type": "error_msg",
                "message": str(e),
            })
            await self._send(websocket, {
                "type": "computing",
                "status": "done",
            })

    async def _handle_select_image(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return

        await self._send(ws, {"type": "computing", "status": "started"})

        image_path = data.get("path", "")
        session.image_path = image_path

        tps = TPS(os.path.join(DATA_DIR, "TPS_Settings.ini"))

        # Resolve MCP path
        mcp = session.params.get('MCPPath', 'mcp-proton.txt')
        if not os.path.isabs(mcp):
            mcp = os.path.join(DATA_DIR, os.path.basename(mcp))
        session.params['MCPPath'] = mcp

        result = solve_single(image_path, session.params, tps)

        session.image_data = result['imageData']
        session.spec_data = result['specData']
        session.noise_spec = result['noiseSpec']
        session.parabola = result['parabola']
        session.cutoff_energy = result['cutoffEnergy']
        session.is_8bit = result['is8bitImage']

        image_png = render_image_base64(
            result['imageData'], session.params,
            parabola=result['parabola'],
            show_parabola=session.show_parabola,
        )

        spec_json = spectrum_to_json(result['specData'], result['noiseSpec'])
        parabola_json = {'x': result['parabola'][0].tolist(),
                         'y': result['parabola'][1].tolist()}

        await self._send(ws, {
            "type": "analysis_result",
            "image_png": image_png,
            "spectrum_data": spec_json,
            "cutoff": result['cutoffEnergy'],
            "parabola": parabola_json,
        })
        await self._send(ws, {"type": "computing", "status": "done"})

    async def _handle_update_param(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return

        param = data.get("param")
        value = data.get("value")
        if param:
            session.params[param] = value

        # Re-analyze if we have an image
        if session.image_path:
            await self._handle_select_image(ws, sid, {"path": session.image_path})

    async def _handle_update_params(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return

        params = data.get("params", {})
        session.params.update(params)

        if session.image_path:
            await self._handle_select_image(ws, sid, {"path": session.image_path})

    async def _handle_set_cursor(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return

        energy = data.get("energy", 0)
        session.spec_cursor = energy

        # Convert energy to pixel X position on image
        image_cursor_x = None
        if energy and energy > 0 and session.image_data is not None:
            tps = TPS(os.path.join(DATA_DIR, "TPS_Settings.ini"))
            A = session.params.get('A', 1)
            Z = session.params.get('Z', 1)
            X0 = session.params.get('X0', 81)
            image_cursor_x = CutoffLine(tps, energy, X0, A, Z)

        # Re-render image with cursor line (no full re-analysis needed)
        if session.image_data is not None:
            image_png = render_image_base64(
                session.image_data, session.params,
                parabola=session.parabola,
                show_parabola=session.show_parabola,
                cursor_x=image_cursor_x,
            )
            await self._send(ws, {"type": "image_update", "image_png": image_png})

        await self._send(ws, {
            "type": "cursor_update",
            "energy": energy,
            "image_x": image_cursor_x,
        })

    async def _handle_toggle_parabola(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return
        session.show_parabola = data.get("show", False)

        if session.image_data is not None:
            image_png = render_image_base64(
                session.image_data, session.params,
                parabola=session.parabola,
                show_parabola=session.show_parabola,
            )
            await self._send(ws, {"type": "image_update", "image_png": image_png})

    async def _handle_apply_filter(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return

        mode = data.get("mode", "none")
        filter_params = data.get("params", {})
        session.params['filterMode'] = mode
        session.params.update(filter_params)

        if session.image_path:
            await self._handle_select_image(ws, sid, {"path": session.image_path})

    async def _handle_start_watch(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return

        directory = data.get("directory", "")

        def on_new_file(file_path):
            asyncio.get_event_loop().call_soon_threadsafe(
                asyncio.create_task,
                self._notify_new_file(sid, file_path)
            )

        watcher = DirectoryWatcher()
        watcher.start(directory, on_new_file)
        self.watchers[sid] = watcher

        await self._send(ws, {"type": "watch_started", "directory": directory})

    async def _handle_stop_watch(self, sid):
        watcher = self.watchers.pop(sid, None)
        if watcher:
            watcher.stop()
        ws = self.connections.get(sid)
        if ws:
            await self._send(ws, {"type": "watch_stopped"})

    async def _notify_new_file(self, sid, file_path):
        ws = self.connections.get(sid)
        if ws:
            await self._send(ws, {
                "type": "new_file",
                "filename": os.path.basename(file_path),
                "path": file_path,
            })

    async def _handle_batch(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return

        await self._send(ws, {"type": "computing", "status": "started"})

        tps = TPS(os.path.join(DATA_DIR, "TPS_Settings.ini"))
        mcp = session.params.get('MCPPath', 'mcp-proton.txt')
        if not os.path.isabs(mcp):
            mcp = os.path.join(DATA_DIR, os.path.basename(mcp))
        session.params['MCPPath'] = mcp

        results = solve_batch(data.get("file_paths", []), session.params, tps)

        png_bytes = render_batch_spectrum(results, session.params)
        spectrum_png = base64.b64encode(png_bytes).decode('utf-8')

        spectra = []
        for r in results:
            if 'error' in r:
                spectra.append({'fileName': r['fileName'], 'error': r['error']})
            else:
                spectra.append({
                    'fileName': r['fileName'],
                    'cutoffEnergy': r['cutoffEnergy'],
                    'spectrum': spectrum_to_json(r['specData']),
                })

        await self._send(ws, {
            "type": "batch_result",
            "spectrum_png": spectrum_png,
            "spectra": spectra,
        })
        await self._send(ws, {"type": "computing", "status": "done"})

    async def _handle_compare(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session:
            return

        await self._send(ws, {"type": "computing", "status": "started"})

        tps = TPS(os.path.join(DATA_DIR, "TPS_Settings.ini"))

        png_bytes = generate_comparison_image(
            file_list=data.get("file_paths", []),
            params=session.params,
            tps_obj=tps,
            y_range_px=data.get("y_range_px", 80),
            gamma=data.get("gamma", 1.0),
            color_min=data.get("color_min", 0),
            color_max=data.get("color_max", 65536),
            cmap_name=data.get("cmap", "partical"),
            custom_energy_ticks=data.get("custom_energy_ticks", ""),
        )

        await self._send(ws, {
            "type": "compare_result",
            "comparison_png": base64.b64encode(png_bytes).decode('utf-8'),
        })
        await self._send(ws, {"type": "computing", "status": "done"})

    async def _handle_fit(self, ws, sid, data):
        session = self.session_manager.get_session(sid)
        if not session or session.spec_data is None:
            await self._send(ws, {"type": "error", "message": "No spectrum data available"})
            return

        Efit_min = data.get("Efit_min", 1.0)
        Efit_max = data.get("Efit_max", 50.0)

        fit_result = FitSpectrum(session.spec_data, Efit_min, Efit_max)

        if fit_result['success']:
            await self._send(ws, {
                "type": "fit_result",
                "success": True,
                "N0": fit_result['N0'],
                "kT": fit_result['kT'],
                "R2": fit_result['R2'],
                "sigma_kT": fit_result['sigma_kT'],
                "fit_curve": {
                    'energy': fit_result['E_fit'].tolist(),
                    'dNdE': fit_result['Y_model'].tolist(),
                },
            })
        else:
            await self._send(ws, {
                "type": "fit_result",
                "success": False,
                "message": fit_result['message'],
            })

    async def _handle_export_spectrum(self, ws, sid):
        session = self.session_manager.get_session(sid)
        if not session or session.spec_data is None:
            await self._send(ws, {"type": "error", "message": "No spectrum data"})
            return

        # Send spectrum data as downloadable text
        lines = []
        for i in range(session.spec_data.shape[1]):
            lines.append(f"{session.spec_data[0][i]:.6f}\t{session.spec_data[1][i]:.6e}")

        await self._send(ws, {
            "type": "export_data",
            "format": "txt",
            "content": "\n".join(lines),
            "filename": f"spectrum_{sid}.txt",
        })

    async def _send(self, ws: WebSocket, data: dict):
        try:
            await ws.send_json(data)
        except Exception as e:
            logger.warning(f"[WS] Failed to send message type={data.get('type')}: {e}")
