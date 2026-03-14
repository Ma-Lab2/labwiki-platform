from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StackLayer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    material_name: str                          # "Al", "HD", "EBT", "Mylar", "Cu", "Cr" etc
    thickness: float = Field(ge=0)             # μm
    thickness_type: Literal["variable", "fixed"] = "variable"
    is_detector: bool = False                   # True for HD/EBT/Cu/Cr or custom detectors
    layer_id: Optional[str] = None

    @field_validator("material_name")
    @classmethod
    def validate_material_name(cls, v: str) -> str:
        if not v:
            raise ValueError("material_name is required")
        return v


class MaterialInfo(BaseModel):
    name: str
    density: float              # g/cm³
    source: str = "pstar"       # "builtin" or "pstar"
    csv_path: Optional[str] = None
