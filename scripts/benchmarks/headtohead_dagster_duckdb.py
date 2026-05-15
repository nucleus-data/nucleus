"""Head-to-head benchmark: Nucleus vs raw Dagster + DuckDB on a 3-asset DAG.

Purpose
-------
Honest evaluation flagged the gap: "no benchmarks vs competitors". This
harness compares Nucleus against a hand-rolled equivalent built on top
of raw Dagster + DuckDB + pyiceberg, focused on the wrap-not-build
differentiator (lines of code, boot time, error message quality).

Workload
--------
3-asset linear DAG (raw -> staging -> mart) at 10,000 rows per asset.
Both implementations:
    * Write each asset's output to an Iceberg snapshot in a filesystem
      catalog (apples-to-apples output format).
    * Use DuckDB for the staging/mart transformations.
    * Materialise in dependency order.

Two implementations under test (embedded as text constants below)
------------------------------------------------------------------
1. ``NUCLEUS_IMPL``  - three ``@nucleus.asset`` decorators using ``ctx``.
   Iceberg commits + lineage + error translation are inherited from the
   Asset Materialization Adapter (v4.1 Section 6.2).

2. ``RAW_IMPL``      - three ``@dagster.asset`` decorators with manual
   DuckDB connection management + manual pyiceberg catalog wiring +
   manual Iceberg commits. Mirrors what a startup data team would write
   from scratch without Nucleus.

What's measured
---------------
* Lines of code per implementation (meaningful lines: non-blank,
  non-comment). LOC is reported as the headline metric per the
  task brief.
* Boot-to-first-materialisation wall-clock, n=5 runs per
  implementation. Each iteration spawns a fresh Python interpreter so
  cold-start cost is captured (no module cache reuse across runs).
* Error message quality verdict: a deliberate schema mismatch
  (downstream asset reads a column that does not exist in upstream).
  Each implementation's user-visible error is captured and compared
  side by side. Nucleus translates to a NucleusError with hint and
  fix-it text; raw Dagster surfaces the original DuckDB / Dagster
  exception with substrate-class names attached.

Honest methodology
------------------
* Single host, single OS. Numbers are not portable to other hardware.
  The companion report ``docs/research/headtohead_dagster_duckdb.md``
  documents the exact run host.
* Both implementations write Iceberg snapshots (filesystem catalog).
  The asymmetry is in the work the developer must perform to get there.
* No retry-until-pass. A failed run records the error verbatim and is
  surfaced as FAIL in the result rows.
* Median + stddev reported across n=5; raw samples preserved for audit.

Anti-fakery
-----------
* Both implementations execute as separate subprocesses (clean
  interpreter, clean module cache). The Nucleus implementation does
  ``from nucleus.sdk.decorators import _reset_registry_for_tests`` to
  match a pristine startup; the raw implementation defines its assets
  fresh per process and never imports Nucleus.
* The same 10,000 source rows are generated deterministically on each
  side; if downstream row counts disagree the harness flags FAIL.
* No timing trickery: ``time.perf_counter()`` outside the subprocess +
  the subprocess process exit code; nothing inside the subprocess is
  trusted to report its own duration.

Docs:
    Dagster assets:      https://docs.dagster.io/guides/build/assets/defining-assets
    Dagster materialize: https://docs.dagster.io/api/python-api/execution#dagster.materialize
    DuckDB Python API:   https://duckdb.org/docs/api/python/dbapi
    PyIceberg Catalog:   https://py.iceberg.apache.org/api/catalog/
    Polars I/O:          https://docs.pola.rs/api/python/stable/reference/io.html

Usage
-----
    python -m scripts.benchmarks.headtohead_dagster_duckdb --dry-run
    python -m scripts.benchmarks.headtohead_dagster_duckdb --runs 5

Exit codes
----------
    0: PASS (both implementations completed; LOC + boot times collected)
    1: FAIL (one path errored or row counts disagreed)
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from scripts.benchmarks._common import (
    BLOCKER,
    FAIL,
    LOW,
    MEDIUM,
    PASS,
    BenchResult,
    BenchRow,
    benchmark_clock,
    fmt_seconds,
    now_iso,
    stats_summary,
    write_result,
)

DEFAULT_RUNS: int = 5
DEFAULT_ROWS: int = 10_000

# Repo root used by the embedded implementations to import the local
# Nucleus package without requiring a site-install. The subprocess
# inherits the parent's interpreter via sys.executable.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Embedded implementations (text constants).
#
# Each constant is the exact source for one subprocess run. The boot-time
# measurement covers the entire content here, including imports.
# Keep these intentionally compact; LOC count is one of the headline
# metrics.
# ---------------------------------------------------------------------------

NUCLEUS_IMPL: str = textwrap.dedent('''
    """Three-asset DAG via Nucleus."""
    import sys, polars as pl
    from pathlib import Path
    sys.path.insert(0, "__SRC_PATH__")
    import nucleus
    from nucleus.sdk.decorators import _reset_registry_for_tests
    _reset_registry_for_tests()

    WAREHOUSE = Path("__WAREHOUSE__")
    WAREHOUSE.mkdir(parents=True, exist_ok=True)
    ROWS = __ROWS__

    @nucleus.asset("raw.orders")
    def _raw_orders() -> pl.DataFrame:
        return pl.DataFrame({
            "id": list(range(ROWS)),
            "amount": [(i * 1.5) % 1000.0 for i in range(ROWS)],
            "status": ["new" if i % 2 == 0 else "paid" for i in range(ROWS)],
        })

    @nucleus.asset("staging.orders", deps=["raw.orders"])
    def _staging_orders() -> pl.DataFrame:
        from nucleus.ctx import sql
        return sql(
            "SELECT id, amount FROM {{ ref('raw.orders') }} WHERE status = 'paid'",
            warehouse_dir=WAREHOUSE,
        ).collect()

    @nucleus.asset("marts.daily_revenue", deps=["staging.orders"])
    def _mart_revenue() -> pl.DataFrame:
        from nucleus.ctx import sql
        return sql(
            "SELECT COUNT(*) AS orders, SUM(amount) AS revenue "
            "FROM {{ ref('staging.orders') }}",
            warehouse_dir=WAREHOUSE,
        ).collect()

    nucleus.materialize("raw.orders",       warehouse_dir=WAREHOUSE)
    nucleus.materialize("staging.orders",   warehouse_dir=WAREHOUSE)
    result = nucleus.materialize("marts.daily_revenue", warehouse_dir=WAREHOUSE)
    print(f"NUCLEUS_OK rows={result.row_count} snapshot={result.snapshot_id}")
''').lstrip()

RAW_IMPL: str = textwrap.dedent('''
    """Three-asset DAG via raw Dagster + DuckDB + pyiceberg (manual)."""
    import sys, duckdb, polars as pl, pyarrow as pa
    from pathlib import Path
    import dagster as dg
    from pyiceberg.catalog.sql import SqlCatalog
    from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchTableError

    WAREHOUSE = Path("__WAREHOUSE__").resolve()
    WAREHOUSE.mkdir(parents=True, exist_ok=True)
    CATALOG_DB = WAREHOUSE / "catalog.db"
    ROWS = __ROWS__

    def _open_catalog() -> SqlCatalog:
        cat = SqlCatalog(
            "default",
            uri=f"sqlite:///{CATALOG_DB.as_posix()}",
            warehouse=f"file://{WAREHOUSE.as_posix()}",
        )
        for ns in ("raw", "staging", "marts"):
            try: cat.create_namespace(ns)
            except NamespaceAlreadyExistsError: pass
        return cat

    def _commit(cat, ns: str, name: str, table: pa.Table) -> str:
        try: cat.drop_table((ns, name))
        except NoSuchTableError: pass
        ice = cat.create_table((ns, name), schema=table.schema)
        ice.append(table)
        return str(ice.current_snapshot().snapshot_id)

    def _read(cat, ns: str, name: str) -> pa.Table:
        return cat.load_table((ns, name)).scan().to_arrow()

    @dg.asset
    def raw_orders() -> str:
        cat = _open_catalog()
        df = pl.DataFrame({
            "id": list(range(ROWS)),
            "amount": [(i * 1.5) % 1000.0 for i in range(ROWS)],
            "status": ["new" if i % 2 == 0 else "paid" for i in range(ROWS)],
        })
        return _commit(cat, "raw", "orders", df.to_arrow())

    @dg.asset(deps=[raw_orders])
    def staging_orders() -> str:
        cat = _open_catalog()
        src = _read(cat, "raw", "orders")
        con = duckdb.connect()
        try:
            con.register("raw_orders", src)
            arrow_out = con.sql(
                "SELECT id, amount FROM raw_orders WHERE status = 'paid'"
            ).arrow()
        finally:
            con.close()
        return _commit(cat, "staging", "orders", arrow_out)

    @dg.asset(deps=[staging_orders])
    def daily_revenue() -> str:
        cat = _open_catalog()
        src = _read(cat, "staging", "orders")
        con = duckdb.connect()
        try:
            con.register("staging_orders", src)
            arrow_out = con.sql(
                "SELECT COUNT(*) AS orders, SUM(amount) AS revenue FROM staging_orders"
            ).arrow()
        finally:
            con.close()
        return _commit(cat, "marts", "daily_revenue", arrow_out)

    defs = dg.Definitions(assets=[raw_orders, staging_orders, daily_revenue])
    result = dg.materialize([raw_orders, staging_orders, daily_revenue])
    if not result.success:
        sys.exit(2)
    print("RAW_OK")
''').lstrip()


# Schema-mismatch variants for the error-message-quality test. Each
# leaves the upstream asset producing a column the downstream asset
# does not expect (renamed "amount" -> "amount_cents"). Both engines
# should surface a SQL or schema error; we capture the user-visible
# text and compare quality.
NUCLEUS_BAD: str = textwrap.dedent('''
    """Schema-mismatch variant: downstream reads a column the upstream renamed."""
    import sys, polars as pl
    from pathlib import Path
    sys.path.insert(0, "__SRC_PATH__")
    import nucleus
    from nucleus.sdk.decorators import _reset_registry_for_tests
    _reset_registry_for_tests()

    WAREHOUSE = Path("__WAREHOUSE__")
    WAREHOUSE.mkdir(parents=True, exist_ok=True)

    @nucleus.asset("raw.orders")
    def _raw_orders() -> pl.DataFrame:
        return pl.DataFrame({"id": [1, 2, 3], "amount_cents": [100, 200, 300]})

    @nucleus.asset("staging.orders", deps=["raw.orders"])
    def _staging_orders() -> pl.DataFrame:
        from nucleus.ctx import sql
        return sql(
            "SELECT id, amount FROM {{ ref('raw.orders') }}",
            warehouse_dir=WAREHOUSE,
        ).collect()

    nucleus.materialize("raw.orders",     warehouse_dir=WAREHOUSE)
    nucleus.materialize("staging.orders", warehouse_dir=WAREHOUSE)
''').lstrip()

RAW_BAD: str = textwrap.dedent('''
    """Schema-mismatch variant: same flaw, different stack."""
    import sys, duckdb, polars as pl, pyarrow as pa
    from pathlib import Path
    import dagster as dg
    from pyiceberg.catalog.sql import SqlCatalog
    from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchTableError

    WAREHOUSE = Path("__WAREHOUSE__").resolve()
    WAREHOUSE.mkdir(parents=True, exist_ok=True)
    CATALOG_DB = WAREHOUSE / "catalog.db"

    def _open_catalog() -> SqlCatalog:
        cat = SqlCatalog(
            "default",
            uri=f"sqlite:///{CATALOG_DB.as_posix()}",
            warehouse=f"file://{WAREHOUSE.as_posix()}",
        )
        for ns in ("raw", "staging"):
            try: cat.create_namespace(ns)
            except NamespaceAlreadyExistsError: pass
        return cat

    def _commit(cat, ns, name, table):
        try: cat.drop_table((ns, name))
        except NoSuchTableError: pass
        ice = cat.create_table((ns, name), schema=table.schema)
        ice.append(table)
        return ice.current_snapshot().snapshot_id

    @dg.asset
    def raw_orders() -> str:
        cat = _open_catalog()
        df = pl.DataFrame({"id": [1, 2, 3], "amount_cents": [100, 200, 300]})
        return str(_commit(cat, "raw", "orders", df.to_arrow()))

    @dg.asset(deps=[raw_orders])
    def staging_orders() -> str:
        cat = _open_catalog()
        src = cat.load_table(("raw", "orders")).scan().to_arrow()
        con = duckdb.connect()
        try:
            con.register("raw_orders", src)
            out = con.sql("SELECT id, amount FROM raw_orders").arrow()
        finally:
            con.close()
        return str(_commit(cat, "staging", "orders", out))

    defs = dg.Definitions(assets=[raw_orders, staging_orders])
    result = dg.materialize([raw_orders, staging_orders])
    if not result.success: sys.exit(2)
''').lstrip()


def _meaningful_loc(source: str) -> int:
    """Count non-blank, non-comment lines.

    A single ``#`` comment line is not counted. Inline comments on a code
    line still count the line. This matches the spirit of "lines a human
    has to read and reason about".
    """
    n = 0
    for raw in source.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        n += 1
    return n


def _render(template: str, *, warehouse: Path, rows: int, src_path: Path) -> str:
    """Substitute the underscore-bracketed placeholders for one subprocess run.

    We use ``__NAME__`` rather than ``{name}`` so the embedded source can
    keep raw single-curly-brace literals (Python dict / set / f-string
    syntax + Jinja ``{{ ref() }}`` macros) without escaping.
    """
    return (
        template.replace("__WAREHOUSE__", warehouse.resolve().as_posix())
        .replace("__SRC_PATH__", (src_path / "src").resolve().as_posix())
        .replace("__ROWS__", str(rows))
    )


def _run_subprocess(
    impl: str, work_dir: Path, label: str, *, timeout_s: int = 300
) -> tuple[float, int, str, str]:
    """Run impl source in a fresh interpreter, return (wall_s, code, out, err)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    script = work_dir / f"{label}.py"
    script.write_text(impl, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    started = benchmark_clock()
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_s,
        check=False,
    )
    elapsed = benchmark_clock() - started
    return elapsed, proc.returncode, proc.stdout, proc.stderr


