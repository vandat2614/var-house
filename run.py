"""
Entry point for production deployment (Render, Fly.io, etc.)
Run: uvicorn run:app --host 0.0.0.0 --port \
"""
import sys
import os

# Ensure the project root is in Python path so 'src.*' imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.main import app  # noqa: F401 - exported for uvicorn
