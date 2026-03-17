# tests/conftest.py
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so imports like `backend.app` work
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Optional: set environment variables used by the app during tests
os.environ.setdefault("LOG_DIR", str(ROOT / "logs"))
