"""Streamlit Community Cloud entry point for PhantomPulse saved predictions."""
from pathlib import Path
import runpy

PROJECT = Path(__file__).resolve().parent
runpy.run_path(str(PROJECT / "FULL_CODE" / "dashboard.py"), run_name="__main__")
