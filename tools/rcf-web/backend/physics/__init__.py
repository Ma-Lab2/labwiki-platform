"""
Physics module for RCF stack spectrometer design

This module contains all physics calculations including:
- Stopping power functions for various materials (Al, Cu, Cr, HD, EBT)
- Layer physics for energy transport through materials
- Material registry for PSTAR-based materials
- Multi-ion support (proton, carbon, etc.)
"""

from .stopping_power import (
    # Aluminum
    s_AL1, s_AL2, s_AL3, s_Alpk_1,
    # Copper
    s_Cu, s_Cu_1, s_Cu_2, s_Cu_3, s_Cu_4,
    # Chromium
    s_Cr, s_Cr_1, s_Cr_2, s_Cr_3, s_Cr_4,
    # HD detectors
    s_HD1_1, s_HD1_2, s_HD1_3, s_HD1_4, s_HD1pk_1,
    s_HD2_1, s_HD2_2, s_HD2_3, s_HD2pk_1,
    # EBT detectors
    s_EBT1_1, s_EBT1_2, s_EBT2_1, s_EBT2_2
)

from .layer_physics import (
    Al_layer, Cu_layer, Cr_layer,
    EBT1_layer, EBT2_layer,
    HD1_layer, HD2_layer,
    generic_passive_layer,
    design,
    # Multi-ion layer functions
    Al_layer_ion, Cu_layer_ion, Cr_layer_ion,
    EBT1_layer_ion, EBT2_layer_ion,
    HD1_layer_ion, HD2_layer_ion,
    generic_passive_layer_ion,
    calculate_layer_ion
)

from .material_registry import (
    Material,
    MaterialRegistry,
    registry,
    make_tabulated_sp,
    load_material_from_pstar
)

# Ion module
from .ion import (
    Ion,
    PROTON, DEUTERON, TRITON,
    HELIUM3, HELIUM4, ALPHA,
    CARBON12, CARBON13,
    NITROGEN14, OXYGEN16, NEON20,
    SILICON28, ARGON40, IRON56,
    ION_CATALOG,
    get_ion, list_available_ions, create_custom_ion,
    get_ion_display_list
)

# Bethe-Bloch multi-ion support
from .stopping_power_bethe import (
    bethe_bloch_ion,
    s_Al_ion,
    stopping_power_ion_in_material,
    stopping_power_ion_simple
)

__all__ = [
    # Stopping power functions
    's_AL1', 's_AL2', 's_AL3', 's_Alpk_1',
    's_Cu', 's_Cu_1', 's_Cu_2', 's_Cu_3', 's_Cu_4',
    's_Cr', 's_Cr_1', 's_Cr_2', 's_Cr_3', 's_Cr_4',
    's_HD1_1', 's_HD1_2', 's_HD1_3', 's_HD1_4', 's_HD1pk_1',
    's_HD2_1', 's_HD2_2', 's_HD2_3', 's_HD2pk_1',
    's_EBT1_1', 's_EBT1_2', 's_EBT2_1', 's_EBT2_2',
    # Layer functions
    'Al_layer', 'Cu_layer', 'Cr_layer',
    'EBT1_layer', 'EBT2_layer',
    'HD1_layer', 'HD2_layer',
    'generic_passive_layer',
    'design',
    # Multi-ion layer functions
    'Al_layer_ion', 'Cu_layer_ion', 'Cr_layer_ion',
    'EBT1_layer_ion', 'EBT2_layer_ion',
    'HD1_layer_ion', 'HD2_layer_ion',
    'generic_passive_layer_ion',
    'calculate_layer_ion',
    # Material registry
    'Material', 'MaterialRegistry', 'registry',
    'make_tabulated_sp', 'load_material_from_pstar',
    # Ion module
    'Ion',
    'PROTON', 'DEUTERON', 'TRITON',
    'HELIUM3', 'HELIUM4', 'ALPHA',
    'CARBON12', 'CARBON13',
    'NITROGEN14', 'OXYGEN16', 'NEON20',
    'SILICON28', 'ARGON40', 'IRON56',
    'ION_CATALOG',
    'get_ion', 'list_available_ions', 'create_custom_ion',
    'get_ion_display_list',
    # Bethe-Bloch multi-ion
    'bethe_bloch_ion', 's_Al_ion',
    'stopping_power_ion_in_material', 'stopping_power_ion_simple'
]
