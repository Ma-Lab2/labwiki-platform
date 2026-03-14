"""
config.py - Environment variable configuration.
"""

import os

DATA_DIR = os.environ.get("PYTPS_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
IMAGE_DIR = os.environ.get("PYTPS_IMAGE_DIR", "/data/images")
OUTPUT_DIR = os.environ.get("PYTPS_OUTPUT_DIR", "/data/output")
WORKERS = int(os.environ.get("PYTPS_WORKERS", "4"))
SESSION_MAX_AGE = int(os.environ.get("PYTPS_SESSION_MAX_AGE", "3600"))
