"""
renderer.py - Matplotlib-based image rendering (replaces TDraw.py).
Generates PNG images as bytes for web transport.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm
from io import BytesIO
import os
import base64

from backend.core import CustomColormaps


def get_colormap(name: str):
    """Get a matplotlib colormap by name."""
    if name == 'partical':
        return CustomColormaps.particals
    elif name == 'field':
        return CustomColormaps.field
    else:
        try:
            return plt.get_cmap(name)
        except ValueError:
            return plt.get_cmap('jet')


def render_image(image_data: np.ndarray, params: dict,
                 parabola=None, show_parabola=False,
                 show_origin=True, cursor_x=None) -> bytes:
    """
    Render a pseudocolor image as PNG bytes.

    Parameters
    ----------
    image_data : ndarray
        Filtered, flipped image data.
    params : dict
        Display parameters: colormin, colormax, cmap, X0, Y0.
    parabola : ndarray, optional
        Parabola overlay (2, m).
    show_parabola : bool
    show_origin : bool
    cursor_x : float, optional
        Vertical cursor line position.

    Returns
    -------
    bytes : PNG image data.
    """
    fig, ax = plt.subplots(figsize=(10, 8))

    cmap = get_colormap(params.get('cmap', 'partical'))
    colormin = params.get('colormin', 0)
    colormax = params.get('colormax', 60000)

    img = ax.imshow(image_data, cmap=cmap, vmin=colormin, vmax=colormax)
    ax.invert_yaxis()
    fig.colorbar(img, ax=ax)

    if cursor_x is not None:
        ax.axvline(cursor_x, linewidth=1, color='black')

    if show_parabola and parabola is not None:
        ax.plot(parabola[0], parabola[1], alpha=0.5, linewidth=2, color='red')

    if show_origin:
        X0 = params.get('X0', 0)
        Y0 = params.get('Y0', 0)
        hLine_x = np.arange(X0 - 50, X0 + 51)
        hLine_y = np.full(101, Y0, dtype=int)
        vLine_x = np.full(101, X0, dtype=int)
        vLine_y = np.arange(Y0 - 50, Y0 + 51)
        ax.plot(hLine_x, hLine_y, linewidth=1, color='black')
        ax.plot(vLine_x, vLine_y, linewidth=1, color='black')

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_image_base64(image_data: np.ndarray, params: dict,
                        parabola=None, show_parabola=False,
                        show_origin=True, cursor_x=None) -> str:
    """Render image and return as base64 string."""
    png_bytes = render_image(image_data, params, parabola,
                             show_parabola, show_origin, cursor_x)
    return base64.b64encode(png_bytes).decode('utf-8')


def render_batch_spectrum(spectra_list: list, params: dict) -> bytes:
    """
    Render overlaid spectra from batch analysis as PNG.

    Parameters
    ----------
    spectra_list : list of dict
        Each dict has: fileName, specData (2,n), cutoffEnergy.
    params : dict
        specEmin, specEmax, specdNdEmin, specdNdEmax.

    Returns
    -------
    bytes : PNG image data.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.set_xlim(params.get('specEmin', 0), params.get('specEmax', 100))
    ax.set_ylim(params.get('specdNdEmin', 1e6), params.get('specdNdEmax', 3e11))
    ax.set_xlabel("E (MeV)")
    ax.set_ylabel("dN/dE")

    for item in spectra_list:
        if 'error' in item:
            continue
        spec = item['specData']
        cutoff = item.get('cutoffEnergy', '')
        name = os.path.splitext(item['fileName'])[0]
        label = f"{name}--{cutoff}MeV" if not isinstance(cutoff, str) else f"{name}--NaN"
        ax.semilogy(spec[0], spec[1], label=label)

    ax.legend(fontsize=8)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def spectrum_to_json(spec_data: np.ndarray, noise_spec: np.ndarray = None) -> dict:
    """
    Convert spectrum arrays to JSON-serializable format for ECharts.

    Returns
    -------
    dict with keys: energy, dNdE, noise_energy, noise_dNdE
    """
    result = {
        'energy': spec_data[0].tolist(),
        'dNdE': spec_data[1].tolist(),
    }
    if noise_spec is not None:
        result['noise_energy'] = noise_spec[0].tolist()
        result['noise_dNdE'] = noise_spec[1].tolist()
    return result
