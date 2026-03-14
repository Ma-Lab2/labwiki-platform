"""
Material management API routes.
"""

from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from schemas.stack import MaterialInfo
from services.material_service import (
    load_all_pstar_materials,
    list_registered_materials,
    register_uploaded_material,
)

router = APIRouter(prefix="/materials", tags=["materials"])


@router.get("/", response_model=List[MaterialInfo])
async def get_materials():
    """List all registered materials."""
    materials = list_registered_materials()
    return [MaterialInfo(**m) for m in materials]


@router.post("/upload-pstar", response_model=MaterialInfo)
async def upload_pstar(
    name: str = Form(...),
    density: float = Form(...),
    replace: bool = Form(False),
    file: UploadFile = File(...)
):
    """Upload a PSTAR CSV file to register a new material."""
    content = await file.read()
    csv_text = content.decode("utf-8")

    try:
        info = register_uploaded_material(name, density, csv_text, replace=replace)
        return MaterialInfo(**info)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch-load")
async def batch_load():
    """Load all materials from pstar_data/ directory."""
    count = load_all_pstar_materials()
    return {"loaded": count, "message": f"成功加载 {count} 个材料"}
