"""
Linear design service - refactored from computation/linear_design_thread.py

Pure Python implementation without QThread/PyQt dependencies.
Finds optimal aluminum thicknesses for linearly spaced cutoff energies.
"""

import math
import numpy as np
from typing import List, Dict, Optional, Callable, Any

from physics.layer_physics import Al_layer, EBT1_layer, EBT2_layer, HD1_layer, HD2_layer
from config import EBT2_CUTOFF_LAYER, HD1_CUTOFF_LAYER


def _test_energy_through_layers(
    initial_energy: float,
    layer_config: List[tuple],
    target_detector_type: str,
    path_factor: float
) -> tuple:
    """
    Test energy propagation through layer configuration.

    Returns:
        (final_energy, is_valid, edep)
    """
    current_energy = initial_energy

    for i, (material_type, thickness) in enumerate(layer_config):
        if i == len(layer_config) - 1:
            break

        if material_type == "Al":
            current_energy = Al_layer(current_energy, thickness, path_factor)
        elif material_type == "HD":
            current_energy, _, _ = HD1_layer(current_energy, path_factor)
            if current_energy > 0:
                current_energy = HD2_layer(current_energy, path_factor)
        elif material_type == "EBT":
            current_energy = EBT1_layer(current_energy, path_factor)
            if current_energy > 0:
                current_energy, _, _ = EBT2_layer(current_energy, path_factor)
                if current_energy > 0:
                    current_energy = EBT1_layer(current_energy, path_factor)

        if current_energy <= 0:
            return 0, False, 0

    if current_energy <= 0:
        return 0, False, 0

    if target_detector_type == "HD":
        final_energy, stop_pos, edep = HD1_layer(current_energy, path_factor)
        N_cutoff = int(round(HD1_CUTOFF_LAYER * path_factor))
        is_valid = (stop_pos <= N_cutoff and edep > 0)
        return final_energy, is_valid, edep
    elif target_detector_type == "EBT":
        energy_after_ebt1 = EBT1_layer(current_energy, path_factor)
        if energy_after_ebt1 > 0:
            final_energy, stop_pos, edep = EBT2_layer(energy_after_ebt1, path_factor)
            N_cutoff = int(round(EBT2_CUTOFF_LAYER * path_factor))
            is_valid = (stop_pos <= N_cutoff and edep > 0)
            return final_energy, is_valid, edep

    return 0, False, 0


def _calculate_first_rcf_cutoff_energy(
    al_thick_1: float,
    detector_type: str,
    path_factor: float,
    progress_cb: Optional[Callable] = None
) -> float:
    """Calculate cutoff energy for first RCF."""
    energy_scan_min = 0.5
    energy_scan_max = 100.0
    energy_scan_step = 0.1

    E_range = np.arange(energy_scan_min, energy_scan_max + energy_scan_step, energy_scan_step)

    edep_data = []
    energy_data = []

    if progress_cb:
        progress_cb(f"扫描能量范围: {energy_scan_min}-{energy_scan_max} MeV", 5.0)

    for Ein in E_range:
        Eout = Ein
        Eout = Al_layer(Eout, al_thick_1, path_factor)
        if Eout <= 0:
            continue

        edep = 0
        if detector_type == "EBT":
            Eout = EBT1_layer(Eout, path_factor)
            if Eout > 0:
                Eout, EBT2_stop_pos, edep = EBT2_layer(Eout, path_factor)
                N_cutoff = int(round(EBT2_CUTOFF_LAYER * path_factor))
                if EBT2_stop_pos <= N_cutoff and edep > 0:
                    energy_data.append(Ein)
                    edep_data.append(edep)
        elif detector_type == "HD":
            Eout, HD1_stop_pos, edep = HD1_layer(Eout, path_factor)
            N_cutoff = int(round(HD1_CUTOFF_LAYER * path_factor))
            if HD1_stop_pos <= N_cutoff and edep > 0:
                energy_data.append(Ein)
                edep_data.append(edep)

    if len(edep_data) == 0:
        return 0.0

    edep_array = np.array(edep_data)
    index_max = np.argmax(edep_array)
    cutoff_energy = energy_data[index_max]

    if progress_cb:
        progress_cb(f"第一个RCF截止能量: {cutoff_energy:.2f} MeV", 10.0)

    return cutoff_energy


