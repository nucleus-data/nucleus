"""Benchmark regression check — AGENTS.md §11.13.

Compares the latest benchmark run against a recorded baseline. CI fails
the dep-upgrade PR if any tracked metric drifts more than ±10%
(configurable via ``--tolerance``). Addresses
``nucleus_architecture_v4.1.md`` §19 risk-register rows #2 (DuckDB Labs
pivot — perf regression is the signal to consider DataFusion swap), #8
(Error Translation feasibility) and #11 (composability drift).

Fixtures live under ``tests/upgrade_smoke/`` per ``AGENTS.md`` §11.13:
``baseline.json`` (last known-good) and ``current.json`` (latest run).
Neither exists yet — this is a **SKELETON**. The first real baseline
is recorded post-PoC #1 promotion (``AGENTS.md`` §11.1).

Expected JSON shape (both files)::

    {"version": 1, "recorded_at": "...",
     "metrics": {"duckdb_aggregation_100m_rows_s":
                     {"value": 1.8, "direction": "negative"}, ...}}

``direction``: ``negative`` = lower is better (latency/RAM; growing
past +tol% fails); ``positive`` = higher is better (throughput;
falling past -tol% fails).

Usage:  ``python scripts/benchmark_regression.py``
        ``[--baseline X --current Y] [--tolerance PCT] [--dry-run | --record] [--json]``
Exit:   0 PASS (or skeleton), 1 FAIL (regression), 2 INCOMPLETE (missing/malformed).
Stdlib only — argparse, dataclasses, json, pathlib, sys.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = REPO_ROOT / "tests" / "upgrade_smoke" / "baseline.json"
DEFAULT_CURRENT = REPO_ROOT / "tests" / "upgrade_smoke" / "current.json"
DEFAULT_TOLERANCE_PCT = 10.0


@dataclass
class Regression:
    metric: str
    baseline: float
    current: float
    delta_pct: float
    direction: str
    reason: str


def _load_metrics(path: Path) -> dict[str, dict[str, Any]]:
    """Parse a benchmark JSON file and return its ``metrics`` mapping."""
    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("metrics"), dict):
        raise ValueError(f"{path}: top-level 'metrics' object missing")
    metrics: dict[str, dict[str, Any]] = {}
    for key, entry in raw["metrics"].items():
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: metric '{key}' must be an object")
        metrics[str(key)] = dict(entry)
    return metrics


def _compare(
    baseline: dict[str, dict[str, Any]], current: dict[str, dict[str, Any]], tolerance_pct: float,
) -> tuple[list[Regression], list[str]]:
    """Return ``(regressions, missing_or_malformed)`` for the two fixture sets."""
    regressions: list[Regression] = []
    issues: list[str] = []
    for metric, base_entry in baseline.items():
        if metric not in current:
            issues.append(f"{metric}: missing in current")
            continue
        try:
            base_v = float(base_entry["value"])
            cur_v = float(current[metric]["value"])
        except (KeyError, TypeError, ValueError):
            issues.append(f"{metric}: malformed value")
            continue
        direction = str(base_entry.get("direction", "negative")).lower()
        if direction not in ("positive", "negative"):
            issues.append(f"{metric}: unknown direction '{direction}'")
            continue
        delta_pct = 0.0 if base_v == 0 and cur_v == 0 else (
            float("inf") if base_v == 0 else (cur_v - base_v) / base_v * 100.0
        )
        regressed = (
            (direction == "negative" and delta_pct > tolerance_pct)
            or (direction == "positive" and delta_pct < -tolerance_pct)
        )
        if regressed:
            verb = "grew" if direction == "negative" else "fell"
            bound = f"+{tolerance_pct:.0f}%" if direction == "negative" else f"-{tolerance_pct:.0f}%"
            regressions.append(Regression(
                metric=metric, baseline=base_v, current=cur_v, delta_pct=delta_pct,
                direction=direction,
                reason=f"{direction}-direction metric {verb} {delta_pct:+.1f}% past {bound}",
            ))
    return regressions, issues


def _render(
    regressions: list[Regression], issues: list[str],
    baseline_path: Path, current_path: Path, tolerance_pct: float,
) -> str:
    lines = ["=" * 72, "Benchmark Regression Check", "=" * 72,
             f" baseline : {baseline_path}", f" current  : {current_path}",
             f" tolerance: \u00b1{tolerance_pct:.0f}%", ""]
    if regressions:
        lines.append(f"REGRESSIONS ({len(regressions)}):")
        lines.extend(
            f"  {r.metric}: {r.baseline:.4g} -> {r.current:.4g}  "
            f"({r.delta_pct:+.2f}%, {r.direction}) — {r.reason}"
            for r in regressions
        )
    else:
        lines.append("No regressions within tolerance.")
    if issues:
        lines.append("")
        lines.append("Missing / malformed metrics:")
        lines.extend(f"  - {m}" for m in issues)
    lines.append("=" * 72)
    return "\n".join(lines)


def _emit_incomplete(reason: str, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps({"ok": False, "verdict": "INCOMPLETE", "reason": reason}, indent=2))
    else:
        print(f"Benchmark regression check: INCOMPLETE — {reason}", file=sys.stderr)
    return 2


def _print_skeleton(baseline: Path, current: Path, *, as_json: bool) -> int:
    payload: dict[str, Any] = {
        "ok": True, "verdict": "SKELETON",
        "baseline": str(baseline), "current": str(current),
        "hint": "no baseline yet; record one with `--record` once a real benchmark harness lands post-PoC #1",
    }
    if as_json:
        print(json.dumps(payload, indent=2))
        return 0
    print(
        "Benchmark regression check: SKELETON MODE\n"
        f"  baseline : {baseline}  ({'exists' if baseline.exists() else 'not found'})\n"
        f"  current  : {current}  ({'exists' if current.exists() else 'not found'})\n"
        "\nNo benchmark fixtures exist yet; first real run lands post-PoC #1 promotion.\n"
        "Per AGENTS.md §11.13: record a baseline with `--record` once a real benchmark\n"
        "harness populates tests/upgrade_smoke/current.json. Risk register: \n"
        "nucleus_architecture_v4.1.md §19 (rows #2, #8, #11)."
    )
    return 0


def _cmd_record(baseline: Path, current: Path, *, as_json: bool) -> int:
    if not current.exists():
        return _emit_incomplete(f"--record failed: current file missing ({current})", as_json=as_json)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text(current.read_text(encoding="utf-8"), encoding="utf-8")
    if as_json:
        print(json.dumps({"ok": True, "verdict": "RECORDED",
                          "baseline": str(baseline), "from": str(current)}, indent=2))
    else:
        print(f"Recorded new baseline: {baseline} (overwrote previous if any).")
        print("Per AGENTS.md §11.13: include changelog summary + rollback command in the upgrade PR.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark regression check (AGENTS.md §11.13).")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE,
                        help=f"baseline metrics JSON (default: {DEFAULT_BASELINE.relative_to(REPO_ROOT)})")
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT,
                        help=f"current-run metrics JSON (default: {DEFAULT_CURRENT.relative_to(REPO_ROOT)})")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE_PCT,
                        help="\u00b1%% allowed before flagging regression (default 10).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Force skeleton output; never read fixtures.")
    parser.add_argument("--record", action="store_true",
                        help="Copy --current onto --baseline (intentional perf change).")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    args = parser.parse_args(argv)

    if args.record:
        return _cmd_record(args.baseline, args.current, as_json=args.json)
    if args.dry_run or not args.baseline.exists():
        return _print_skeleton(args.baseline, args.current, as_json=args.json)
    if not args.current.exists():
        return _emit_incomplete(f"current file missing: {args.current}", as_json=args.json)
    try:
        base = _load_metrics(args.baseline)
        cur = _load_metrics(args.current)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _emit_incomplete(f"parse error: {type(exc).__name__}: {exc}", as_json=args.json)

    regressions, issues = _compare(base, cur, args.tolerance)
    if args.json:
        print(json.dumps({
            "ok": not regressions, "verdict": "FAIL" if regressions else "PASS",
            "tolerance_pct": args.tolerance,
            "regressions": [asdict(r) for r in regressions], "issues": issues,
        }, indent=2))
    else:
        print(_render(regressions, issues, args.baseline, args.current, args.tolerance))
    return 1 if regressions else 0


if __name__ == "__main__":
    sys.exit(main())
