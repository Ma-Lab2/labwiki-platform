"""
Material Registry for PSTAR-based materials

This module provides a flexible material system that can:
1. Load stopping power data from PSTAR CSV files
2. Register custom materials without writing fitting functions
3. Compute energy loss using tabulated data with interpolation

Author: Tan Song / Claude
"""

import numpy as np
from typing import Callable, Optional


class Material:
    """
    Material definition with stopping power function

    Attributes:
        name (str): Material name (e.g., 'Mylar', 'Kapton')
        density (float): Density in g/cm³
        sp_func (Callable): Stopping power function S/ρ(E) -> MeV·cm²/g
    """

    def __init__(self, name: str, density: float, sp_func: Callable[[float], float]):
        """
        Initialize a material

        Args:
            name: Material name
            density: Density in g/cm³
            sp_func: Function that returns S/ρ (MeV·cm²/g) given energy (MeV)
        """
        self.name = name
        self.density = density  # g/cm³
        self.sp_func = sp_func  # S/ρ function

    def dE_per_um(self, E: float) -> float:
        """
        Calculate energy loss per micrometer

        Args:
            E: Particle energy (MeV)

        Returns:
            Energy loss per micrometer (MeV/μm)

        Formula:
            dE/dx (MeV/μm) = (S/ρ)(E) × ρ × 10⁻⁴
        """
        if E <= 0:
            return 0.0

        S_over_rho = self.sp_func(E)  # MeV·cm²/g
        dE_dx = S_over_rho * self.density * 1e-4  # MeV/μm

        return max(0.0, dE_dx)

    def to_dict(self):
        """Serialize material to dictionary (for JSON)"""
        # Note: sp_func cannot be serialized directly
        # We'll need to store CSV path separately
        return {
            'name': self.name,
            'density': self.density
        }


class MaterialRegistry:
    """
    Global registry for materials

    Provides:
    - Material storage and lookup
    - PSTAR CSV loading
    - Built-in material registration
    """

    def __init__(self):
        self.materials = {}  # name -> Material
        self.csv_paths = {}  # name -> CSV file path (for reloading)

    def register(self, material: Material, csv_path: Optional[str] = None):
        """
        Register a material

        Args:
            material: Material object to register
            csv_path: Optional path to PSTAR CSV file (for saving/loading)
        """
        self.materials[material.name] = material
        if csv_path:
            self.csv_paths[material.name] = csv_path

        print(f"✓ 材料已注册: {material.name} (密度: {material.density} g/cm³)")

    def get(self, name: str) -> Optional[Material]:
        """Get material by name"""
        return self.materials.get(name)

    def exists(self, name: str) -> bool:
        """Check if material is registered"""
        return name in self.materials

    def list_materials(self):
        """List all registered materials"""
        return list(self.materials.keys())

    def remove(self, name: str):
        """Remove a material from registry"""
        if name in self.materials:
            del self.materials[name]
            if name in self.csv_paths:
                del self.csv_paths[name]

    def to_dict(self):
        """Serialize registry to dictionary"""
        return {
            name: {
                'material': mat.to_dict(),
                'csv_path': self.csv_paths.get(name)
            }
            for name, mat in self.materials.items()
        }


def make_tabulated_sp(csv_path: str, E_col: int = 0, SP_col: int = 1,
                      delimiter: str = ',', skip_header: int = 0) -> Callable[[float], float]:
    """
    Create stopping power function from PSTAR CSV file

    Args:
        csv_path: Path to CSV file with PSTAR data
        E_col: Column index for energy (MeV)
        SP_col: Column index for S/ρ (MeV·cm²/g)
        delimiter: CSV delimiter (default: ',')
        skip_header: Number of header lines to skip

    Returns:
        Function that takes energy (MeV) and returns S/ρ (MeV·cm²/g)

    CSV Format Expected:
        Energy[MeV], S/rho[MeV*cm^2/g]
        0.001, 1234.5
        0.002, 890.1
        ...
    """
    try:
        # Load CSV data
        data = np.loadtxt(csv_path, delimiter=delimiter, skiprows=skip_header)

        if data.ndim == 1:
            raise ValueError("CSV文件只有一列数据，需要至少两列（能量和阻止能）")

        E_grid = data[:, E_col]
        SP_grid = data[:, SP_col]

        # Validate data
        if len(E_grid) < 2:
            raise ValueError(f"数据点太少（{len(E_grid)}个），至少需要2个点")

        # Sort by energy (in case CSV is not sorted)
        sort_idx = np.argsort(E_grid)
        E_grid = E_grid[sort_idx]
        SP_grid = SP_grid[sort_idx]

        print(f"✓ 加载PSTAR数据: {len(E_grid)}个能量点")
        print(f"  能量范围: {E_grid[0]:.6f} - {E_grid[-1]:.2f} MeV")
        print(f"  S/ρ范围: {SP_grid.min():.2f} - {SP_grid.max():.2f} MeV·cm²/g")

        def sp_func(E: float) -> float:
            """
            Interpolated stopping power function

            Out-of-bounds strategy: Use endpoint values (no extrapolation)
            """
            E = float(E)

            # Clamp to table bounds (no extrapolation)
            if E <= E_grid[0]:
                return float(SP_grid[0])
            if E >= E_grid[-1]:
                return float(SP_grid[-1])

            # Linear interpolation
            return float(np.interp(E, E_grid, SP_grid))

        return sp_func

    except Exception as e:
        raise RuntimeError(f"加载PSTAR文件失败 ({csv_path}): {e}")


def load_material_from_pstar(name: str, density: float, csv_path: str,
                              E_col: int = 0, SP_col: int = 1,
                              delimiter: str = ',', skip_header: int = 0) -> Material:
    """
    Load a material from PSTAR CSV file

    Args:
        name: Material name
        density: Material density (g/cm³)
        csv_path: Path to PSTAR CSV file
        E_col: Energy column index
        SP_col: S/ρ column index
        delimiter: CSV delimiter
        skip_header: Number of header lines

    Returns:
        Material object
    """
    sp_func = make_tabulated_sp(csv_path, E_col, SP_col, delimiter, skip_header)
    return Material(name, density, sp_func)


# Global registry instance
registry = MaterialRegistry()
