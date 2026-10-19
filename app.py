"""Compatibility entrypoint for the existing Streamlit Cloud configuration.

Streamlit Cloud is configured to launch ``app.py`` from the repository root,
while the application and its relative assets live in ``streamlit/``.
"""

import os
import runpy
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent / "streamlit"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)
runpy.run_path(str(APP_DIR / "app.py"), run_name="__main__")