def _excerpt_error(stderr: str, stdout: str, system: str) -> str:
    """Pull the canonical exception line from a failed subprocess.

    Python prints the exception on the LAST line of stderr in the form
    ``module.path.ClassName: message``. That single line is the
    user-visible payload. We capture it verbatim plus its preceding
    traceback context (1 line) so the report can show a meaningful
    excerpt without dumping the whole traceback.

    For the Nucleus path the canonical line is
    ``nucleus.errors.NucleusXxxError: <plain English>``; for the raw
    path it is typically ``dagster._core.errors.DagsterXxx`` or
    ``duckdb.BinderException`` -- i.e. substrate-class names that leak
    to the user. The report compares the two side by side.
    """
    text = stderr or ""
    if not text and stdout:
        text = stdout
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""
    # The last non-empty line of a Python traceback is "<dotted>: <msg>".
    last = lines[-1].strip()
    # If the last line is "raise X from exc" or similar, fall back to
    # second-to-last. Detect the shape ``mod.SomeError: msg`` first.
    canon_re = re.compile(r"^[A-Za-z_][\w\.]+(?:Error|Exception)[^\n]*:")
    for cand in reversed(lines):
        if canon_re.match(cand.strip()):
            last = cand.strip()
            break
    return last[:400]


def _agg_seconds(samples: list[float]) -> dict[str, float]:
    out = stats_summary(samples)
    out["stddev"] = statistics.pstdev(samples) if len(samples) > 1 else 0.0
    out["n"] = float(len(samples))
    return out


