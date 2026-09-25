"""Root Vercel entrypoint for RiskSure.

The backend directory is added to sys.path because backend/app.py uses
project-local imports such as database, models, and integrations.
"""
import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.app import app
