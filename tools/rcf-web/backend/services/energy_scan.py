"""
Energy scan service - refactored from computation/energy_pk_thread.py

Pure Python implementation without QThread/PyQt dependencies.
"""

import math
import numpy as np
from typing import List, Dict, Optional, Callable, Any

from physics.layer_physics import (
    Al_layer, Cu_layer, Cr_layer,
    EBT1_layer, EBT2_layer, HD1_layer, HD2_layer,
    Al_layer_ion, Cu_layer_ion, Cr_layer_ion,
    EBT1_layer_ion, EBT2_layer_ion, HD1_layer_ion, HD2_layer_ion,
    generic_passive_layer_ion
)
from physics.layer_physics import generic_passive_layer
from physics.material_registry import registry
from models.rcf_model import RCF
from config import EBT2_CUTOFF_LAYER, HD1_CUTOFF_LAYER


def _get_ion(ion_key: str):
    """Get ion object from key. Returns None for proton."""
    if ion_key == "proton" or not ion_key:
        return None
    try:
        from physics.ion import get_ion
        return get_ion(ion_key)
    except (ImportError, KeyError):
        return None


def run_energy_scan(
    layers: List[Dict[str, Any]],
    energy_min: float = 0.5,
    energy_max: float = 100.0,
    energy_step: float = 0.1,
    incidence_angle: float = 0.0,
    ion_key: str = "proton",
    progress_cb: Optional[Callable[[str, float], None]] = None
) -> Dict[str, Any]:
    """
    Run energy scan across RCF stack.

    Args:
        layers: List of dicts with keys: material_name, thickness, is_detector
        energy_min/max/step: Energy range in MeV (or MeV/u for ions)
        incidence_angle: Incidence angle in degrees
        ion_key: Ion type key (e.g. "proton", "He4", "C12")
        progress_cb: Optional callback(message, percent)

    Returns:
        Dict with keys: rcf_results, res_ene_matrix, energy_range
    """
    path_factor = 1.0 / math.cos(math.radians(incidence_angle)) if incidence_angle > 0 else 1.0
    ion = _get_ion(ion_key)
    use_ion_funcs = ion is not None

    E_range = np.arange(energy_min, energy_max + energy_step, energy_step)
    row_num = len(layers)

    # Build RCF stack and rcf_dict (maps layer index -> RCF index)
    RCF_stack = []
    rcf_dict = {}  # layer_index -> rcf_index
    rcf_layer_ids = {}  # layer_index -> layer_id
    rcf_count = 0
    for i, layer in enumerate(layers):
        if layer.get("is_detector", False):
            rcf = RCF(name=layer["material_name"], rcfid=rcf_count, table_ID=i)
            RCF_stack.append(rcf)
            rcf_dict[i] = rcf_count
            rcf_layer_ids[i] = layer.get("layer_id")
            rcf_count += 1

    # Initialize result arrays
    res_ene_zoom = np.zeros(shape=(len(E_range), row_num))

    for rcf in RCF_stack:
        rcf.initialize_arrays(E_range)

    total_energies = len(E_range)

    # Scan through each input energy
    for kk, Ein in enumerate(E_range):
        if progress_cb and kk % max(1, total_energies // 20) == 0:
            pct = (kk / total_energies) * 100
            progress_cb(f"扫描 {Ein:.1f} MeV", pct)

        Eout = Ein

        for i in range(row_num):
            material_name = layers[i]["material_name"]
            thickness = float(layers[i]["thickness"])

            if material_name == "Al":
                if Eout <= 0:
                    break
                if use_ion_funcs:
                    Eout = Al_layer_ion(Eout, thickness, ion, path_factor)
                else:
                    Eout = Al_layer(Eout, thickness, path_factor)
                res_ene_zoom[kk, i] = Eout
                if Eout <= 0:
                    break

            elif material_name == "Cu":
                if Eout <= 0:
                    break
                if use_ion_funcs:
                    Eout, Cu_stop_pos, edep = Cu_layer_ion(Eout, int(thickness), ion, path_factor)
                else:
                    Eout, Cu_stop_pos, edep = Cu_layer(Eout, int(thickness), path_factor)
                res_ene_zoom[kk, i] = Eout
                if Eout <= 0:
                    break
                if i in rcf_dict:
                    index = rcf_dict[i]
                    RCF_stack[index].record_deposition(kk, Cu_stop_pos, edep)
                    if Cu_stop_pos <= thickness:
                        RCF_stack[index].add_detection_energy(Ein)

            elif material_name == "Cr":
                if Eout <= 0:
                    break
                if use_ion_funcs:
                    Eout, Cr_stop_pos, edep = Cr_layer_ion(Eout, int(thickness), ion, path_factor)
                else:
                    Eout, Cr_stop_pos, edep = Cr_layer(Eout, int(thickness), path_factor)
                res_ene_zoom[kk, i] = Eout
                if Eout <= 0:
                    break
                if i in rcf_dict:
                    index = rcf_dict[i]
                    RCF_stack[index].record_deposition(kk, Cr_stop_pos, edep)
                    if Cr_stop_pos <= thickness:
                        RCF_stack[index].add_detection_energy(Ein)

            elif material_name == "EBT":
                if Eout <= 0:
                    break
                if use_ion_funcs:
                    Eout = EBT1_layer_ion(Eout, ion, path_factor)
                    res_ene_zoom[kk, i] = Eout
                    if Eout <= 0:
                        break
                    Eout, EBT2_stop_pos, edep = EBT2_layer_ion(Eout, ion, path_factor)
                else:
                    Eout = EBT1_layer(Eout, path_factor)
                    res_ene_zoom[kk, i] = Eout
                    if Eout <= 0:
                        break
                    Eout, EBT2_stop_pos, edep = EBT2_layer(Eout, path_factor)
                res_ene_zoom[kk, i] = Eout
                if i in rcf_dict:
                    index = rcf_dict[i]
                    RCF_stack[index].record_deposition(kk, EBT2_stop_pos, edep)
                    N_cutoff = int(round(EBT2_CUTOFF_LAYER * path_factor))
                    if EBT2_stop_pos <= N_cutoff:
                        RCF_stack[index].add_detection_energy(Ein)
                if Eout <= 0:
                    break
                if use_ion_funcs:
                    Eout = EBT1_layer_ion(Eout, ion, path_factor)
                else:
                    Eout = EBT1_layer(Eout, path_factor)
                res_ene_zoom[kk, i] = Eout
                if Eout <= 0:
                    break

            elif material_name == "HD":
                if Eout <= 0:
                    break
                if use_ion_funcs:
                    Eout, HD1_stop_pos, edep = HD1_layer_ion(Eout, ion, path_factor)
                else:
                    Eout, HD1_stop_pos, edep = HD1_layer(Eout, path_factor)
                res_ene_zoom[kk, i] = Eout
                if i in rcf_dict:
                    index = rcf_dict[i]
                    RCF_stack[index].record_deposition(kk, HD1_stop_pos, edep)
                    N_cutoff = int(round(HD1_CUTOFF_LAYER * path_factor))
                    if HD1_stop_pos <= N_cutoff:
                        RCF_stack[index].add_detection_energy(Ein)
                if Eout <= 0:
                    break
                if use_ion_funcs:
                    Eout = HD2_layer_ion(Eout, ion, path_factor)
                else:
                    Eout = HD2_layer(Eout, path_factor)
                res_ene_zoom[kk, i] = Eout
                if Eout <= 0:
                    break

            else:
                # Custom PSTAR material
                if Eout <= 0:
                    break
                if registry.exists(material_name):
                    material = registry.get(material_name)
                    if use_ion_funcs:
                        Eout, stop_pos, edep = generic_passive_layer_ion(
                            Eout, thickness, material, ion, path_factor
                        )
                    else:
                        Eout, stop_pos, edep = generic_passive_layer(
                            Eout, thickness, material, path_factor
                        )
                    res_ene_zoom[kk, i] = Eout
                    if i in rcf_dict:
                        index = rcf_dict[i]
                        RCF_stack[index].record_deposition(kk, stop_pos, edep)
                        if stop_pos <= thickness:
                            RCF_stack[index].add_detection_energy(Ein)
                    if Eout <= 0:
                        break
                else:
                    continue

    # Calculate cutoff energies
    for rcf in RCF_stack:
        rcf.calculate_cutoff_energy(E_range)

    if progress_cb:
        progress_cb("计算完成", 100.0)

    # Build response
    rcf_results = []
    for rcf in RCF_stack:
        energies, depositions = rcf.get_response_curve()
        rcf_results.append({
            "rcf_id": rcf.rcfid,
            "name": rcf.name,
            "table_id": rcf.table_ID,
            "layer_id": rcf_layer_ids.get(rcf.table_ID),
            "cutoff_energy": rcf.Cutoff_ene,
            "energy_zoom": [round(e, 1) for e in rcf.energy_zoom],
            "edep_curve_x": energies.tolist() if energies is not None else [],
            "edep_curve_y": depositions.tolist() if depositions is not None else [],
        })

    return {
        "rcf_results": rcf_results,
        "res_ene_matrix": res_ene_zoom.tolist(),
        "energy_range": E_range.tolist(),
    }