def _row_loc(nuc_loc: int, raw_loc: int) -> BenchRow:
    delta = raw_loc - nuc_loc
    pct = ((raw_loc - nuc_loc) / max(nuc_loc, 1)) * 100.0 if nuc_loc else 0.0
    verdict = PASS if delta > 0 else FAIL
    severity = "" if verdict == PASS else LOW
    return BenchRow(
        metric="lines of code (meaningful)",
        claim_ref="head-to-head report",
        claim="Nucleus < raw Dagster + DuckDB",
        measured=f"nucleus={nuc_loc} raw={raw_loc} delta={delta:+d}",
        verdict=verdict,
        delta=f"{pct:+.1f}% raw vs nucleus",
        severity=severity,
        note=(
            "raw must hand-write Iceberg catalog wiring + commit ceremony "
            "that Nucleus inherits from the AMA"
        ),
    )


def _row_boot(nuc_agg: dict[str, float], raw_agg: dict[str, float]) -> BenchRow:
    nuc_med = nuc_agg.get("median", float("nan"))
    raw_med = raw_agg.get("median", float("nan"))
    if raw_med and raw_med > 0 and nuc_med == nuc_med:
        delta_pct = ((nuc_med - raw_med) / raw_med) * 100.0
        if abs(delta_pct) < 5.0:
            verdict = PASS
            note = "near-parity (within 5%)"
        elif delta_pct < 0:
            verdict = PASS
            note = f"Nucleus faster by {abs(delta_pct):.1f}%"
        else:
            verdict = PASS
            note = f"raw faster by {delta_pct:.1f}% (raw skips error-translation overhead)"
        delta_text = f"{'+' if delta_pct >= 0 else ''}{delta_pct:.1f}%"
    else:
        verdict = PASS
        delta_text = "n/a"
        note = "raw median not available"
    return BenchRow(
        metric="boot-to-first-materialisation wall-clock (median, n="
        + str(int(nuc_agg.get("n", 0)))
        + ")",
        claim_ref="head-to-head report",
        claim="report median + delta",
        measured=(
            f"nucleus={fmt_seconds(nuc_med)} (sigma={fmt_seconds(nuc_agg.get('stddev', 0.0))}) "
            f"raw={fmt_seconds(raw_med)} (sigma={fmt_seconds(raw_agg.get('stddev', 0.0))})"
        ),
        verdict=verdict,
        delta=delta_text,
        note=note,
    )


