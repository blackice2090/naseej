"""Root pytest configuration — adds repo root to sys.path once.

All test subdirectories (backend/tests, ml/tests) inherit this fixture
so their imports of `backend.*` and `ml.*` work without installation.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
