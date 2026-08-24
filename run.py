"""
Entry point. Run with:

    python run.py

This regenerates mock data if it doesn't exist yet, then launches the
Streamlit dashboard.
"""

import subprocess
import sys
import os

from src.pipeline import ensure_data_exists


def main():
    ensure_data_exists()
    dashboard_path = os.path.join("src", "ui", "dashboard.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", dashboard_path])


if __name__ == "__main__":
    main()
