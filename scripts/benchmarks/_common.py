"""Shared utilities for the Nucleus empirical benchmark suite.

This module contains:

* ``hardware_specs()`` — cross-platform machine snapshot (CPU, RAM, OS).
* ``software_versions()`` — wrapped-library versions read from importable modules.
* ``RSSWatcher`` — background thread that samples ``psutil.Process().memory_info().rss``.
* ``BenchResult`` / ``BenchRow`` — JSON-serialisable records consumed by ``run_all.py``.
* ``write_result()`` — atomic JSON writer to ``docs/benchmarks/_results/``.
* ``percentile()`` — small stdlib percentile helper (avoids numpy dep).
* ``Verdict`` constants and ``classify()`` to keep severity logic in one place.

Anti-fakery: every measured number is captured exactly as observed — there
is no smoothing, retry-until-pass, or claim-tuning logic in this file.
Per the task spec: real numbers, even when they fail.

Docs:
    psutil 7.2.2 — https://psutil.readthedocs.io/en/latest/
    Python platform module — https://docs.python.org/3/library/platform.html
    Python statistics module — https://docs.python.org/3/library/statistics.html
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import statistics
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent
RESULTS_DIR: Path = REPO_ROOT / "docs" / "benchmarks" / "_results"

# Verdict constants — keep the markdown report consistent with the JSON schema.
PASS = "PASS"
FAIL = "FAIL"
SKIP_DEPS = "SKIP-DEPS"
NEEDS_INVESTIGATION = "NEEDS-INVESTIGATION"

# Severity levels — used when verdict != PASS to tell the founder how loudly to escalate.
BLOCKER = "BLOCKER"
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"

# Wrapped libraries we want to record per perf doc §References + AGENTS.md §11.13.
_WRAPPED_LIBS: tuple[str, ...] = (
    "duckdb",
    "polars",
    "pyarrow",
    "pyiceberg",
    "psutil",
    "dagster",
    "psycopg",
    "sqlalchemy",
    "dlt",
    "fastapi",
    "uvicorn",
    "litellm",
    "nucleus",
)


@dataclass
class BenchRow:
    """A single (metric, claim, measured, verdict) row in the report table."""

    metric: str
    claim_ref: str  # e.g. "perf doc §2.1"
    claim: str  # human-readable, e.g. "<500ms cold"
    measured: str  # human-readable, e.g. "412ms"
    verdict: str  # PASS / FAIL / SKIP-DEPS / NEEDS-INVESTIGATION
    delta: str = ""  # human-readable, e.g. "-17.6%" or "+312% over claim"
    severity: str = ""  # BLOCKER / HIGH / MEDIUM / LOW (only set when not PASS)
    note: str = ""  # optional one-liner with extra context


@dataclass
class BenchResult:
    """A full benchmark's output — one JSON file per script."""

    name: str  # e.g. "B5: Boot time"
    script: str  # e.g. "scripts/benchmarks/b5_boot_time.py"
    command: str  # exact command line a user can re-run
    started_at: str  # ISO-8601 UTC
    completed_at: str  # ISO-8601 UTC
    elapsed_s: float
    overall_verdict: str  # PASS / FAIL / SKIP-DEPS / NEEDS-INVESTIGATION
    rows: list[BenchRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)  # opt-in extras (per-query times, etc.)


def hardware_specs() -> dict[str, Any]:
    """Return CPU/RAM/OS snapshot for the current host.

    Wraps ``platform.platform()`` + ``psutil.cpu_count()`` +
    ``psutil.virtual_memory()`` (per task spec). Lazy-imports ``psutil`` so
    the module stays usable even on a CI worker without dev deps installed.

    Docs: https://docs.python.org/3/library/platform.html
    Docs: https://psutil.readthedocs.io/en/latest/#psutil.cpu_count
    """
    try:
        import psutil

        physical = psutil.cpu_count(logical=False)
        logical = psutil.cpu_count(logical=True)
        ram_total_gb = round(psutil.virtual_memory().total / 1024**3, 1)
        ram_avail_gb = round(psutil.virtual_memory().available / 1024**3, 1)
        return {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "physical_cores": physical,
            "logical_cores": logical,
            "ram_total_gb": ram_total_gb,
            "ram_available_gb": ram_avail_gb,
        }
    except ImportError:
        return {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "physical_cores": os.cpu_count(),
            "logical_cores": os.cpu_count(),
            "ram_total_gb": None,
            "ram_available_gb": None,
            "note": "psutil unavailable — install nucleus[dev] for full specs.",
        }


