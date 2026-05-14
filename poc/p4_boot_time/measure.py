"""PoC #4 measurement harness — `nucleus up` cold-boot timing.

Validates ``nucleus_poc_plan.md`` §4 acceptance against
``nucleus_architecture_v4.1.md`` §5.7 / §6.3: cold boot <10s, warm <3s,
idle RAM <500MB, all components reachable. Standalone runner:
``python poc/p4_boot_time/measure.py`` (exit 0=PASS, 1=FAIL, 2=INCOMPLETE).
Promotes to ``src/nucleus/cli/up.py`` after PoC #1 (``AGENTS.md`` §11.1).

Pins/docs (per AGENTS.md §11.12): dagster==1.9.5
(https://docs.dagster.io/api/python-api/); pyiceberg==0.8.1
(https://py.iceberg.apache.org/api/); polars==1.18.0
(https://docs.pola.rs/api/python/stable/); duckdb==1.1.3
(https://duckdb.org/docs/api/python/overview); urllib (stdlib,
https://docs.python.org/3/library/urllib.request.html); resource (stdlib
posix, https://docs.python.org/3/library/resource.html); MinIO health
(https://min.io/docs/minio/linux/operations/monitoring/healthcheck-probe.html).
"""

from __future__ import annotations

import importlib
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

TARGET_COLD_BOOT_S, TARGET_WARM_BOOT_S, TARGET_IDLE_RAM_MB = 10.0, 3.0, 500.0
PHASE_TARGETS = {"imports": 3.0, "minio_health": 0.5, "catalog_init": 0.5, "dagster_definitions": 1.5}
DEFAULT_MINIO_HEALTH_URL = "http://localhost:9000/minio/health/live"
_HEAVY_IMPORTS = ("dagster", "pyiceberg", "pyiceberg.catalog", "polars", "duckdb")


@dataclass
class PhaseResult:
    """One measured boot phase. ``skipped=True`` (e.g. MinIO not running) flips
    the verdict to INCOMPLETE rather than failing it."""

    name: str
    duration_s: float
    ok: bool
    target_s: float | None = None
    detail: str = ""
    skipped: bool = False

    @property
    def passed_target(self) -> bool:
        return self.skipped or (self.ok and (self.target_s is None or self.duration_s <= self.target_s))


@contextmanager
def phase(name: str, results: list[PhaseResult], target_s: float | None = None) -> Iterator[None]:
    """Time a body; append a PhaseResult; re-raise on exception so callers
    can choose to swallow (skip) or surface."""
    start = time.perf_counter()
    try:
        yield
        results.append(PhaseResult(name, time.perf_counter() - start, True, target_s))
    except Exception as exc:
        results.append(PhaseResult(
            name, time.perf_counter() - start, False, target_s,
            detail=f"{type(exc).__name__}: {exc}",
        ))
        raise


def measure_imports() -> tuple[float, list[str]]:
    """Import the heavy v0.1 deps. Returns ``(duration_s, missing_modules)``."""
    missing: list[str] = []
    start = time.perf_counter()
    for mod in _HEAVY_IMPORTS:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(mod)
    return time.perf_counter() - start, missing


def measure_minio_health(
    url: str = DEFAULT_MINIO_HEALTH_URL, timeout_s: float = 2.0,
) -> tuple[float, bool, str]:
    """Probe MinIO. Returns ``(duration_s, healthy, detail)``. HTTP 200 + 403
    both count as healthy (different MinIO setups expose different paths)."""
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return time.perf_counter() - start, resp.status == 200, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        return time.perf_counter() - start, exc.code in (200, 403), f"HTTP {exc.code}"
    except Exception as exc:
        return time.perf_counter() - start, False, f"{type(exc).__name__}: {exc}"


def measure_catalog_init(warehouse_dir: Path) -> tuple[float, str]:
    """Init pyiceberg ``SqlCatalog`` over a filesystem warehouse.

    NEEDS VERIFICATION (AGENTS.md §11.12): the v0.1 'filesystem catalog' in
    arch §5.7 is realised as PyIceberg ``SqlCatalog`` (SQLite-backed) over a
    ``file://`` warehouse — see ``docs/research/pyiceberg.md`` §4 and the
    production-shaped flow in ``poc/p3_ingest/ingest.py``. The
    ``type='memory'`` variant in the task spec is NOT used here; an upstream
    ``InMemoryCatalog`` exists (registration string ``type='in-memory'``) but
    is unverified in 0.8.1 — log to ``docs/research/ai_hallucinations.md``.
    """
    from pyiceberg.catalog import load_catalog

    warehouse_dir.mkdir(parents=True, exist_ok=True)
    db = warehouse_dir / "p4_catalog.db"
    start = time.perf_counter()
    cat = load_catalog("p4_boot_time", type="sql", uri=f"sqlite:///{db.resolve().as_posix()}", warehouse=f"file:///{warehouse_dir.resolve().as_posix()}")
    return time.perf_counter() - start, f"catalog={type(cat).__name__}"