def _find_aluminum_thickness_for_target_energy(
    current_layers: List[tuple],
    detector_type: str,
    detector_thickness: float,
    target_energy: float,
    al_thick_min: float,
    al_thick_max: float,
    al_interval: float,
    path_factor: float,
    progress_cb: Optional[Callable] = None,
    base_percent: float = 0.0,
    percent_range: float = 10.0
) -> float:
    """Search for optimal aluminum thickness with two-stage coarse/fine scan."""
    if al_thick_max < al_thick_min:
        return 0.0

    energy_test_range = np.arange(max(0.1, target_energy - 0.5), target_energy + 0.5, 0.1)

    def score_for_thickness(al_thick: float) -> float:
        test_layers = current_layers + [("Al", al_thick), (detector_type, detector_thickness)]
        best_local_score = float("inf")
        for test_energy in energy_test_range:
            try:
                _, is_valid, edep = _test_energy_through_layers(
                    test_energy, test_layers, detector_type, path_factor
                )
                if is_valid and edep > 0:
                    energy_match_score = abs(test_energy - target_energy)
                    deposition_score = 1.0 / max(edep, 0.001)
                    total_score = energy_match_score + deposition_score * 0.1
                    if total_score < best_local_score:
                        best_local_score = total_score
            except Exception:
                continue
        return best_local_score

    fine_step = max(al_interval, 0.1)
    coarse_step = max(fine_step * 5.0, 5.0)

    coarse_values = np.arange(al_thick_min, al_thick_max + coarse_step, coarse_step)
    if coarse_values.size == 0:
        coarse_values = np.array([al_thick_min])

    # Worst-case evaluation count for progress reporting.
    coarse_total = len(coarse_values)
    fine_total = 0
    for center in coarse_values[: min(3, len(coarse_values))]:
        low = max(al_thick_min, center - coarse_step)
        high = min(al_thick_max, center + coarse_step)
        fine_total += int((high - low) / fine_step) + 1
    total_evals = max(1, coarse_total + fine_total)
    eval_count = 0

    coarse_scores = []
    for al_thick in coarse_values:
        score = score_for_thickness(float(al_thick))
        coarse_scores.append((score, float(al_thick)))
        eval_count += 1
        if progress_cb:
            pct = base_percent + (eval_count / total_evals) * percent_range
            progress_cb(f"粗搜索: 厚度 {al_thick:.1f}μm", pct)

    coarse_scores.sort(key=lambda item: item[0])
    best_candidates = [thick for _, thick in coarse_scores[: min(3, len(coarse_scores))]]

    best_thickness = best_candidates[0] if best_candidates else al_thick_min
    best_score = float("inf")

    for center in best_candidates:
        low = max(al_thick_min, center - coarse_step)
        high = min(al_thick_max, center + coarse_step)
        for al_thick in np.arange(low, high + fine_step, fine_step):
            score = score_for_thickness(float(al_thick))
            eval_count += 1
            if progress_cb:
                pct = base_percent + (eval_count / total_evals) * percent_range
                progress_cb(f"精搜索: 厚度 {al_thick:.1f}μm", pct)

            if score < best_score:
                best_score = score
                best_thickness = float(al_thick)

    return max(al_thick_min, min(al_thick_max, best_thickness))


