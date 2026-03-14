"""
Material service - manages PSTAR material loading and registration.

Based on pstar_loader.py and utils/material_database.py from the desktop app.
"""

import json
import os
import re
from datetime import datetime, timezone
from hashlib import sha1
from typing import List, Dict, Optional, Any

from physics.material_registry import Material, registry, make_tabulated_sp


# Known material densities (g/cm³)
KNOWN_DENSITIES = {
    "Aluminum": 2.702, "Al": 2.702,
    "Copper": 8.96, "Cu": 8.96,
    "Titanium": 4.507, "Ti": 4.507,
    "Gold": 19.32, "Au": 19.32,
    "Silver": 10.49, "Ag": 10.49,
    "Lead": 11.35, "Pb": 11.35,
    "Tungsten": 19.3, "W": 19.3,
    "Beryllium": 1.848, "Be": 1.848,
    "Silicon": 2.329, "Si": 2.329,
    "Iron": 7.874, "Fe": 7.874,
    "Mylar": 1.39,
    "Kapton": 1.42,
    "Water": 1.0,
    "Polyethylene": 0.94,
    "Polystyrene": 1.06,
    "Air": 0.001205,
    "Polycarbonate": 1.2,
    "PMMA": 1.19,
    "Teflon": 2.2,
    "StainlessSteel": 8.0,
    "CR39": 1.32,
}

UPLOAD_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "uploaded_materials")
)
UPLOAD_INDEX_PATH = os.path.join(UPLOAD_DATA_DIR, "materials_index.json")


def _count_header_lines(filepath: str) -> int:
    """Count header/comment lines in a CSV file."""
    count = 0
    try:
        with open(filepath, 'r') as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith('#') or stripped.startswith('//'):
                    count += 1
                else:
                    # Check if first field is numeric
                    try:
                        float(stripped.split(',')[0].split()[0])
                        break
                    except ValueError:
                        count += 1
    except Exception:
        pass
    return count


def _ensure_upload_store():
    os.makedirs(UPLOAD_DATA_DIR, exist_ok=True)
    if not os.path.exists(UPLOAD_INDEX_PATH):
        with open(UPLOAD_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump({"materials": {}}, f, ensure_ascii=False, indent=2)


def _read_upload_index() -> Dict[str, Any]:
    _ensure_upload_store()
    with open(UPLOAD_INDEX_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {"materials": {}}
    if "materials" not in data or not isinstance(data["materials"], dict):
        data = {"materials": {}}
    return data


def _write_upload_index(data: Dict[str, Any]):
    _ensure_upload_store()
    with open(UPLOAD_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _sanitize_material_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    return safe[:64].strip("._-") or "material"


def load_all_pstar_materials(pstar_dir: str = None) -> int:
    """
    Load all PSTAR CSV materials from pstar_data/ directory.

    Returns:
        Number of materials successfully loaded.
    """
    if pstar_dir is None:
        pstar_dir = os.path.join(os.path.dirname(__file__), '..', 'pstar_data')
    pstar_dir = os.path.abspath(pstar_dir)

    if not os.path.isdir(pstar_dir):
        print(f"PSTAR directory not found: {pstar_dir}")
        return 0

    loaded = 0
    for fname in sorted(os.listdir(pstar_dir)):
        if not fname.endswith('.csv'):
            continue

        # Extract material name from filename: "Aluminum_PSTAR.csv" -> "Aluminum"
        name = fname.replace('_PSTAR.csv', '').replace('_pstar.csv', '')
        if name == fname:
            name = fname.replace('.csv', '')

        # Skip if already registered
        if registry.exists(name):
            loaded += 1
            continue

        # Find density
        density = KNOWN_DENSITIES.get(name)
        if density is None:
            print(f"  Skipping {name}: unknown density")
            continue

        csv_path = os.path.join(pstar_dir, fname)
        try:
            skip = _count_header_lines(csv_path)
            sp_func = make_tabulated_sp(csv_path, E_col=0, SP_col=4, skip_header=skip)
            material = Material(name=name, density=density, sp_func=sp_func)
            registry.register(material, csv_path=csv_path)
            loaded += 1
        except Exception as e:
            print(f"  Failed to load {name}: {e}")

    return loaded


def load_uploaded_materials() -> int:
    """
    Reload uploaded materials from persistent index and CSV files.

    Returns:
        Number of uploaded materials loaded.
    """
    data = _read_upload_index()
    loaded = 0

    for name, entry in data["materials"].items():
        csv_path = entry.get("csv_path")
        density = entry.get("density")

        if not csv_path or density is None or not os.path.isfile(csv_path):
            continue

        try:
            skip = _count_header_lines(csv_path)
            sp_func = make_tabulated_sp(csv_path, E_col=0, SP_col=4, skip_header=skip)
            material = Material(name=name, density=float(density), sp_func=sp_func)
            registry.register(material, csv_path=csv_path)
            loaded += 1
        except Exception as e:
            print(f"  Failed to reload uploaded material {name}: {e}")

    return loaded


def register_uploaded_material(
    name: str,
    density: float,
    csv_content: str,
    replace: bool = False,
) -> Dict[str, Any]:
    """
    Register a material from uploaded PSTAR CSV content.

    Args:
        name: Material name
        density: Density in g/cm³
        csv_content: Raw CSV file content as string

    Returns:
        Dict with material info
    """
    material_name = name.strip()
    if not material_name:
        raise ValueError("material name is required")
    if density <= 0:
        raise ValueError("density must be positive")

    index = _read_upload_index()
    existing = index["materials"].get(material_name)

    if existing and not replace:
        raise ValueError(f"Material '{material_name}' already exists. Set replace=true to overwrite.")

    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = sha1(csv_content.encode("utf-8")).hexdigest()[:8]
    safe_name = _sanitize_material_name(material_name)
    csv_filename = f"{safe_name}_{now}_{digest}.csv"
    csv_path = os.path.join(UPLOAD_DATA_DIR, csv_filename)

    _ensure_upload_store()
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(csv_content)

    try:
        skip = _count_header_lines(csv_path)
        sp_func = make_tabulated_sp(csv_path, E_col=0, SP_col=4, skip_header=skip)
        material = Material(name=material_name, density=density, sp_func=sp_func)
        registry.register(material, csv_path=csv_path)

        index["materials"][material_name] = {
            "name": material_name,
            "density": density,
            "csv_path": csv_path,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "source": "upload",
        }
        _write_upload_index(index)

        if existing:
            old_path = existing.get("csv_path")
            if old_path and old_path != csv_path and os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

        return {
            "name": material_name,
            "density": density,
            "source": "upload",
            "csv_path": csv_path,
        }
    except Exception as e:
        if os.path.isfile(csv_path):
            os.unlink(csv_path)
        raise ValueError(f"Failed to parse PSTAR CSV for {material_name}: {e}")


def list_registered_materials() -> List[Dict[str, Any]]:
    """List all registered materials with their info."""
    result = []
    upload_index = _read_upload_index()["materials"]

    for name in registry.list_materials():
        mat = registry.get(name)
        csv_path = registry.csv_paths.get(name)
        source = "builtin"
        if name in upload_index:
            source = "upload"
        elif csv_path:
            source = "pstar"

        info = {
            "name": name,
            "density": mat.density,
            "source": source,
            "csv_path": csv_path,
        }
        result.append(info)

    # Also list built-in materials that are always available
    builtins = ["Al", "Cu", "Cr", "EBT", "HD"]
    for b in builtins:
        if not any(r["name"] == b for r in result):
            result.append({"name": b, "density": KNOWN_DENSITIES.get(b, 0), "source": "builtin"})

    return result
