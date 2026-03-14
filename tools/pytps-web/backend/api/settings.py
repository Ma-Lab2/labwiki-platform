"""
settings.py - TPS parameters and initialization settings API.
"""

import os
import numpy as np
from fastapi import APIRouter, HTTPException
from backend.models.schemas import TPSSettings, ParticleInfo
from backend.core.TSettings import TPS, TPSinit, particleList, colormapList
from backend.config import DATA_DIR

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/tps")
async def get_tps_settings():
    """Get current TPS hardware parameters."""
    settings_path = os.path.join(DATA_DIR, "TPS_Settings.ini")
    tps = TPS(settings_path)
    return tps.to_dict()


@router.put("/tps")
async def update_tps_settings(settings: TPSSettings):
    """Update TPS hardware parameters (saves to file)."""
    settings_path = os.path.join(DATA_DIR, "TPS_Settings.ini")

    lines = [
        f"B=\t{settings.B}",
        f"U=\t{settings.U}",
        f"EMGain=\t{settings.EMGain}",
        f"S1=\t{settings.S1}",
        f"Res=\t{settings.Res}",
        f"L=\t{settings.L}",
        f"D=\t{settings.D}",
        f"L1=\t{settings.L1}",
        f"L2=\t{settings.L2}",
        f"L3=\t{settings.L3}",
        f"theta=\t{settings.theta}",
        f"d=\t{settings.d}",
        f"D1=\t{settings.D1}",
        f"L0=\t{settings.L0}",
        f"QE=\t{settings.QE}",
    ]
    with open(settings_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return {"success": True}


@router.get("/init")
async def get_init_settings():
    """Get application initialization parameters."""
    init_path = os.path.join(DATA_DIR, "PyTPS_init.ini")
    params = TPSinit(init_path)
    return params


@router.get("/particles")
async def get_particles():
    """Get list of available particles."""
    return particleList()


@router.get("/colormaps")
async def get_colormaps():
    """Get list of available colormaps."""
    return colormapList()
