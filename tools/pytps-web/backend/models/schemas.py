"""
schemas.py - Pydantic request/response models.
"""

from pydantic import BaseModel, Field
from typing import Optional


class TPSSettings(BaseModel):
    B: float = Field(..., description="Magnetic field (Tesla)")
    U: float = Field(..., description="Electric field voltage (V)")
    EMGain: float = Field(..., description="EMCCD gain")
    S1: float = Field(..., description="Slit width (mm)")
    Res: float = Field(..., description="Pixel resolution (mm/pixel)")
    L: float = Field(..., description="Magnetic field length (mm)")
    D: float = Field(..., description="Drift distance (mm)")
    L1: float = Field(..., description="Electric field param L1 (mm)")
    L2: float = Field(..., description="Electric field param L2 (mm)")
    L3: float = Field(..., description="Electric field param L3 (mm)")
    theta: float = Field(..., description="Electric field angle")
    d: float = Field(..., description="Electrode gap (mm)")
    D1: float = Field(..., description="Electric drift distance (mm)")
    L0: float = Field(..., description="Source distance (mm)")
    QE: float = Field(..., description="Quantum efficiency")


class AnalysisParams(BaseModel):
    X0: int = 81
    Y0: int = 465
    dY: int = 3
    Emin: float = 0.0
    Emax: float = 100.0
    A: int = 1
    Z: int = 1
    colormin: int = 0
    colormax: int = 60000
    specEmin: float = 0.0
    specEmax: float = 100.0
    specdNdEmin: float = 1e6
    specdNdEmax: float = 3e11
    filterMode: str = "none"
    medianSize: int = 5
    medianIterations: int = 1
    morphologicalSize: int = 3
    rollingBallRadius: int = 15
    protectionWidth: int = 9
    aggressiveSize: int = 15
    gentleSize: int = 5
    fadeRadius: int = 20
    cmap: str = "partical"
    showParabola: bool = False


class SolveRequest(BaseModel):
    session_id: Optional[str] = None
    image_path: str
    params: Optional[AnalysisParams] = None


class BatchRequest(BaseModel):
    session_id: Optional[str] = None
    file_paths: list[str]
    params: Optional[AnalysisParams] = None


class CompareRequest(BaseModel):
    session_id: Optional[str] = None
    file_paths: list[str]
    params: Optional[AnalysisParams] = None
    y_range_px: int = 80
    gamma: float = 1.0
    color_min: int = 0
    color_max: int = 65536
    cmap: str = "partical"
    custom_energy_ticks: str = ""


class FitRequest(BaseModel):
    session_id: Optional[str] = None
    Efit_min: float
    Efit_max: float


class ParticleInfo(BaseModel):
    name: str
    A: int
    Z: int


class FileInfo(BaseModel):
    name: str
    size: int
    modified: float


class DirInfo(BaseModel):
    current: str
    dirs: list[str]
    parent: Optional[str] = None
    files: list[FileInfo]
    warning: Optional[str] = None
