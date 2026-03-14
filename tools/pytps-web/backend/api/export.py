"""
export.py - Export spectrum data and images.
"""

import os
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from io import BytesIO, StringIO

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/spectrum")
async def export_spectrum(session_id: str = Query(...)):
    """Export spectrum data as TXT file (tab-delimited: E, dN/dE)."""
    # TODO: integrate with session manager
    raise HTTPException(501, "Export via REST requires session. Use WebSocket mode.")


@router.get("/image")
async def export_image(session_id: str = Query(...)):
    """Export current pseudocolor image as PNG."""
    raise HTTPException(501, "Export via REST requires session. Use WebSocket mode.")