def run_linear_design(
    detectors: List[Dict[str, Any]],
    al_thick_1: float = 30.0,
    energy_interval: float = 2.0,
    al_thick_min: float = 0.0,
    al_thick_max: float = 1000.0,
    al_interval: float = 1.0,
    incidence_angle: float = 0.0,
    progress_cb: Optional[Callable[[str, float], None]] = None
) -> Dict[str, Any]:
    """
    Run linear design optimization.

    Args:
        detectors: List of detector dicts with material_name, thickness
        al_thick_1: First aluminum thickness (um)
        energy_interval: Desired energy interval between detectors (MeV)
        al_thick_min/max/interval: Search range for Al thickness (um)
        incidence_angle: Incidence angle in degrees
        progress_cb: Optional callback(message, percent)

    Returns:
        Dict with energy_sequence, al_thickness_sequence, full_stack, messages
    """
    path_factor = 1.0 / math.cos(math.radians(incidence_angle)) if incidence_angle > 0 else 1.0
    messages = []

    if not detectors:
        return {
            "energy_sequence": [],
            "al_thickness_sequence": [],
            "full_stack": [],
            "messages": ["没有RCF配置数据"]
        }

    row_num = len(detectors)
    messages.append(
        f"使用参数: 初始铝厚={al_thick_1}μm, 能量间隔={energy_interval}MeV, "
        f"斜入射系数={path_factor:.3f}"
    )

    if progress_cb:
        progress_cb("计算第一个RCF的截止能量...", 5.0)

    first_detector_type = detectors[0]["material_name"]
    first_detector_thickness = float(detectors[0]["thickness"])

    first_cutoff_energy = _calculate_first_rcf_cutoff_energy(
        al_thick_1, first_detector_type, path_factor, progress_cb
    )

    if first_cutoff_energy <= 0:
        return {
            "energy_sequence": [],
            "al_thickness_sequence": [],
            "full_stack": [],
            "messages": messages + ["第一个RCF计算失败"]
        }

    target_energies = [first_cutoff_energy + j * energy_interval for j in range(row_num)]
    messages.append(f"目标能量序列: {[f'{e:.1f}' for e in target_energies]} MeV")

    E_zoom = [first_cutoff_energy]
    Al_zoom = [al_thick_1]

    current_layers = [
        ("Al", al_thick_1),
        (first_detector_type, first_detector_thickness)
    ]

    for ej in range(1, row_num):
        target_energy = target_energies[ej]
        detector_type = detectors[ej]["material_name"]
        detector_thickness = float(detectors[ej]["thickness"])

        if progress_cb:
            progress_cb(f"为第{ej + 1}个RCF寻找铝厚度 (目标: {target_energy:.1f} MeV)...",
                       10.0 + (ej / row_num) * 80.0)

        best_al = _find_aluminum_thickness_for_target_energy(
            current_layers, detector_type, detector_thickness, target_energy,
            al_thick_min, al_thick_max, al_interval, path_factor,
            progress_cb,
            base_percent=10.0 + (ej / row_num) * 80.0,
            percent_range=80.0 / row_num
        )

        current_layers.extend([
            ("Al", best_al),
            (detector_type, detector_thickness)
        ])

        E_zoom.append(target_energy)
        Al_zoom.append(best_al)
        messages.append(f"第{ej + 1}个RCF: 铝厚度={best_al:.1f}μm")

    # Build full stack
    full_stack = []
    for i in range(len(detectors)):
        full_stack.append({
            "material_name": "Al",
            "thickness": Al_zoom[i],
            "thickness_type": "variable",
            "is_detector": False
        })
        full_stack.append({
            "material_name": detectors[i]["material_name"],
            "thickness": float(detectors[i]["thickness"]),
            "thickness_type": "fixed",
            "is_detector": True,
            "layer_id": detectors[i].get("layer_id"),
        })

    messages.append("线性设计完成！")
    messages.append(f"能量序列: {[f'{e:.1f}' for e in E_zoom]} MeV")
    messages.append(f"铝厚度序列: {[f'{a:.1f}' for a in Al_zoom]} μm")

    if progress_cb:
        progress_cb("线性设计完成", 100.0)

    return {
        "energy_sequence": E_zoom,
        "al_thickness_sequence": Al_zoom,
        "full_stack": full_stack,
        "messages": messages
    }
