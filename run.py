"""
Production entry point for Render/Fly.io deployment.
Start Command: python run.py
"""
import sys
import os

# Inject project root into Python path BEFORE any src.* imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from src.api.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