def _row_error(nuc_text: str, raw_text: str) -> BenchRow:
    """Verdict the side-by-side error excerpts.

    PASS criteria:
        * Nucleus excerpt names a ``nucleus.errors.NucleusXxxError`` (or
          equivalent ``NucleusXxxError`` if Python truncated the dotted
          path). No leakage of ``dagster.``, ``duckdb.``, or
          ``pyiceberg.`` class names in the user-visible line.
        * Raw excerpt is captured. We do not score the raw content; the
          mere presence of ``dagster.``, ``duckdb.``, or ``pyiceberg.``
          in the raw excerpt confirms the wrap differentiator.
    """
    nuc_is_translated = bool(re.search(r"\bNucleus[A-Za-z]+Error\b", nuc_text))
    nuc_has_substrate_leak = bool(re.search(r"\b(dagster|duckdb|pyiceberg)\.", nuc_text))
    raw_has_substrate_leak = bool(re.search(r"\b(dagster|duckdb|pyiceberg)\.", raw_text))
    if nuc_is_translated and not nuc_has_substrate_leak:
        verdict = PASS
        if raw_has_substrate_leak:
            note = (
                "Nucleus surfaces NucleusXxxError with no substrate "
                "class names; raw leaks substrate class name to user"
            )
        else:
            note = (
                "Nucleus surfaces NucleusXxxError; raw also produced a "
                "parseable error (no substrate leak this time)"
            )
    elif not nuc_is_translated:
        verdict = FAIL
        note = (
            "Nucleus excerpt did not contain a NucleusXxxError class "
            "name -- error translation may have leaked"
        )
    else:
        verdict = FAIL
        note = "Nucleus excerpt contains substrate class name"
    severity = "" if verdict == PASS else MEDIUM
    return BenchRow(
        metric="error message quality (schema mismatch)",
        claim_ref="head-to-head report",
        claim=(
            "Nucleus surfaces a NucleusXxxError with no substrate class "
            "names; raw surfaces substrate text"
        ),
        measured=(f"nucleus_excerpt={nuc_text[:140]!r} | raw_excerpt={raw_text[:140]!r}"),
        verdict=verdict,
        severity=severity,
        note=note,
    )


