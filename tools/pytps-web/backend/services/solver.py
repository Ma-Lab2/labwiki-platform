"""
solver.py - Analysis orchestrator (replaces TSolve.py).
Pure functions that take explicit parameters and return results.
"""

import numpy as np
import os
from backend.core import TImageRead, TFilter, SolveSpectrum, TPSParabola, AutoCutoffEnergy


def build_filter_params(params: dict) -> dict:
    """Build the filter parameters dict from session params."""
    return {
        'medianSize': params.get('medianSize', 5),
        'medianIterations': params.get('medianIterations', 1),
        'morphologicalSize': params.get('morphologicalSize', 3),
        'rollingBallRadius': params.get('rollingBallRadius', 15),
        'fadeRadius': params.get('fadeRadius', 20),
        'thresholdValue': params.get('thresholdValue', 500),
        'morphKernelSize': params.get('morphKernelSize', 3),
        'showSegmentationMask': False,
        'X0': params.get('X0', 81),
        'Y0': params.get('Y0', 465),
        'A': params.get('A', 1),
        'Z': params.get('Z', 1),
        'Emin': params.get('Emin', 0.0),
        'Emax': params.get('Emax', 100.0),
        'dY': params.get('dY', 3),
        'TPS': params.get('TPS_obj'),
        'protectionWidth': params.get('protectionWidth', 9),
        'aggressiveSize': params.get('aggressiveSize', 15),
        'gentleSize': params.get('gentleSize', 5),
    }


def solve_single(image_path: str, params: dict, tps_obj) -> dict:
    """
    Analyze a single TPS image.

    Parameters
    ----------
    image_path : str
        Full path to the image file.
    params : dict
        Analysis parameters (X0, Y0, dY, Emin, Emax, A, Z, filterMode, etc.)
    tps_obj : TPS
        TPS hardware parameters object.

    Returns
    -------
    dict with keys:
        imageData: ndarray (filtered, flipped)
        specData: ndarray (2, n) - energy spectrum
        noiseSpec: ndarray (2, n) - noise spectrum
        parabola: ndarray (2, m) - parabola overlay coordinates
        cutoffEnergy: float or str
        is8bitImage: bool
    """
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    img, is8bit = TImageRead.readImage(image_path)

    filter_params = build_filter_params({**params, 'TPS_obj': tps_obj})
    filter_mode = params.get('filterMode', 'none')
    img = TFilter.applyFilter(img, filter_mode, filter_params)

    image_data = np.flipud(img)

    X0 = params['X0']
    Y0 = params['Y0']
    A = params.get('A', 1)
    Z = params.get('Z', 1)
    Emin = params.get('Emin', 0.0)
    Emax = params.get('Emax', 100.0)
    dY = params.get('dY', 3)
    mcp_path = params.get('MCPPath', '')

    spec_data, noise_spec = SolveSpectrum.SolveSpectrum(
        image_data, X0, Y0, A, Z, Emin, Emax, dY, mcp_path, tps_obj, is8bit
    )

    parabola = TPSParabola.Parabola(
        tps_obj, spec_data[0], X0, Y0, A, Z, image_data.shape[1]
    )

    return {
        'imageData': image_data,
        'specData': spec_data,
        'noiseSpec': noise_spec,
        'parabola': parabola,
        'cutoffEnergy': 0,
        'is8bitImage': is8bit,
    }


def solve_batch(file_list: list, params: dict, tps_obj) -> list:
    """
    Analyze multiple TPS images (batch mode).

    Returns a list of dicts, each with specData, noiseSpec, cutoffEnergy, fileName.
    """
    results = []
    for image_path in file_list:
        try:
            img, is8bit = TImageRead.readImage(image_path)

            filter_params = build_filter_params({**params, 'TPS_obj': tps_obj})
            filter_mode = params.get('filterMode', 'none')
            img = TFilter.applyFilter(img, filter_mode, filter_params)

            data = np.flipud(img)

            X0 = params['X0']
            Y0 = params['Y0']
            A = params.get('A', 1)
            Z = params.get('Z', 1)
            Emin = params.get('Emin', 0.0)
            Emax = params.get('Emax', 100.0)
            dY = params.get('dY', 3)
            mcp_path = params.get('MCPPath', '')
            spec_window = params.get('specWindow', 0.5)

            spec, noise = SolveSpectrum.SolveSpectrum(
                data, X0, Y0, A, Z, Emin, Emax, dY, mcp_path, tps_obj, is8bit
            )

            cutoff = AutoCutoffEnergy.CutoffEnergy(spec, noise, Emin, Emax, spec_window)

            results.append({
                'fileName': os.path.basename(image_path),
                'specData': spec,
                'noiseSpec': noise,
                'cutoffEnergy': cutoff,
            })
        except Exception as e:
            results.append({
                'fileName': os.path.basename(image_path),
                'error': str(e),
            })

    return results