def software_versions() -> dict[str, str]:
    """Return wrapped-library versions via ``importlib.metadata``.

    Falls back to module ``__version__`` when ``importlib.metadata`` cannot
    locate the dist (rare; happens for editable installs + namespace packages).
    Returns ``"missing"`` for libs that aren't importable.

    Docs: https://docs.python.org/3/library/importlib.metadata.html
    """
    out: dict[str, str] = {}
    for name in _WRAPPED_LIBS:
        try:
            out[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            try:
                mod = importlib.import_module(name)
                out[name] = getattr(mod, "__version__", "unknown")
            except ImportError:
                out[name] = "missing"
    return out


def percentile(values: list[float], pct: float) -> float:
    """Compute a single percentile using stdlib only (no numpy dep).

    ``pct`` is in ``[0, 100]``. Empty input returns ``float('nan')`` so the
    caller can tell the suite ran zero samples (edge case worth surfacing,
    not a fake zero).
    """
    if not values:
        return float("nan")
    if len(values) == 1:
        return float(values[0])
    sorted_vs = sorted(values)
    # Use the same boundary as numpy's "linear" interpolation default
    # (https://numpy.org/doc/stable/reference/generated/numpy.percentile.html)
    # so cross-checks against numpy/pandas produce identical numbers.
    rank = (pct / 100.0) * (len(sorted_vs) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_vs) - 1)
    frac = rank - low
    return sorted_vs[low] * (1 - frac) + sorted_vs[high] * frac


def stats_summary(values: list[float]) -> dict[str, float]:
    """Return ``min/median/p95/p99/max`` for a list of float samples."""
    if not values:
        return {
            "min": float("nan"),
            "median": float("nan"),
            "p95": float("nan"),
            "p99": float("nan"),
            "max": float("nan"),
        }
    return {
        "min": float(min(values)),
        "median": float(statistics.median(values)),
        "p95": percentile(values, 95.0),
        "p99": percentile(values, 99.0),
        "max": float(max(values)),
    }