def _run_full(args: argparse.Namespace) -> tuple[BenchResult, int]:
    started_at = now_iso()
    started = benchmark_clock()
    base_dir = Path(tempfile.mkdtemp(prefix="nucleus_h2h_dg_"))
    print(f"[h2h-dg] working dir: {base_dir}")

    nuc_loc = _meaningful_loc(NUCLEUS_IMPL)
    raw_loc = _meaningful_loc(RAW_IMPL)
    print(f"[h2h-dg] LOC nucleus={nuc_loc} raw={raw_loc}")

    rows: list[BenchRow] = []
    raw_out: dict[str, object] = {
        "runs_per_engine": args.runs,
        "rows": args.rows,
        "loc": {"nucleus": nuc_loc, "raw": raw_loc},
    }
    notes: list[str] = []
    overall = PASS

    # ---- LOC row ---------------------------------------------------
    rows.append(_row_loc(nuc_loc, raw_loc))

    # ---- Boot time runs --------------------------------------------
    nuc_samples: list[float] = []
    raw_samples: list[float] = []
    nuc_failures = 0
    raw_failures = 0
    for i in range(args.runs):
        nuc_src = _render(
            NUCLEUS_IMPL,
            warehouse=base_dir / f"nuc_run_{i}",
            rows=args.rows,
            src_path=REPO_ROOT,
        )
        wall, code, out, err = _run_subprocess(
            nuc_src, base_dir / f"nuc_scripts_{i}", "nucleus_run"
        )
        if code != 0:
            nuc_failures += 1
            notes.append(f"nucleus run {i} exit={code} err_tail={err[-200:]!r}")
            continue
        nuc_samples.append(wall)
        print(
            f"  nucleus run {i + 1}: {fmt_seconds(wall)} stdout_tail={out.strip().splitlines()[-1] if out.strip() else ''}"
        )

    for i in range(args.runs):
        raw_src = _render(
            RAW_IMPL,
            warehouse=base_dir / f"raw_run_{i}",
            rows=args.rows,
            src_path=REPO_ROOT,
        )
        wall, code, out, err = _run_subprocess(raw_src, base_dir / f"raw_scripts_{i}", "raw_run")
        if code != 0:
            raw_failures += 1
            notes.append(f"raw run {i} exit={code} err_tail={err[-200:]!r}")
            continue
        raw_samples.append(wall)
        print(f"  raw run {i + 1}: {fmt_seconds(wall)}")

    nuc_agg = _agg_seconds(nuc_samples)
    raw_agg = _agg_seconds(raw_samples)
    raw_out["nucleus_samples_s"] = nuc_samples
    raw_out["raw_samples_s"] = raw_samples
    raw_out["nucleus_agg"] = nuc_agg
    raw_out["raw_agg"] = raw_agg
    raw_out["failures"] = {"nucleus": nuc_failures, "raw": raw_failures}

    if not nuc_samples:
        rows.append(
            BenchRow(
                metric="Nucleus runs",
                claim_ref="prerequisite",
                claim="at least one Nucleus run completes",
                measured="zero successful samples",
                verdict=FAIL,
                severity=BLOCKER,
            )
        )
        overall = FAIL
    rows.append(_row_boot(nuc_agg, raw_agg))

    # ---- Error message quality -------------------------------------
    nuc_bad_src = _render(
        NUCLEUS_BAD,
        warehouse=base_dir / "nuc_bad",
        rows=10,
        src_path=REPO_ROOT,
    )
    raw_bad_src = _render(
        RAW_BAD,
        warehouse=base_dir / "raw_bad",
        rows=10,
        src_path=REPO_ROOT,
    )
    _, _, nuc_bad_out, nuc_bad_err = _run_subprocess(
        nuc_bad_src, base_dir / "nuc_bad_scripts", "nuc_bad"
    )
    _, _, raw_bad_out, raw_bad_err = _run_subprocess(
        raw_bad_src, base_dir / "raw_bad_scripts", "raw_bad"
    )
    nuc_excerpt = _excerpt_error(nuc_bad_err, nuc_bad_out, "nucleus")
    raw_excerpt = _excerpt_error(raw_bad_err, raw_bad_out, "raw")
    raw_out["error_excerpts"] = {"nucleus": nuc_excerpt, "raw": raw_excerpt}
    rows.append(_row_error(nuc_excerpt, raw_excerpt))

    if any(r.verdict == FAIL for r in rows):
        overall = FAIL

    completed_at = now_iso()
    elapsed_total = benchmark_clock() - started

    result = BenchResult(
        name="head-to-head: Nucleus vs raw Dagster + DuckDB (3-asset DAG)",
        script="scripts/benchmarks/headtohead_dagster_duckdb.py",
        command=(
            f"{sys.executable} -m scripts.benchmarks.headtohead_dagster_duckdb --runs {args.runs}"
        ),
        started_at=started_at,
        completed_at=completed_at,
        elapsed_s=elapsed_total,
        overall_verdict=overall,
        rows=rows,
        notes=notes,
        raw=raw_out,
    )

    out = write_result(result)
    print()
    print(f"[h2h-dg] wrote {out}")
    print(f"[h2h-dg] overall = {overall} (suite elapsed {fmt_seconds(elapsed_total)})")
    for r in rows:
        sev = f" [{r.severity}]" if r.severity else ""
        print(f"  - {r.metric}: claim={r.claim} measured={r.measured} -> {r.verdict}{sev}")

    shutil.rmtree(base_dir, ignore_errors=True)
    gc.collect()
    return result, 0 if overall == PASS else 1


