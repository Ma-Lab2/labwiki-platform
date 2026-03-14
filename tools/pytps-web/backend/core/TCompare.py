#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCompare.py - Pure computation functions for proton spectrum comparison.
Extracted from the original TCompare.py (Qt GUI removed).
"""

import numpy as np


def findProtonLineContour(imageData, X0, Y0, dY, Xmin, Xmax):
    """
    Track the actual contour of the proton spectrum line (data-driven).

    Parameters
    ----------
    imageData : ndarray
        Image data (already flipped).
    X0, Y0 : int
        Origin coordinates (pixels).
    dY : int
        Search window half-width (pixels).
    Xmin, Xmax : int
        X range (pixels).

    Returns
    -------
    contour_y : ndarray
        Y position of the proton line for each column X.
    """
    contour_y = np.zeros(imageData.shape[1])

    for x in range(imageData.shape[1]):
        if x < Xmin or x > Xmax:
            contour_y[x] = Y0
            continue

        search_range = 4 * dY
        y_min = max(0, Y0 - search_range)
        y_max = min(imageData.shape[0], Y0 + search_range + 1)

        column = imageData[y_min:y_max, x]

        if len(column) > 0 and np.max(column) > 0:
            threshold = np.max(column) * 0.3
            above_threshold = column > threshold

            if np.any(above_threshold):
                indices = np.arange(len(column))
                weights = column * above_threshold
                if np.sum(weights) > 0:
                    centroid = np.sum(indices * weights) / np.sum(weights)
                    contour_y[x] = y_min + centroid
                else:
                    contour_y[x] = Y0
            else:
                contour_y[x] = Y0
        else:
            contour_y[x] = Y0

    from scipy.ndimage import median_filter
    contour_y[Xmin:Xmax+1] = median_filter(contour_y[Xmin:Xmax+1], size=5)

    return contour_y


def compensateElectricField(imageData, TPS, X0, Y0, A, Z, Emin, Emax, dY):
    """
    Compensate electric field deflection using theory + local contour refinement.

    Parameters
    ----------
    imageData : ndarray
        Image data (already flipped).
    TPS : TPS object
        TPS parameters.
    X0, Y0 : int
        Origin coordinates (pixels).
    A, Z : int
        Particle mass number and charge number.
    Emin, Emax : float
        Energy range (MeV).
    dY : int
        Extraction window half-width (pixels).

    Returns
    -------
    compensatedImage : ndarray
        Compensated image (proton line at Y0 position).
    yRange : tuple
        Display Y range (ymin, ymax), pixel coordinates.
    xRange : tuple
        Display X range (xmin, xmax), pixel coordinates.
    newY0 : int
        Y0 position in the compensated image (pixels).
    """
    LB = (TPS.L / 2 + TPS.D) * TPS.L
    TB = Z * TPS.B * LB * 0.00998115

    LE1 = (TPS.L1 * TPS.D1 + TPS.L1 * TPS.L2 + TPS.L1 ** 2 / 2) / TPS.d
    LE2 = (np.log((TPS.L2 + TPS.L3) / TPS.L3) * (TPS.L2 + TPS.L3 + TPS.D1) - TPS.L2) / TPS.theta
    LE = (LE1 + LE2) / 2
    TE = TPS.U * Z * LE / 1000000

    if Emin == 0:
        Xmax_px = imageData.shape[1] - 1
    else:
        Xmax_px = int(np.ceil(X0 + TB / np.sqrt(2 * A * Emin) / TPS.Res))
        Xmax_px = min(Xmax_px, imageData.shape[1] - 1)

    Xmin_px = max(0, int(np.floor(X0 + TB / np.sqrt(2 * A * Emax) / TPS.Res)))

    compensatedHeight = max(16 * dY + 1, 400)
    compensatedWidth = imageData.shape[1]
    compensatedImage = np.zeros((compensatedHeight, compensatedWidth), dtype=imageData.dtype)

    newY0 = compensatedHeight // 2

    for x in range(Xmin_px, Xmax_px + 1):
        if x <= X0 or x >= imageData.shape[1]:
            continue

        E = (TB / ((x - X0) * TPS.Res)) ** 2 / (2 * A)
        electricDeflection = TE / (E * TPS.Res)
        parabola_y_theory = Y0 + electricDeflection

        energy_factor = max(1.0, Emax / E) if E > 0.1 else 3.0
        search_radius = int(dY * 1.2 * min(energy_factor, 3.0))
        search_y_min = max(0, int(parabola_y_theory) - search_radius)
        search_y_max = min(imageData.shape[0], int(parabola_y_theory) + search_radius + 1)

        search_column = imageData[search_y_min:search_y_max, x]

        if len(search_column) > 0 and np.max(search_column) > 0:
            bg_level = np.percentile(search_column, 10)
            signal = search_column - bg_level
            signal[signal < 0] = 0

            if np.sum(signal) > 0:
                indices = np.arange(len(search_column))
                weights = signal ** 2
                centroid = np.sum(indices * weights) / np.sum(weights)
                actual_parabola_y = search_y_min + centroid
            else:
                actual_parabola_y = parabola_y_theory
        else:
            actual_parabola_y = parabola_y_theory

        extract_range = 150

        src_y_center = int(np.round(actual_parabola_y))
        src_y_min = max(0, src_y_center - extract_range)
        src_y_max = min(imageData.shape[0], src_y_center + extract_range + 1)

        source_data = imageData[src_y_min:src_y_max, x]

        dst_y_min = newY0 - extract_range
        dst_y_max = newY0 + extract_range + 1

        copy_length = min(len(source_data), dst_y_max - dst_y_min)

        if copy_length > 0 and dst_y_min >= 0 and dst_y_max <= compensatedHeight:
            src_offset = (len(source_data) - copy_length) // 2
            compensatedImage[dst_y_min:dst_y_min + copy_length, x] = \
                source_data[src_offset:src_offset + copy_length]

    y_extend = 3 * dY + 15
    ymin = max(0, newY0 - y_extend)
    ymax = min(compensatedHeight, newY0 + y_extend)

    return compensatedImage, (ymin, ymax), (Xmin_px, Xmax_px), newY0


def generateAutoEnergyTicks(E_min, E_max):
    """Auto-generate energy tick marks."""
    energy_ticks = []
    if E_max >= 10:
        energy_ticks.extend(np.arange(10, min(E_max, 50) + 1, 5))
    if E_min < 10:
        energy_ticks.extend(np.arange(max(1, int(E_min)), 10, 1))
    return sorted(set(energy_ticks), reverse=True)
