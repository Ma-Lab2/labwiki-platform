from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from .stack import StackLayer


class EnergyScanRequest(BaseModel):
    layers: List[StackLayer]
    energy_min: float = Field(default=0.5, gt=0)
    energy_max: float = Field(default=100.0, gt=0)
    energy_step: float = Field(default=0.1, gt=0)
    incidence_angle: float = Field(default=0.0, ge=0, lt=90)   # degrees
    ion_key: str = "proton"

    @model_validator(mode="after")
    def validate_energy_range(self):
        if self.energy_min >= self.energy_max:
            raise ValueError("energy_min must be less than energy_max")
        return self


class RCFResult(BaseModel):
    rcf_id: int
    name: str
    table_id: int
    layer_id: Optional[str] = None
    cutoff_energy: Optional[float] = None
    energy_zoom: List[float] = []
    edep_curve_x: List[float] = []    # input energies
    edep_curve_y: List[float] = []    # deposited energies


class EnergyScanResponse(BaseModel):
    rcf_results: List[RCFResult]
    res_ene_matrix: List[List[float]]
    energy_range: List[float]


class LinearDesignRequest(BaseModel):
    detectors: List[StackLayer]       # detector sequence (HD/EBT only)
    al_thick_1: float = Field(default=30.0, ge=0)          # first Al thickness μm
    energy_interval: float = Field(default=2.0, gt=0)      # MeV between detectors
    al_thick_min: float = Field(default=0.0, ge=0)
    al_thick_max: float = Field(default=1000.0, ge=0)
    al_interval: float = Field(default=1.0, gt=0)
    incidence_angle: float = Field(default=0.0, ge=0, lt=90)

    @model_validator(mode="after")
    def validate_search_range(self):
        if self.al_thick_min > self.al_thick_max:
            raise ValueError("al_thick_min must be less than or equal to al_thick_max")
        return self


class LinearDesignResponse(BaseModel):
    energy_sequence: List[float]
    al_thickness_sequence: List[float]
    full_stack: List[StackLayer]
    messages: List[str] = []


class AsyncTaskResponse(BaseModel):
    task_id: str
    ws_token: str
    expires_at: datetime


class ProgressMessage(BaseModel):
    type: str = "progress"       # "progress", "result", "error"
    message: str = ""
    percent: float = 0.0
    data: Optional[dict] = None
