"""
files.py - File browsing and upload API endpoints.
"""

import os
import logging
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from backend.models.schemas import FileInfo, DirInfo
from backend.config import IMAGE_DIR

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["files"])

IMAGE_EXTENSIONS = {'.tif', '.tiff', '.jpg', '.jpeg', '.png', '.raw'}


@router.get("/list")
async def list_files(path: str = Query(default=None)):
    """List image files in a directory."""
    dir_path = path or IMAGE_DIR
    if not os.path.isdir(dir_path):
        logger.warning(f"Directory not found: {dir_path}")
        return {"files": [], "warning": f"目录不存在: {dir_path}"}

    files = []
    try:
        for name in sorted(os.listdir(dir_path)):
            full = os.path.join(dir_path, name)
            if os.path.isfile(full):
                ext = os.path.splitext(name)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    stat = os.stat(full)
                    files.append(FileInfo(
                        name=name,
                        size=stat.st_size,
                        modified=stat.st_mtime,
                    ))
    except PermissionError:
        logger.warning(f"Permission denied: {dir_path}")
        return {"files": [], "warning": f"无权限访问: {dir_path}"}

    return {"files": files}


@router.get("/browse")
async def browse_directory(path: str = Query(default=None)):
    """Browse directories."""
    dir_path = path or IMAGE_DIR
    if not os.path.isdir(dir_path):
        logger.warning(f"Directory not found: {dir_path}")
        # Return a fallback with the parent directory if possible
        parent = os.path.dirname(dir_path) if dir_path != '/' else None
        return DirInfo(current=dir_path, dirs=[], parent=parent, files=[], warning=f"目录不存在: {dir_path}")

    dirs = []
    files = []
    try:
        for name in sorted(os.listdir(dir_path)):
            full = os.path.join(dir_path, name)
            if os.path.isdir(full):
                dirs.append(name)
            elif os.path.isfile(full):
                ext = os.path.splitext(name)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    stat = os.stat(full)
                    files.append(FileInfo(
                        name=name,
                        size=stat.st_size,
                        modified=stat.st_mtime,
                    ))
    except PermissionError:
        logger.warning(f"Permission denied: {dir_path}")

    parent = os.path.dirname(dir_path) if dir_path != '/' else None

    return DirInfo(current=dir_path, dirs=dirs, parent=parent, files=files)


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), path: str = Query(default=None)):
    """Upload an image file."""
    dir_path = path or IMAGE_DIR
    os.makedirs(dir_path, exist_ok=True)

    file_path = os.path.join(dir_path, file.filename)
    content = await file.read()
    with open(file_path, 'wb') as f:
        f.write(content)

    return {"filename": file.filename, "path": file_path}
