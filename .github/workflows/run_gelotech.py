#!/usr/bin/env python3
"""
Launcher for the gelotech package.

Place this file in the parent directory of the 'gelotech' package folder and run:
    python run_gelotech.py

This ensures the package is imported as a package (so relative imports inside
the package work). It is a small convenience wrapper around `python -m gelotech.main`.
"""
import sys
from pathlib import Path

def main(argv=None):
    # Ensure the script is run from the repo root (or at least the parent of the gelotech folder).
    # This helps when users double-click or run the script directly.
    try:
        # Import the package entrypoint
        from gelotech.main import main as gelomain
    except Exception as e:
        print("Failed to import gelotech.main:", e)
        print("Make sure you run this script from the directory that contains the 'gelotech' package folder.")
        raise
    return gelomain(argv)

if __name__ == "__main__":
    sys.exit(main())