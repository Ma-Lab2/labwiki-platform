"""
comparison.py - Proton spectrum comparison rendering service.
Replaces the Qt-based drawing logic from TCompare.CompareWindow.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm
from mpl_toolkits.axes_grid1 import make_axes_locatable
from io import BytesIO
import os
import base64

from backend.core import TImageRead, TFilter, TCompare
from backend.services.renderer import get_colormap


def generate_comparison_image(
    file_list: list,
    params: dict,
    tps_obj,
    y_range_px: int = 80,
    gamma: float = 1.0,
    color_min: int = 0,
    color_max: int = 65536,
    cmap_name: str = 'partical',
    custom_energy_ticks: str = '',
) -> bytes:
    """
    Generate a proton spectrum comparison image (PNG bytes).

    Parameters
    ----------
    file_list : list of str
        Full paths to image files.
    params : dict
        Analysis params (X0, Y0, A, Z, Emin, Emax, dY, filterMode, etc.).
    tps_obj : TPS
        TPS hardware parameters.
    y_range_px : int
        Y display range in pixels (default 80).
    gamma : float
        Gamma correction (default 1.0 = linear).
    color_min, color_max : int
        Colorbar range.
    cmap_name : str
        Colormap name.
    custom_energy_ticks : str
        User-specified energy ticks (comma-separated), or empty for auto.

    Returns
    -------
    bytes : PNG image data.
    """
    comparison_data = []

    X0 = params['X0']
    Y0 = params['Y0']
    A = params.get('A', 1)
    Z = params.get('Z', 1)
    Emin = params.get('Emin', 0.0)
    Emax = params.get('Emax', 100.0)
    dY = params.get('dY', 3)
    Res = tps_obj.Res

    for file_path in file_list:
        if not os.path.isfile(file_path):
            continue

        img, is8bit = TImageRead.readImage(file_path)
        filter_params = {
            'medianSize': params.get('medianSize', 5),
            'medianIterations': params.get('medianIterations', 1),
            'morphologicalSize': params.get('morphologicalSize', 3),
            'rollingBallRadius': params.get('rollingBallRadius', 15),
        }
        img = TFilter.applyFilter(img, params.get('filterMode', 'none'), filter_params)
        image_data = np.flipud(img)

        compensated, y_range, x_range, new_y0 = TCompare.compensateElectricField(
            image_data, tps_obj, X0, Y0, A, Z, Emin, Emax, dY
        )

        comparison_data.append({
            'fileName': os.path.basename(file_path),
            'image': compensated,
            'yRange': y_range,
            'xRange': x_range,
            'newY0': new_y0,
        })

    if not comparison_data:
        raise ValueError("No valid images to compare")

    # Render the comparison figure
    return _draw_comparison(
        comparison_data, params, tps_obj, y_range_px,
        gamma, color_min, color_max, cmap_name, custom_energy_ticks
    )


def _draw_comparison(
    comparison_data, params, tps_obj, strip_height_px,
    gamma, color_min, color_max, cmap_name, custom_energy_ticks
):
    """Draw comparison figure (single axes + vertical stacking)."""
    n_images = len(comparison_data)
    X0 = params['X0']
    A = params.get('A', 1)
    Z = params.get('Z', 1)
    Emin = params.get('Emin', 0.0)
    Emax = params.get('Emax', 100.0)
    Res = tps_obj.Res

    all_xmin = min(d['xRange'][0] for d in comparison_data)
    all_xmax = max(d['xRange'][1] for d in comparison_data)

    # Build image strips
    image_strips = []
    y0_positions = []
    split_positions = []
    filenames = []
    current_y_offset = 0

    for i, data in enumerate(comparison_data):
        new_y0 = data['newY0']
        strip_y_min = max(0, new_y0 - strip_height_px // 2)
        strip_y_max = min(data['image'].shape[0], new_y0 + strip_height_px // 2)
        region = data['image'][strip_y_min:strip_y_max, all_xmin:all_xmax]
        image_strips.append(region)

        y0_in_strip = (new_y0 - strip_y_min) * Res
        y0_positions.append(current_y_offset + y0_in_strip)
        filenames.append(data['fileName'])

        strip_h = region.shape[0] * Res
        current_y_offset += strip_h

        if i < n_images - 1:
            split_positions.append(current_y_offset)

    combined = np.vstack(image_strips)

    # Crop blank columns
    col_max = np.max(combined, axis=0)
    valid_cols = np.where(col_max > 0)[0]
    if len(valid_cols) > 0:
        actual_xmin = valid_cols[0] + all_xmin
        actual_xmax = valid_cols[-1] + all_xmin
        combined = combined[:, valid_cols[0]:valid_cols[-1]+1]
    else:
        actual_xmin, actual_xmax = all_xmin, all_xmax

    # Physics
    LB = (tps_obj.L / 2 + tps_obj.D) * tps_obj.L
    TB = Z * tps_obj.B * LB * 0.00998115

    def x_pixel_to_energy(x_px):
        if x_px <= X0:
            return 50
        return (TB / ((x_px - X0) * Res)) ** 2 / (2 * A)

    E_min_actual = x_pixel_to_energy(actual_xmax)
    E_max_actual = x_pixel_to_energy(actual_xmin)

    x_phys_min = (actual_xmin - X0) * Res
    x_phys_max = (actual_xmax - X0) * Res
    y_phys_max = combined.shape[0] * Res

    # Create figure
    fig, ax = plt.subplots(figsize=(12, max(4, 2 * n_images)))
    cmap = get_colormap(cmap_name)

    if abs(gamma - 1.0) > 0.01:
        norm = PowerNorm(gamma=gamma, vmin=color_min, vmax=color_max)
        im = ax.imshow(combined, cmap=cmap, aspect='equal',
                       extent=[x_phys_min, x_phys_max, 0, y_phys_max],
                       norm=norm, origin='lower', interpolation='bilinear')
    else:
        im = ax.imshow(combined, cmap=cmap, aspect='equal',
                       extent=[x_phys_min, x_phys_max, 0, y_phys_max],
                       vmin=color_min, vmax=color_max,
                       origin='lower', interpolation='bilinear')

    ax.set_xlim(x_phys_max, x_phys_min)
    ax.set_ylim(0, y_phys_max)
    ax.margins(0)
    ax.autoscale(enable=False)

    # Split lines and Y0 reference lines
    for sy in split_positions:
        ax.axhline(y=sy, color='black', linewidth=0.8, alpha=0.8, zorder=10)
    for y0p in y0_positions:
        ax.axhline(y=y0p, color='red', linewidth=0.8, linestyle='--', alpha=0.7, zorder=5)

    # Y-axis: filenames
    y_tick_pos = []
    y_tick_labels = []
    prev_split = 0
    for i, fn in enumerate(filenames):
        next_split = split_positions[i] if i < len(split_positions) else y_phys_max
        center = (prev_split + next_split) / 2
        y_tick_pos.append(center)
        name = os.path.splitext(fn)[0]
        y_tick_labels.append(name[:15] + '...' if len(name) > 15 else name)
        prev_split = next_split

    ax.set_yticks(y_tick_pos)
    ax.set_yticklabels(y_tick_labels, fontsize=8)

    # X-axis: energy ticks
    if custom_energy_ticks.strip():
        energy_ticks = []
        for part in custom_energy_ticks.replace(',', ' ').split():
            try:
                e = float(part)
                if e > 0:
                    energy_ticks.append(e)
            except ValueError:
                continue
        energy_ticks = sorted(set(energy_ticks), reverse=True) or \
            TCompare.generateAutoEnergyTicks(E_min_actual, E_max_actual)
    else:
        energy_ticks = TCompare.generateAutoEnergyTicks(E_min_actual, E_max_actual)

    def energy_to_x_mm(E):
        if E <= 0:
            return x_phys_max
        x_px = X0 + TB / np.sqrt(2 * A * E) / Res
        return (x_px - X0) * Res

    ax.set_xticks([energy_to_x_mm(E) for E in energy_ticks])
    ax.set_xticklabels([f'{E:.0f}' for E in energy_ticks])
    ax.set_xlabel('Proton Energy (MeV)', fontsize=11)
    ax.set_title('Proton Spectrum Comparison (Electric field compensated)', fontsize=13, pad=15)
    ax.grid(True, alpha=0.2, linestyle=':', linewidth=0.5)

    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="2%", pad=0.1)
    cbar = fig.colorbar(im, cax=cax, label='Intensity (a.u.)')
    cbar.ax.tick_params(labelsize=9)

    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
