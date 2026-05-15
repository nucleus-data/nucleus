"""Forbid ``os.rename(`` and ``Path.rename(`` calls inside ``src/nucleus/``.

Per ``docs/research/performance_reliability_targets.md`` §10 item #5 +
``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-4.

Why
---
POSIX ``rename(2)`` (https://man7.org/linux/man-pages/man2/rename.2.html) is
atomic: a successful call leaves either the old or new state on disk, never
a partial state, even across a power cut. NTFS rename is NOT atomic in the
same sense — when the target already exists, Windows performs a
delete-then-rename that can leave a torn intermediate state if the process
dies between the two steps. Python wraps both behaviours in the same
function, so the same source code is safe on Linux/macOS and unsafe on
Windows.

The cross-platform safe choice (Python 3.3+, PEP 428
https://peps.python.org/pep-0428/) is the ``replace`` family:

* On POSIX it calls ``rename(2)`` (atomic).
* On Windows it calls ``MoveFileEx`` with ``MOVEFILE_REPLACE_EXISTING``
  (https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexa),
  which is documented as a single-volume atomic operation.

Docs:
    https://docs.python.org/3.11/library/os.html#os.replace
    https://docs.python.org/3.11/library/pathlib.html#pathlib.Path.replace

Detection strategy
------------------
We walk the Python AST (``ast.parse`` → ``ast.walk``) and only flag
``ast.Call`` nodes whose ``func`` is one of:

* ``ast.Attribute`` with ``attr == "rename"`` and ``value.id == "os"``
  → matches ``os.rename(...)``.
* ``ast.Attribute`` with ``attr == "rename"`` and the receiver is a
  ``Path``-typed expression (``Path(...).rename``, ``foo_path.rename``,
  ``self.path.rename``, ``lockfile.rename``, etc.).

This is bulletproof against the regex false-positives that hit docstring
literals and string-format helpers. Tests in ``tests/`` are out of scope:
they exercise the dangerous APIs deliberately.

Scope
-----
We scan ``src/nucleus/**.py`` only. Third-party deps (e.g. ``pyiceberg``
inside ``.venv/``) are out of scope; Worker B1's audit
(``docs/research/windows_atomicity.md``) confirms ``pyiceberg`` ≥ 0.11
uses pyarrow / SQLite catalog atomicity primitives instead of filesystem
rename.

Usage
-----
    python scripts/check_os_rename.py
    python scripts/check_os_rename.py --json
    python scripts/check_os_rename.py --target src/nucleus
    python scripts/check_os_rename.py --help

Exit codes
----------
    0  clean — zero forbidden rename calls
    1  one or more forbidden calls found
    2  invocation / IO error (target dir missing, unreadable file)
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = REPO_ROOT / "src" / "nucleus"

# Receiver names that almost always denote a filesystem path object.
# A ``rename`` method called on any of these is treated as a forbidden
# filesystem rename. Catalog ``rename_table`` (different attribute name)
# and Iceberg schema ``rename_column`` / ``rename_field`` are unaffected
# because the AST attribute name differs.
_PATH_LIKE_RECEIVER_NAMES: frozenset[str] = frozenset(
    {
        "path",
        "Path",
        "lock_file",
        "lockfile",
        "src",
        "dst",
        "tmp_path",
        "tmpfile",
        "metadata_path",
        "snapshot_path",
        "target",
        "target_path",
        "old_path",
        "new_path",
        "filepath",
        "file_path",
    }
)


@dataclass
class RenameReport:
    """Aggregate report for the rename audit."""

    violations: list[tuple[Path, int, str, str]] = field(default_factory=list)
    files_scanned: int = 0
    target: Path = DEFAULT_TARGET

    @property
    def ok(self) -> bool:
        return not self.violations


def _is_path_like_receiver(node: ast.expr) -> bool:
    """Return True when *node* most likely evaluates to a filesystem path.

    Recognised forms:
      * ``Path("...")`` / ``pathlib.Path("...")``  (a Call returning a Path)
      * ``foo_path``, ``lockfile``, ``self.path``  (Name / Attribute matching
        the conventional names in ``_PATH_LIKE_RECEIVER_NAMES`` or ending
        in ``_path``)

    A bare ``foo.rename()`` whose receiver does NOT match these conventions
    is not flagged — the goal is high precision, low false-positive rate.
    """
    if isinstance(node, ast.Call):
        # Path("..."), pathlib.Path("..."), PurePath("..."), etc.
        func = node.func
        if isinstance(func, ast.Name) and func.id in {
            "Path",
            "PurePath",
            "WindowsPath",
            "PosixPath",
        }:
            return True
        if isinstance(func, ast.Attribute) and func.attr in {
            "Path",
            "PurePath",
            "WindowsPath",
            "PosixPath",
        }:
            return True
        return False

    if isinstance(node, ast.Name):
        if node.id in _PATH_LIKE_RECEIVER_NAMES:
            return True
        if node.id.endswith("_path") or node.id.endswith("_file"):
            return True
        return False

    if isinstance(node, ast.Attribute):
        # self.path, foo.metadata_path, etc.
        if node.attr in _PATH_LIKE_RECEIVER_NAMES:
            return True
        if node.attr.endswith("_path") or node.attr.endswith("_file"):
            return True
        return False

    return False


def _classify(call: ast.Call) -> str | None:
    """Return a short tag if *call* is a forbidden rename, else None."""
    func = call.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr != "rename":
        return None

    # os.rename(...)
    if isinstance(func.value, ast.Name) and func.value.id == "os":
        return "os.rename"

    # Path-like receiver: foo_path.rename(...), Path(...).rename(...), etc.
    if _is_path_like_receiver(func.value):
        return "Path.rename"

    return None


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return ``[(line_no, kind, source_excerpt), …]`` for every hit."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        # Skip files we can't parse — they're already broken; loud governance
        # would mask the real syntax error in CI output.
        print(f"check_os_rename: skipping unparseable {path}: {exc}", file=sys.stderr)
        return []

    source_lines = text.splitlines()
    hits: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _classify(node)
        if kind is None:
            continue
        lineno = node.lineno
        excerpt = source_lines[lineno - 1].rstrip() if 0 < lineno <= len(source_lines) else ""
        hits.append((lineno, kind, excerpt))
    return hits


def scan_target(target: Path) -> RenameReport:
    """Walk *target* recursively and return a :class:`RenameReport`."""
    if not target.exists():
        raise FileNotFoundError(f"target not found: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"target is not a directory: {target}")

    report = RenameReport(target=target)
    for py_file in sorted(target.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        report.files_scanned += 1
        for lineno, kind, content in _scan_file(py_file):
            report.violations.append((py_file, lineno, kind, content))
    return report


def _render(report: RenameReport, target: Path) -> str:
    """Return the human-readable report."""
    lines: list[str] = [
        "os.rename / Path.rename audit",
        "=" * 60,
        f"Target: {target}",
        f"Files scanned: {report.files_scanned}",
        "",
    ]
    if report.ok:
        lines.append("PASS: zero forbidden rename calls in scanned tree.")
        lines.append("")
        lines.append(
            "Use os.replace() or Path.replace() instead --- atomic on POSIX "
            "(rename(2)) and near-atomic on NTFS (MoveFileEx with "
            "MOVEFILE_REPLACE_EXISTING)."
        )
        lines.append("Docs: https://docs.python.org/3.11/library/os.html#os.replace")
        return "\n".join(lines)

    lines.append(f"FAIL: found {len(report.violations)} forbidden call(s).")
    lines.append("")
    lines.append(
        "Migrate each call to os.replace() / Path.replace() (Python 3.3+, cross-platform atomic):"
    )
    lines.append("")
    for path, lineno, kind, content in report.violations:
        rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        lines.append(f"  [{kind}] {rel}:{lineno}: {content}")
    lines.append("")
    lines.append("Why this matters:")
    lines.append("  * POSIX rename(2) is atomic; NTFS rename is NOT.")
    lines.append("  * On Windows os.rename(src, dst) raises FileExistsError if dst exists.")
    lines.append("  * os.replace(src, dst) handles both atomically.")
    lines.append("")
    lines.append(
        "References: docs/research/performance_reliability_targets.md (perf gap #5), "
        "docs/decisions/ADR-024-reliability-hardening-plan.md P0-4, "
        "docs/research/windows_atomicity.md."
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when src/nucleus/ contains os.rename or Path.rename calls "
            "(perf doc gap #5; ADR-024 P0-4)."
        ),
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help=(
            "Directory to scan recursively (default: src/nucleus). "
            "Pass --target src to scan the whole package, --target . to "
            "audit the entire repo."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human report.",
    )
    args = parser.parse_args(argv)

    try:
        report = scan_target(args.target)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"check_os_rename: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"check_os_rename: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "target": str(args.target),
                    "files_scanned": report.files_scanned,
                    "violations": [
                        {
                            "file": str(
                                p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p
                            ),
                            "line": ln,
                            "kind": kind,
                            "content": content,
                        }
                        for p, ln, kind, content in report.violations
                    ],
                },
                indent=2,
            )
        )
    else:
        print(_render(report, args.target))

    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
