"""Performance budget enforcement stub — ADR-023.

Per ADR-023 §2: this script prints the authoritative v0.2 performance budgets
from `pyproject.toml` `[tool.nucleus.perf_budgets]` and exits 0.  Actual
benchmark measurements are NOT automated in v0.2 (deferred to v0.3 when a
stable benchmark harness + nightly runner are available).

Architecture ref: nucleus_architecture_v4.1.md §16 (performance targets).
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


def _load_budgets(repo_root: Path) -> dict[str, object]:
    pyproject_path = repo_root / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    tool_nucleus = data.get("tool", {}).get("nucleus", {})
    return dict(tool_nucleus.get("perf_budgets", {}))


_DEFAULT_BUDGETS: dict[str, str] = {
    "boot_p95_s": "10",
    "materialize_1gb_p95_s": "60",
    "duckdb_query_100m_p95_s": "2",
    "ingest_postgres_1m_rows_p95_s": "120",
    "sql_resolver_p95_ms": "50",
    "workbench_ttfb_p95_ms": "200",
    "ai_copilot_ttfb_p95_s": "3",
    "governance_scripts_total_p95_s": "30",
    "idle_ram_mb": "200",
}


def main() -> int:
    repo_root = Path(__file__).parent.parent
    overrides = _load_budgets(repo_root)
    budgets = {**_DEFAULT_BUDGETS, **overrides}

    print("=" * 68)
    print(" Nucleus v0.2 Performance Budgets (ADR-023 §2)")
    print(" Status: aspirational (nightly-unverified — automation deferred v0.3)")
    print("=" * 68)
    col = max(len(k) for k in budgets)
    for key, value in sorted(budgets.items()):
        print(f"  {key:<{col}}  {value}")
    print()
    print("EXIT 0 — stub only; manual runs required at release per AGENTS.md §11.13.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