def measure_dagster_definitions() -> tuple[float, str]:
    """Construct ``Definitions(assets=[trivial])``. Mirrors what `nucleus up`
    will do at boot — ephemeral instance per ``docs/research/dagster.md`` §4."""
    import dagster as dg

    @dg.asset
    def p4_boot_probe() -> int:
        return 1

    start = time.perf_counter()
    defs = dg.Definitions(assets=[p4_boot_probe])
    return time.perf_counter() - start, f"assets={len(list(defs.assets))}"


def measure_idle_ram() -> tuple[float, str]:
    """Return ``(rss_mb, source_detail)``. psutil → resource → ``-1`` fallback.

    psutil isn't pinned in pyproject.toml but ships transitively via dagster
    on Win/macOS/Linux (``docs/research/dagster.md`` §7); on posix without
    psutil we use ``resource.getrusage``; on Windows without psutil we return
    -1.0 with a clear message."""
    try:
        import psutil  # docs: https://psutil.readthedocs.io/
        return psutil.Process().memory_info().rss / 1024 / 1024, "psutil"
    except ImportError:
        pass
    if os.name == "posix":
        import resource  # ru_maxrss is KB on Linux, bytes on macOS.
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return (rss / 1024 / 1024 if sys.platform == "darwin" else rss / 1024), "resource.getrusage"
    return -1.0, "no measurement available (pip install psutil)"


def measure_total_cold_boot(
    warehouse_dir: Path, minio_url: str = DEFAULT_MINIO_HEALTH_URL,
) -> tuple[float, list[PhaseResult]]:
    """Run the 4 boot phases sequentially. Returns ``(total_s, results)``.

    MinIO is the only optional phase: if unreachable it's recorded ``skipped``
    (still failing the phase target but not the verdict)."""
    results: list[PhaseResult] = []
    cold_start = time.perf_counter()

    def _imports() -> str:
        elapsed, missing = measure_imports()
        if missing:
            raise ImportError(f"missing modules: {', '.join(missing)}")
        return f"imported {len(_HEAVY_IMPORTS)} heavy modules in {elapsed:.2f}s"

    def _minio() -> str:
        _, healthy, detail = measure_minio_health(minio_url)
        if not healthy:
            raise ConnectionError(detail)
        return detail

    bodies: list[tuple[str, Callable[[], str], bool]] = [
        ("imports", _imports, False),
        ("minio_health", _minio, True),
        ("catalog_init", lambda: measure_catalog_init(warehouse_dir)[1], False),
        ("dagster_definitions", lambda: measure_dagster_definitions()[1], False),
    ]
    for name, body, optional in bodies:
        held: list[str] = []
        try:
            with phase(name, results, target_s=PHASE_TARGETS[name]):
                held.append(body())
        except Exception:
            if optional and results:
                results[-1].skipped = True
            continue
        if held and results:
            results[-1].detail = held[0]
    return time.perf_counter() - cold_start, results


def main(argv: list[str] | None = None) -> int:
    """Run all phases, print summary, return exit code (0=PASS, 1=FAIL, 2=INCOMPLETE)."""
    _ = argv
    print("=" * 78)
    print("PoC #4 — `nucleus up` Boot Timing")
    print("=" * 78)
    with TemporaryDirectory(prefix="p4_boot_") as tmp:
        total_s, results = measure_total_cold_boot(warehouse_dir=Path(tmp) / "warehouse")
    ram_mb, ram_source = measure_idle_ram()
    print(f"\n{'Phase':<22} {'Duration':>10} {'Target':>10} {'Status':>8}  Detail")
    print("-" * 78)
    for r in results:
        status = "SKIP" if r.skipped else ("PASS" if r.passed_target else "FAIL")
        target = f"<{r.target_s:.2f}s" if r.target_s is not None else "—"
        print(f"{r.name:<22} {r.duration_s:>9.3f}s {target:>10} {status:>8}  {r.detail}")
    ram_ok = 0 < ram_mb <= TARGET_IDLE_RAM_MB
    ram_status = "PASS" if ram_ok else ("UNKNOWN" if ram_mb < 0 else "FAIL")
    ram_target = f"<{int(TARGET_IDLE_RAM_MB)}MB"
    print(f"{'idle_ram':<22} {ram_mb:>9.1f}MB {ram_target:>10} {ram_status:>8}  source={ram_source}")
    cold_ok = total_s <= TARGET_COLD_BOOT_S
    print("=" * 78)
    print(f"Total cold boot: {total_s:.2f}s (target <{TARGET_COLD_BOOT_S}s) "
          f"{'PASS' if cold_ok else 'FAIL'}")
    if any(not r.passed_target and not r.skipped for r in results) or not cold_ok or (ram_mb >= 0 and not ram_ok):
        print("VERDICT: FAIL")
        return 1
    if any(r.skipped for r in results) or ram_mb < 0:
        print("VERDICT: INCOMPLETE (start MinIO / install psutil and re-run)")
        return 2
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
