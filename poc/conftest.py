"""Pytest config for /internal/poc/ — minimal sibling of tests/conftest.py.

Adds ``src/`` to ``sys.path`` so PoC tests can ``import nucleus.*`` even
without an editable install. Once ``pip install -e .[dev]`` is done, this
is a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
