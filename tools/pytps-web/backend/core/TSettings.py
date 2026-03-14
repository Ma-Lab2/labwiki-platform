import numpy as np
import os
from . import CustomColormaps


class TPS(object):
    def __init__(self, settings_path=None):
        if settings_path is None:
            settings_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'TPS_Settings.ini')
        data = np.genfromtxt(settings_path, delimiter='\t', encoding='utf-8')
        data = data[..., 1]
        self.B = data[0]
        self.U = data[1]
        self.EMGain = data[2]
        self.S1 = data[3]
        self.Res = data[4]
        self.L = data[5]
        self.D = data[6]
        self.L1 = data[7]
        self.L2 = data[8]
        self.L3 = data[9]
        self.theta = data[10]
        self.d = data[11]
        self.D1 = data[12]
        self.L0 = data[13]
        self.QE = data[14]

    def to_dict(self):
        return {
            'B': self.B, 'U': self.U, 'EMGain': self.EMGain,
            'S1': self.S1, 'Res': self.Res, 'L': self.L,
            'D': self.D, 'L1': self.L1, 'L2': self.L2,
            'L3': self.L3, 'theta': self.theta, 'd': self.d,
            'D1': self.D1, 'L0': self.L0, 'QE': self.QE
        }

    @classmethod
    def from_dict(cls, d, settings_path=None):
        """Create a TPS instance from a dict (for updating params via API)"""
        obj = cls.__new__(cls)
        for key in ['B', 'U', 'EMGain', 'S1', 'Res', 'L', 'D',
                     'L1', 'L2', 'L3', 'theta', 'd', 'D1', 'L0', 'QE']:
            setattr(obj, key, d[key])
        return obj


def LoadMCPData(path):
    MCPdata = np.genfromtxt(path, delimiter='\t', encoding='utf-8')
    return MCPdata


def TPSinit(init_path=None):
    """
    Load application parameters from PyTPS_init.ini.
    Returns a dict instead of modifying an app object.
    """
    if init_path is None:
        init_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'PyTPS_init.ini')

    path_data = np.genfromtxt(init_path, delimiter='\t', dtype=str, encoding='utf-8')
    float_data = np.genfromtxt(init_path, delimiter='\t', encoding='utf-8')
    int_data = np.genfromtxt(init_path, delimiter='\t', dtype=np.int64, encoding='utf-8')

    params = {}
    params['imagePath'], params['savePath'], params['MCPPath'] = path_data[0:3, 1]
    params['X0'], params['Y0'], params['dY'], params['colormin'], params['colormax'] = \
        int(int_data[3, 1]), int(int_data[4, 1]), int(int_data[5, 1]), int(int_data[6, 1]), int(int_data[7, 1])
    params['Emin'], params['Emax'] = float(float_data[8, 1]), float(float_data[9, 1])
    params['specEmin'], params['specEmax'] = float(float_data[10, 1]), float(float_data[11, 1])
    params['specdNdEmin'], params['specdNdEmax'] = float(float_data[12, 1]), float(float_data[13, 1])
    params['specWindow'] = float(float_data[14, 1])

    # Filter configuration
    params['filterMode'] = path_data[15, 1]
    params['medianSize'] = int(int_data[16, 1])
    params['medianIterations'] = int(int_data[17, 1])
    params['morphologicalSize'] = int(int_data[18, 1])
    params['rollingBallRadius'] = int(int_data[19, 1])
    params['protectionWidth'] = int(int_data[20, 1])
    params['aggressiveSize'] = int(int_data[21, 1])
    params['gentleSize'] = int(int_data[22, 1])

    try:
        params['fadeRadius'] = int(int_data[23, 1])
    except IndexError:
        params['fadeRadius'] = 20

    return params


def getList(image_path):
    """Return list of image files in directory."""
    if not os.path.isdir(image_path):
        return []
    file_list = os.listdir(image_path)
    image_extensions = ('.tif', '.tiff', '.jpg', '.png', '.raw')
    return [f for f in file_list if f.lower().endswith(image_extensions)]


def particleList():
    """Return list of particle options."""
    return [
        {"name": "H-1", "A": 1, "Z": 1},
        {"name": "C-6", "A": 12, "Z": 6},
        {"name": "O-8", "A": 16, "Z": 8},
        {"name": "O-7", "A": 16, "Z": 7},
        {"name": "C-5", "A": 12, "Z": 5},
        {"name": "O-6", "A": 16, "Z": 6},
        {"name": "C-4", "A": 12, "Z": 4},
        {"name": "O-5", "A": 16, "Z": 5},
        {"name": "C-3", "A": 12, "Z": 3},
        {"name": "O-4", "A": 16, "Z": 4},
        {"name": "C-2", "A": 12, "Z": 2},
        {"name": "C-1", "A": 12, "Z": 1},
    ]


def colormapList():
    """Return list of available colormap names."""
    return [
        "partical", "field", "jet", "hsv", "hot", "cool", "gray",
        "spring", "summer", "autumn", "winter", "bone", "pink", "copper"
    ]