class RSSWatcher:
    """Background thread that samples ``psutil.Process().memory_info().rss``.

    Tracks the maximum observed RSS across the watched lifespan. Used by the
    materialize / ingest benchmarks to capture peak memory without relying on
    OS-specific ``getrusage`` quirks.

    Docs: https://psutil.readthedocs.io/en/latest/#psutil.Process.memory_info

    Usage::

        watcher = RSSWatcher().start()
        try:
            heavy_work()
        finally:
            peak_bytes = watcher.stop()
    """

    def __init__(self, interval_s: float = 0.05, target_pid: int | None = None) -> None:
        self.interval_s = interval_s
        self.target_pid = target_pid if target_pid is not None else os.getpid()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._peak_bytes = 0
        self._sample_count = 0

    def _run(self) -> None:
        try:
            import psutil

            proc = psutil.Process(self.target_pid)
        except (ImportError, Exception):
            return
        # Sample once immediately so even a sub-millisecond span produces a number.
        try:
            self._peak_bytes = max(self._peak_bytes, int(proc.memory_info().rss))
            self._sample_count += 1
        except Exception:
            return
        while not self._stop_event.wait(self.interval_s):
            try:
                rss = int(proc.memory_info().rss)
            except Exception:
                break
            self._peak_bytes = max(self._peak_bytes, rss)
            self._sample_count += 1

    def start(self) -> RSSWatcher:
        """Spawn the sampler thread; returns self for chaining."""
        self._thread = threading.Thread(target=self._run, daemon=True, name="rss-watcher")
        self._thread.start()
        return self

    def stop(self) -> int:
        """Stop sampling; return the peak RSS in bytes."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        return self._peak_bytes

    @property
    def sample_count(self) -> int:
        return self._sample_count


def now_iso() -> str:
    """ISO-8601 UTC timestamp; trims microseconds for readability."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_result(result: BenchResult) -> Path:
    """Atomic-write a ``BenchResult`` to ``docs/benchmarks/_results/<name>.json``.

    The orchestrator (``run_all.py``) reads these files; per-script callers
    don't need to know the path layout.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    safe = result.script.split("/")[-1].replace(".py", "")
    path = RESULTS_DIR / f"{safe}.json"
    payload = {
        "schema_version": 1,
        "result": asdict(result),
        "hardware": hardware_specs(),
        "software": software_versions(),
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path


def fmt_seconds(s: float) -> str:
    """Human-readable seconds with units appropriate to magnitude."""
    if s != s:  # noqa: PLR0124  # intentional NaN check (nan != nan == True)
        return "n/a"
    if s < 1.0:
        return f"{s * 1000:.1f}ms"
    if s < 60.0:
        return f"{s:.2f}s"
    return f"{s / 60.0:.2f}min"


def fmt_bytes(b: float) -> str:
    """Human-readable bytes with units (KB/MB/GB)."""
    if b != b:  # noqa: PLR0124  # intentional NaN check (nan != nan == True)
        return "n/a"
    if b < 1024:
        return f"{b:.0f}B"
    if b < 1024**2:
        return f"{b / 1024:.1f}KB"
    if b < 1024**3:
        return f"{b / 1024**2:.1f}MB"
    return f"{b / 1024**3:.2f}GB"


def delta_pct(measured: float, claim_value: float) -> float | None:
    """Percentage delta vs claim. Returns None when claim is zero/NaN."""
    if claim_value is None or claim_value != claim_value or claim_value == 0:  # noqa: PLR0124  # intentional NaN check (nan != nan == True)
        return None
    return (measured - claim_value) / claim_value * 100.0


def fmt_delta(measured: float, claim_value: float) -> str:
    """Render a +/- percentage with a one-letter sign hint."""
    pct = delta_pct(measured, claim_value)
    if pct is None:
        return "n/a"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def classify(measured: float, claim_value: float, *, lower_is_better: bool = True) -> str:
    """Return PASS / FAIL based on whether measured violates claim_value.

    ``lower_is_better=True`` for latency / RAM (FAIL when measured > claim).
    ``lower_is_better=False`` for throughput (FAIL when measured < claim).
    """
    if claim_value is None or claim_value != claim_value:  # noqa: PLR0124  # intentional NaN check (nan != nan == True)
        return NEEDS_INVESTIGATION
    if lower_is_better:
        return PASS if measured <= claim_value else FAIL
    return PASS if measured >= claim_value else FAIL


def severity_for(measured: float, claim_value: float, *, lower_is_better: bool = True) -> str:
    """Map the percentage overshoot to a severity tag.

    Heuristic: <50% over claim = LOW, 50-100% = MEDIUM, 100-200% = HIGH,
    >200% = BLOCKER. Per the task spec the founder needs the severity to
    tell which finding to escalate first.
    """
    pct = delta_pct(measured, claim_value)
    if pct is None:
        return MEDIUM
    overshoot = pct if lower_is_better else -pct
    if overshoot < 50:
        return LOW
    if overshoot < 100:
        return MEDIUM
    if overshoot < 200:
        return HIGH
    return BLOCKER


def proxy_blocked(url: str, *, timeout_s: float = 3.0) -> tuple[bool, str]:
    """Return ``(True, reason)`` when the URL is unreachable (proxy / DNS / 4xx).

    Used by B1 to decide whether to attempt the DuckDB TPC-H extension download
    or short-circuit to SKIP-DEPS with a clear message. Per the task spec we
    must surface infrastructure gaps explicitly rather than fake the run.

    Docs: https://docs.python.org/3/library/urllib.request.html
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, method="HEAD")
    try:
        urllib.request.urlopen(req, timeout=timeout_s)
        return False, ""
    except urllib.error.HTTPError as exc:
        # 407 = Proxy auth required; 403 = forbidden; both block real downloads.
        return True, f"HTTP {exc.code} {exc.reason}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return True, f"{type(exc).__name__}: {exc}"


def ensure_repo_root_on_path() -> None:
    """Insert the repo's ``src/`` on ``sys.path`` so ``import nucleus`` works.

    Useful when scripts run before ``pip install -e .`` lands the package.
    The CI installs nucleus already, so this is a defensive no-op there.
    """
    src = REPO_ROOT / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


def docker_available() -> bool:
    """Return True iff ``docker --version`` returns 0 within 5 seconds."""
    import shutil
    import subprocess

    if shutil.which("docker") is None:
        return False
    try:
        proc = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return proc.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def benchmark_clock() -> float:
    """Monotonic wall-clock for benchmark timings (perf_counter — no clock skew).

    Docs: https://docs.python.org/3/library/time.html#time.perf_counter
    """
    return time.perf_counter()


__all__ = [
    "BLOCKER",
    "BenchResult",
    "BenchRow",
    "FAIL",
    "HIGH",
    "LOW",
    "MEDIUM",
    "NEEDS_INVESTIGATION",
    "PASS",
    "REPO_ROOT",
    "RESULTS_DIR",
    "RSSWatcher",
    "SKIP_DEPS",
    "benchmark_clock",
    "classify",
    "delta_pct",
    "docker_available",
    "ensure_repo_root_on_path",
    "fmt_bytes",
    "fmt_delta",
    "fmt_seconds",
    "hardware_specs",
    "now_iso",
    "percentile",
    "proxy_blocked",
    "severity_for",
    "software_versions",
    "stats_summary",
    "write_result",
]
