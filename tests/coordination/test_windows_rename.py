"""Tests for Windows rename atomicity documentation and os.replace usage.

Per ``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-4.

On Windows, ``os.rename()`` is NOT guaranteed to be atomic across a crash
(unlike POSIX ``rename(2)``).  Nucleus replaces all filesystem rename
operations with ``os.replace()`` which is atomic on both POSIX and Windows
as of Python 3.3+ (PEP 428).

Docs:
    https://docs.python.org/3/library/os.html#os.replace
    https://docs.python.org/3/library/pathlib.html#pathlib.Path.replace

Coverage:
    R1  os.replace is available on this platform.
    R2  os.replace succeeds when target already exists (unlike os.rename on Windows).
    R3  os.replace on a non-existent source raises FileNotFoundError.
    R4  No nucleus coordination source files use os.rename (vocabulary check).
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

import pytest

IS_WINDOWS = platform.system() == "Windows"


# ---------------------------------------------------------------------------
# R1: os.replace availability
# ---------------------------------------------------------------------------


def test_os_replace_is_available() -> None:
    """R1: os.replace exists on all supported platforms (Python 3.3+)."""
    assert hasattr(os, "replace"), "os.replace must exist (Python 3.3+)"


# ---------------------------------------------------------------------------
# R2: os.replace overwrites existing target atomically
# ---------------------------------------------------------------------------


def test_os_replace_overwrites_existing_target(tmp_path: Path) -> None:
    """R2: os.replace succeeds when the target file already exists.

    On Windows, ``os.rename()`` raises ``FileExistsError`` if the target
    exists.  ``os.replace()`` handles this atomically on both platforms.
    """
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("new content", encoding="utf-8")
    dst.write_text("old content", encoding="utf-8")

    os.replace(str(src), str(dst))

    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "new content"


# ---------------------------------------------------------------------------
# R3: os.replace raises FileNotFoundError for missing source
# ---------------------------------------------------------------------------


def test_os_replace_raises_for_missing_source(tmp_path: Path) -> None:
    """R3: os.replace raises FileNotFoundError when the source does not exist."""
    with pytest.raises(FileNotFoundError):
        os.replace(str(tmp_path / "nonexistent.txt"), str(tmp_path / "dst.txt"))


# ---------------------------------------------------------------------------
# R4: No os.rename in nucleus coordination source
# ---------------------------------------------------------------------------


def test_no_os_rename_in_coordination_source() -> None:
    """R4: Nucleus coordination sources do not use os.rename().

    os.rename() is NOT atomic on Windows when the target already exists.
    All rename operations must use os.replace() (Python 3.3+, cross-platform
    atomic).  This test scans the coordination source directory for violations.

    Per ADR-024 P0-4.
    Docs: https://docs.python.org/3/library/os.html#os.replace
    """
    import re
    from pathlib import Path as _Path

    coordination_dir = _Path(__file__).parent.parent.parent / "src" / "nucleus" / "coordination"
    violations = []
    pattern = re.compile(r"\bos\.rename\s*\(")

    for py_file in coordination_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                violations.append(
                    f"{py_file.relative_to(coordination_dir)}:{lineno}: {line.strip()}"
                )

    assert not violations, (
        "Found os.rename() usage in coordination source (use os.replace()):\n"
        + "\n".join(violations)
    )
