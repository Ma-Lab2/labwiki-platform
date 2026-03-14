"""
Configuration constants for RCF Stack Spectrometer Design

Author: Tan Song
"""

# Material densities (g/cm³)
DENSITY_AL = 2.702
DENSITY_CU = 8.92
DENSITY_CR = 1.32  # Approximate for Cr-39

# RCF detector structure parameters
EBT1_LAYERS = 125  # Number of layers in EBT1 protective coating
EBT2_LAYERS = 30   # Number of layers in EBT2 active layer
EBT2_CUTOFF_LAYER = 29  # Maximum layer for valid detection

HD1_LAYERS = 8     # Number of layers in HD1 active layer
HD1_CUTOFF_LAYER = 7  # Maximum layer for valid detection
HD2_LAYERS = 97    # Number of layers in HD2 backing

# Default thicknesses (μm)
DEFAULT_AL_THICKNESS = 30
DEFAULT_HD_THICKNESS = 105
DEFAULT_EBT_THICKNESS = 280

# Energy scan defaults
DEFAULT_ENERGY_MIN = 0.5  # MeV
DEFAULT_ENERGY_MAX = 100.0  # MeV
DEFAULT_ENERGY_STEP = 0.1  # MeV

# Linear design defaults
DEFAULT_AL_MIN = 0.0
DEFAULT_AL_MAX = 1000.0
DEFAULT_AL_INTERVAL = 1.0

# Matplotlib font settings
PLOT_FONTS = ['SimHei', 'DejaVu Sans', 'Microsoft YaHei', 'Arial Unicode MS']

# File formats
SUPPORTED_SAVE_FORMATS = ['*.txt', '*.json']

# ============================================================================
# 多离子支持配置 (Multi-Ion Support Configuration)
# ============================================================================

# 默认离子类型
DEFAULT_ION = 'proton'

# GUI 中显示的离子列表 (display_name, ion_key)
ION_GUI_LIST = [
    ('质子 (proton)', 'proton'),
    ('氘核 (deuteron)', 'deuteron'),
    ('α粒子 (He4)', 'He4'),
    ('碳-12 (C12)', 'C12'),
    ('氮-14 (N14)', 'N14'),
    ('氧-16 (O16)', 'O16'),
    ('氖-20 (Ne20)', 'Ne20'),
    ('硅-28 (Si28)', 'Si28'),
    ('氩-40 (Ar40)', 'Ar40'),
    ('铁-56 (Fe56)', 'Fe56'),
]

# 能量范围 (MeV/u) - 不同离子的建议能量范围
ION_ENERGY_RANGES = {
    'proton': (0.5, 200.0),      # 质子: 0.5-200 MeV
    'deuteron': (0.5, 150.0),    # 氘核: 0.5-150 MeV/u
    'He4': (0.5, 150.0),         # α粒子: 0.5-150 MeV/u
    'C12': (1.0, 400.0),         # 碳离子: 1-400 MeV/u (医疗常用: 100-430 MeV/u)
    'N14': (1.0, 400.0),         # 氮离子
    'O16': (1.0, 400.0),         # 氧离子
    'Ne20': (1.0, 400.0),        # 氖离子
    'Si28': (1.0, 500.0),        # 硅离子
    'Ar40': (1.0, 500.0),        # 氩离子
    'Fe56': (1.0, 1000.0),       # 铁离子 (宇宙射线研究)
}

# 物理常数
ELECTRON_MASS_MEV = 0.511  # MeV/c²
PROTON_MASS_MEV = 938.272  # MeV/c²
AMU_MEV = 931.494  # 原子质量单位 MeV/c²
FINE_STRUCTURE_CONSTANT = 1/137.036

# 材料平均激发能 (eV) - 用于 Bethe-Bloch 公式
MEAN_EXCITATION_ENERGIES = {
    'Al': 166.0,
    'Cu': 322.0,
    'Cr': 257.0,
    'Fe': 286.0,
    'Ti': 233.0,
    'Pb': 823.0,
    'W': 727.0,
    'Au': 790.0,
    'Ag': 470.0,
    'Si': 173.0,
    'Be': 63.7,
    'Mylar': 78.7,
    'Kapton': 79.6,
    'Water': 75.0,
    'Polyethylene': 57.4,
    'PMMA': 74.0,
    'Polystyrene': 68.7,
    'Air': 85.7,
}

