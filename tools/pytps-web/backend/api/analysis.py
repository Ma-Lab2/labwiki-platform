"""
analysis.py - Core analysis API endpoints: solve, batch, compare, fit.
"""

import os
import base64
from fastapi import APIRouter, HTTPException, Depends

from backend.models.schemas import SolveRequest, BatchRequest, CompareRequest, FitRequest
from backend.services.solver import solve_single, solve_batch
from backend.services.renderer import render_image_base64, render_batch_spectrum, spectrum_to_json
from backend.services.comparison import generate_comparison_image
from backend.core.TSettings import TPS, TPSinit
from backend.core.TFit import FitSpectrum
from backend.config import DATA_DIR

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _get_tps():
    return TPS(os.path.join(DATA_DIR, "TPS_Settings.ini"))


def _get_default_params():
    return TPSinit(os.path.join(DATA_DIR, "PyTPS_init.ini"))


def _merge_params(base: dict, override) -> dict:
    """Merge override params (Pydantic model or None) into base dict."""
    if override is None:
        return base
    d = override.model_dump(exclude_none=True) if hasattr(override, 'model_dump') else {}
    merged = {**base, **d}
    return merged


@router.post("/solve")
async def solve_image(req: SolveRequest):
    """Analyze a single TPS image. Returns pseudocolor PNG + spectrum data."""
    tps = _get_tps()
    defaults = _get_default_params()
    params = _merge_params(defaults, req.params)

    # Resolve MCP path
    mcp_path = params.get('MCPPath', '')
    if not os.path.isabs(mcp_path):
        mcp_path = os.path.join(DATA_DIR, os.path.basename(mcp_path))
    params['MCPPath'] = mcp_path

    try:
        result = solve_single(req.image_path, params, tps)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")

    # Render image
    image_png = render_image_base64(
        result['imageData'], params,
        parabola=result['parabola'],
        show_parabola=params.get('showParabola', False),
        show_origin=True,
    )

    # Spectrum data for ECharts
    spec_json = spectrum_to_json(result['specData'], result['noiseSpec'])

    # Parabola data
    parabola_json = {
        'x': result['parabola'][0].tolist(),
        'y': result['parabola'][1].tolist(),
    } if result['parabola'] is not None else None

    return {
        "image_png": image_png,
        "spectrum_data": spec_json,
        "cutoff": result['cutoffEnergy'],
        "parabola": parabola_json,
    }


@router.post("/batch")
async def batch_analysis(req: BatchRequest):
    """Analyze multiple images (batch mode). Returns overlaid spectrum PNG + data."""
    tps = _get_tps()
    defaults = _get_default_params()
    params = _merge_params(defaults, req.params)

    mcp_path = params.get('MCPPath', '')
    if not os.path.isabs(mcp_path):
        mcp_path = os.path.join(DATA_DIR, os.path.basename(mcp_path))
    params['MCPPath'] = mcp_path

    try:
        results = solve_batch(req.file_paths, params, tps)
    except Exception as e:
        raise HTTPException(500, f"Batch analysis failed: {str(e)}")

    # Render overlaid spectrum
    png_bytes = render_batch_spectrum(results, params)
    spectrum_png = base64.b64encode(png_bytes).decode('utf-8')

    # Spectrum data for frontend
    spectra = []
    for r in results:
        if 'error' in r:
            spectra.append({'fileName': r['fileName'], 'error': r['error']})
        else:
            spectra.append({
                'fileName': r['fileName'],
                'cutoffEnergy': r['cutoffEnergy'],
                'spectrum': spectrum_to_json(r['specData']),
            })

    return {
        "spectrum_png": spectrum_png,
        "spectra": spectra,
    }


@router.post("/compare")
async def compare_protons(req: CompareRequest):
    """Generate proton spectrum comparison image."""
    tps = _get_tps()
    defaults = _get_default_params()
    params = _merge_params(defaults, req.params)

    try:
        png_bytes = generate_comparison_image(
            file_list=req.file_paths,
            params=params,
            tps_obj=tps,
            y_range_px=req.y_range_px,
            gamma=req.gamma,
            color_min=req.color_min,
            color_max=req.color_max,
            cmap_name=req.cmap,
            custom_energy_ticks=req.custom_energy_ticks,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Comparison failed: {str(e)}")

    return {
        "comparison_png": base64.b64encode(png_bytes).decode('utf-8'),
    }


@router.post("/fit")
async def fit_spectrum(req: FitRequest):
    """Fit energy spectrum with thermal model."""
    # Need session data - for now use a simple approach
    # In WebSocket mode this would use session state
    # For REST, caller should POST spectrum data
    # TODO: integrate with session
    raise HTTPException(501, "Fit via REST not yet implemented. Use WebSocket.")