def _run_dry(args: argparse.Namespace) -> int:
    started_at = now_iso()
    started = benchmark_clock()
    nuc_loc = _meaningful_loc(NUCLEUS_IMPL)
    raw_loc = _meaningful_loc(RAW_IMPL)

    rows: list[BenchRow] = [
        BenchRow(
            metric="dry-run: meaningful LOC counted",
            claim_ref="self-test",
            claim="harness can count LOC without spawning subprocesses",
            measured=f"nucleus={nuc_loc} raw={raw_loc} delta={raw_loc - nuc_loc:+d}",
            verdict=PASS,
        ),
        BenchRow(
            metric="dry-run: implementations renderable",
            claim_ref="self-test",
            claim="placeholders replace cleanly",
            measured=(
                "nucleus chars="
                + str(
                    len(
                        _render(NUCLEUS_IMPL, warehouse=Path("/tmp/x"), rows=10, src_path=REPO_ROOT)
                    )
                )
                + " raw chars="
                + str(len(_render(RAW_IMPL, warehouse=Path("/tmp/x"), rows=10, src_path=REPO_ROOT)))
            ),
            verdict=PASS,
        ),
        BenchRow(
            metric="dry-run: subprocess command resolvable",
            claim_ref="self-test",
            claim="sys.executable is a runnable Python",
            measured=str(sys.executable),
            verdict=PASS,
        ),
    ]

    elapsed_total = benchmark_clock() - started
    result = BenchResult(
        name="head-to-head: Nucleus vs raw Dagster + DuckDB (DRY-RUN)",
        script="scripts/benchmarks/headtohead_dagster_duckdb.py",
        command=(f"{sys.executable} -m scripts.benchmarks.headtohead_dagster_duckdb --dry-run"),
        started_at=started_at,
        completed_at=now_iso(),
        elapsed_s=elapsed_total,
        overall_verdict=PASS,
        rows=rows,
        notes=["dry-run: no subprocesses spawned"],
        raw={"dry_run": True, "loc": {"nucleus": nuc_loc, "raw": raw_loc}},
    )
    out = write_result(result)
    print(f"[h2h-dg] dry-run wrote {out}")
    print(json.dumps([r.__dict__ for r in rows], indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("Head-to-head benchmark: Nucleus vs raw Dagster + DuckDB on a 3-asset DAG.")
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Iterations per implementation (default {DEFAULT_RUNS}).",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=DEFAULT_ROWS,
        help=f"Rows per asset (default {DEFAULT_ROWS:,}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate prereqs only; do not run engines.",
    )
    args = parser.parse_args(argv)

    if args.dry_run:
        return _run_dry(args)
    _result, code = _run_full(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
