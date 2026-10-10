"""Compatibility entry point for `uvicorn main:app`; prefer backend/app/main.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from app.main import app  # noqa: E402,F401
