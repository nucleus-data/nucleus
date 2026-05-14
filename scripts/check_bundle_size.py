"""CI gate: initial Workbench JS bundle (gzip) must stay under budget.

Per ``docs/decisions/ADR-016-workbench-mvp.md`` §Compliance / §Consequences
(bundle-size discipline).

Scaffold behavior: an empty ``static/`` dir (only ``.gitkeep``) exits 0.
"""

from __future__ import annotations

import gzip
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATIC = REPO / "src" / "nucleus" / "workbench" / "static"
BUDGET_BYTES = 500 * 1024


def _gzip_size(path: Path) -> int:
    data = path.read_bytes()
    return len(gzip.compress(data))


def main() -> int:
    if not STATIC.exists():
        print("OK: bundle dir missing (scaffold pre-build)")
        return 0

    js_files = sorted(STATIC.rglob("*.js"))
    if not js_files:
        print("OK: bundle is empty (scaffold pre-build)")
        return 0

    total = 0
    rows: list[tuple[str, int]] = []
    for f in js_files:
        gz = _gzip_size(f)
        total += gz
        rows.append((f.relative_to(REPO).as_posix(), gz))

    if total > BUDGET_BYTES:
        print(f"FAIL: gzipped JS total {total} B exceeds budget {BUDGET_BYTES} B")
        for path, sz in rows:
            print(f"  {path}: {sz} B (gzip)")
        return 1

    print(f"OK: gzipped JS total {total} B (budget {BUDGET_BYTES} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
