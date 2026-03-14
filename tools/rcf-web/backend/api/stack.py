"""
Stack configuration API routes.
"""

import json
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse

from schemas.stack import StackLayer

router = APIRouter(prefix="/stack", tags=["stack"])


@router.post("/validate")
async def validate_stack(layers: List[StackLayer]):
    """Validate a stack configuration."""
    errors = []
    has_detector = False

    for i, layer in enumerate(layers):
        if layer.thickness <= 0:
            errors.append(f"Layer {i}: thickness must be positive")
        if not layer.material_name:
            errors.append(f"Layer {i}: material_name is required")
        if layer.is_detector:
            has_detector = True

    if not has_detector:
        errors.append("Stack must contain at least one detector layer")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "layer_count": len(layers),
        "detector_count": sum(1 for l in layers if l.is_detector),
    }


@router.post("/import-json")
async def import_json(file: UploadFile = File(...)):
    """Import stack configuration from JSON file."""
    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    # Support both formats: bare array or {"materials": [...]}
    if isinstance(data, dict):
        data = data.get("materials", [])
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="JSON must be an array or contain 'materials' key")

    # Convert from desktop app format to web format
    layers = []
    for item in data:
        is_det = item.get("rcf") is not None or item.get("is_detector", False)
        layers.append(StackLayer(
            material_name=item["material_name"],
            thickness=float(item["thickness"]),
            thickness_type=item.get("thickness_type", "variable"),
            is_detector=is_det,
            layer_id=str(uuid.uuid4()),
        ))

    return {"layers": [l.model_dump() for l in layers]}


@router.post("/export-json")
async def export_json(layers: List[StackLayer]):
    """Export stack configuration as JSON (desktop-compatible format)."""
    data = []
    for layer in layers:
        item = {
            "material_name": layer.material_name,
            "thickness": str(layer.thickness),
            "thickness_type": layer.thickness_type,
            "rcf": None,
        }
        data.append(item)
    return data
