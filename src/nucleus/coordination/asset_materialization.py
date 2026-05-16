"""Asset Materialization Adapter (AMA) — data-path owner (L2).

Per ``nucleus_architecture_v4.1.md`` §6.2 (Asset Materialization Adapter,
the runtime this module owns) + §6.3 (Coordination layer rules) + §6.4
(Error Translation discipline). Implements the contract that
``docs/decisions/ADR-013-ctx-materialize-api.md`` §1 promises end-users
through :func:`nucleus.materialize`, and that
``docs/architecture/v01_skeleton_plan.md`` §3.1 r3 promises the CLI's
``nucleus run`` will consume after Mo 4-6.

# Stability: Beta

What this module does (v0.1 scope)
----------------------------------
v4.1 §6.2 names five steps the AMA performs end-to-end:

    1. Pre-write: validate output against the asset contract
    2. Pre-write: enforce partition constraints
    3. Delegate atomic write to the catalog (ADR-001)
    4. Post-write: emit OpenLineage event
    5. Post-write: update asset registry (run history, freshness, cost)

In v0.1 this module owns steps 1 and 3. The data path calls the user's
asset body **directly** (no Dagster IO manager) and commits the returned
Polars DataFrame or PyArrow Table to Iceberg via ``pyiceberg``:

* ``sdk/contracts.py``               — schema contracts (v4.1 §15; wired
                                       2026-05-13; NucleusCheckExecutionError = NE3007
                                       per ADR-006 §1 Coordination-layer carve-out)
* ``coordination/lineage.py``        — OpenLineage emit (wired 2026-05-12)

Dagster remains a pinned dep for future scheduling, sensors, asset-graph
topology, and Workbench visualization (v0.2+). The data-write path is owned
by the AMA, not Dagster — Option A per the 2026-05-14 beachhead E2E fix
(``nucleus run example_asset`` was pickling to /tmp/ instead of committing
to Iceberg; Dagster log streams were leaking to user stdout).

What this module is NOT (anti-over-engineering, founder directive 2026-05-13)
-----------------------------------------------------------------------------
* No batch materialization — single asset only per call
* No partition iteration / sweep — single partition value passes through
* No retry loop — Dagster owns asset-body retries via future
  ``@nucleus.asset(retry=...)`` per ADR-005 §4 carve-out
* No memoization / singleton catalog handle — per-call fresh
* No new ``NucleusError`` subclasses defined IN THIS FILE — uses the
  NE-coded set ratified by ADR-006.

Replaceability mandate (v4.1 §6.5)
----------------------------------
Zero Dagster types cross out through the returned :class:`MaterializationResult`.
All exceptions flow through :func:`nucleus.coordination.error_translation.translate`
so the user-facing ``NucleusError.rendered()`` carries zero ``dagster.`` strings
— enforced by ``scripts/dagster_leak_check.py`` in CI. When the
in-house ``nucleus-mini-scheduler`` (v4.1 §6.7) lands by v1.0, this
module is the swap point; the public AMA signature
:func:`materialize_asset` must survive unchanged.

Iceberg write discipline (per nucleus-iceberg-write SKILL.md)
--------------------------------------------------------------
``pyiceberg`` imports are confined to :func:`_commit_to_iceberg`.
All catalog ops cite docs URLs per AGENTS.md §11.12.
``CommitFailedException`` surfaces as ``NucleusCommitConflictError``;
``CommitStateUnknownException`` surfaces as ``NucleusCommitUnknownError``.
No multi-table transactions (ADR-001: catalog handles per-table atomicity).
v0.2 adds three reliability guards (ADR-024):
* DuckDB ``SET memory_limit`` at connection init (P0-1, NE2007).
* Advisory filesystem lock per asset (P0-2, NE3008).
* ``expire_old_snapshots`` after successful commit (P0-3, NE3009).
"""

from __future__ import annotations

import contextlib
import dataclasses
import inspect
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

from nucleus.coordination import lineage
from nucleus.coordination.error_translation import translate
from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusError,
    NucleusInternalError,
    NucleusMemoryLimitExceeded,
)

logger = logging.getLogger(__name__)
from nucleus.sdk import contracts
from nucleus.sdk.decorators import _AssetDefinition, get_asset
from nucleus.sdk.results import MaterializationResult

# Sentinel values for MaterializationResult fields that are not yet populated.
# ADR-013 §2 promises ``snapshot_id`` is an Iceberg snapshot ID and
# ``lineage_event_id`` is an OpenLineage RunEvent UUID. Both are empty strings
# when no Iceberg commit occurred (asset returned None/non-DataFrame, or
# ``warehouse_dir`` was not provided, or dry_run=True).
_NO_SNAPSHOT_YET: Final[str] = ""
_NO_LINEAGE_YET: Final[str] = ""
# Row count sentinel for paths that do not commit to Iceberg.
_NO_ROW_COUNT_YET: Final[int] = 0

# Accepted ``upstream=`` values mirrored from
# :mod:`nucleus.sdk.materialize` so direct callers (CLI, tests) hit the
# same validation surface even when they bypass the SDK boundary.
_UpstreamMode = Literal["skip", "materialize", "validate"]

# ---------------------------------------------------------------------------
# DuckDB perf settings (ADR-024 P0-1; perf doc §10 #2)
# ---------------------------------------------------------------------------

# Fraction of total RAM to target for DuckDB's memory_limit.
# Lowered 0.80 → 0.60 per ``docs/internal/research/performance_reliability_targets.md``
# §10 item #2 — the upstream default of 80 % combined with no GROUP BY hash
# spill on `memory_limit` exhaustion (https://duckdb.org/docs/1.3/guides/troubleshooting/oom_errors)
# silently OOM-kills the process on machines that also run Docker containers,
# IDEs, or browser tabs.  60 % leaves headroom for the host OS.
_DUCKDB_RAM_FRACTION: float = 0.60
# Absolute floor (2 GB) and ceiling (32 GB) regardless of physical RAM.
_DUCKDB_MEM_FLOOR_BYTES: int = 2 * 1024**3
_DUCKDB_MEM_CEIL_BYTES: int = 32 * 1024**3
# Fallback thread count when neither physical-core nor logical-core lookup works.
_DUCKDB_THREADS_FALLBACK: int = 4


def _compute_duckdb_memory_limit(override_str: str | None = None) -> str:
    """Return the ``SET memory_limit`` string for this machine.

    Priority:
    1. *override_str* — caller-supplied value from ``nucleus_project.yaml``
       ``memory_limit`` key (e.g. ``"8GB"``).
    2. ``psutil``-derived 60 % of total RAM, clamped to [2 GB, 32 GB].
       (Lowered from 80 % in v0.2 per perf doc §10 item #2.)
    3. ``"10GB"`` fallback when ``psutil`` is unavailable.

    Docs: https://duckdb.org/docs/guides/performance/how_to_tune_workloads.html
    Docs: https://psutil.readthedocs.io/en/latest/#psutil.virtual_memory
    Per ``docs/decisions/ADR-024-reliability-hardening-plan.md`` P0-1.
    """
    if override_str:
        return override_str

    try:
        import psutil  # Docs: https://psutil.readthedocs.io/en/latest/

        total_bytes = psutil.virtual_memory().total
        target_bytes = int(total_bytes * _DUCKDB_RAM_FRACTION)
        limit_bytes = max(_DUCKDB_MEM_FLOOR_BYTES, min(_DUCKDB_MEM_CEIL_BYTES, target_bytes))
        return f"{limit_bytes // (1024**3)}GB"
    except ImportError:
        logger.debug("psutil not available; using 10GB DuckDB memory_limit default")
        return "10GB"


def _compute_duckdb_threads() -> int:
    """Return the ``SET threads`` value for this machine.

    Prefers physical-core count over logical-core count: DuckDB's vectorized
    pipeline does not benefit from SMT/hyper-threads for analytical workloads
    (https://duckdb.org/docs/guides/performance/how_to_tune_workloads.html
    §"Threads"), and exceeding physical cores degrades cache-locality.

    Fallback chain:
    1. ``psutil.cpu_count(logical=False)`` — physical cores
    2. ``psutil.cpu_count()`` — logical cores
    3. ``_DUCKDB_THREADS_FALLBACK`` (4)

    Docs: https://psutil.readthedocs.io/en/latest/#psutil.cpu_count
    Per perf doc §10 item #2.
    """
    try:
        import psutil  # Docs: https://psutil.readthedocs.io/en/latest/

        physical = psutil.cpu_count(logical=False)
        if physical and physical > 0:
            return int(physical)
        logical = psutil.cpu_count()
        if logical and logical > 0:
            return int(logical)
    except ImportError:
        logger.debug(
            "psutil not available; using %d-thread DuckDB default", _DUCKDB_THREADS_FALLBACK
        )
    return _DUCKDB_THREADS_FALLBACK


def _apply_duckdb_memory_limit(
    conn: Any,
    memory_limit_str: str,
    spill_dir: Path,
    *,
    threads: int | None = None,
) -> None:
    """Apply DuckDB perf settings (memory_limit, temp_directory, threads) to *conn*.

    The function name is preserved for back-compat with the existing P0-1
    test suite; the keyword-only ``threads`` arg is the v0.2 addition per
    perf doc §10 item #2.

    Translates ``duckdb.OutOfMemoryException`` (and similar) into
    :class:`~nucleus.errors.NucleusMemoryLimitExceeded` (NE2007).

    Args:
        conn: An open DuckDB connection.
        memory_limit_str: Value for ``SET memory_limit``, e.g. ``"8GB"``.
        spill_dir: Directory for DuckDB spill-to-disk files.  Created if absent.
        threads: Optional explicit thread count.  When ``None``, the value is
            derived from :func:`_compute_duckdb_threads`.  Pass an integer
            (e.g. ``8``) to override.

    Docs: https://duckdb.org/docs/guides/performance/how_to_tune_workloads.html
    Docs: https://duckdb.org/docs/configuration/overview
    Per ADR-024 P0-1 + perf doc §10 #2.
    """
    try:
        spill_dir.mkdir(parents=True, exist_ok=True)
        conn.execute(f"SET memory_limit = '{memory_limit_str}'")
        conn.execute(f"SET temp_directory = '{spill_dir.resolve().as_posix()}'")
        thread_count = threads if threads is not None else _compute_duckdb_threads()
        conn.execute(f"SET threads = {thread_count}")
        logger.debug(
            "DuckDB memory_limit=%s, threads=%d, spill=%s",
            memory_limit_str,
            thread_count,
            spill_dir,
        )
    except Exception as exc:
        exc_name = type(exc).__name__.lower()
        if "memory" in exc_name or "oom" in exc_name or "outofmemory" in exc_name:
            raise NucleusMemoryLimitExceeded(
                user_message=(
                    f"DuckDB exceeded the {memory_limit_str} memory limit. "
                    "Increase ``memory_limit`` in nucleus_project.yaml or split "
                    "the asset into smaller partitions."
                ),
                fix_hint=(
                    "Add ``memory_limit: '16GB'`` (or higher) under the "
                    "``[storage]`` section of nucleus_project.yaml, then re-run."
                ),
                cause=exc,
            ) from exc
        raise translate(exc) from exc


def _resolve_asset_from_registry(asset_key: str) -> _AssetDefinition:
    """Return the asset's registered definition or raise NucleusAssetNotFound.

    The in-process registry is owned by :mod:`nucleus.sdk.decorators`
    (one ``_AssetDefinition`` per ``@nucleus.asset``-decorated function).
    The SDK boundary already filters obviously-malformed keys, but a
    direct AMA caller may pass anything; surface a typed error per
    ADR-013 §4 (NE3002 reused).
    """
    entry = get_asset(asset_key)
    if entry is None:
        raise NucleusAssetNotFound(
            user_message=f"Asset {asset_key!r} is not defined.",
            fix_hint=(
                "Register the asset with @nucleus.asset(<key>) and import the "
                "module that defines it, then call materialize again. List "
                "registered assets with `nucleus list` (v0.1+)."
            ),
            asset=asset_key,
        )
    return entry


def _invoke_asset_body(entry: _AssetDefinition) -> Any:
    """Directly invoke the user's asset body function.

    Handles 0-arg and 1-arg (ctx) signatures per the asset model spec §14.
    Translates all non-NucleusError exceptions to NucleusError per v4.1 §6.4.
    No Dagster involved — the AMA owns the data path (Option A).

    v0.1 passes ``None`` as the placeholder ``ctx`` argument; the real
    :class:`nucleus.Ctx` lights up alongside ``ctx/_context.py``
    (v01_skeleton_plan §3.1 r4). User bodies that just ``return`` something
    (the common v0.1 case) are unaffected.
    """
    user_fn = entry.fn
    user_arity = len(inspect.signature(user_fn).parameters)
    if user_arity > 1:
        raise NucleusInternalError(
            user_message=(
                f"Asset {entry.key!r} body has {user_arity} parameters; v0.1 "
                "asset bodies must take zero or one positional argument (the ctx)."
            ),
            fix_hint=(
                "Reduce the asset body signature to `def fn()` or `def fn(ctx)`. "
                "Multiple-arg bodies are reserved for v0.3+ once upstream-asset "
                "injection lands."
            ),
            asset=entry.key,
        )
    try:
        if user_arity == 0:
            return user_fn()
        # v0.1 placeholder: ctx is None until Phase C wires the real Ctx.
        return user_fn(None)
    except NucleusError:
        # Already typed — pass through unchanged. Reachable when the user's
        # asset body raises a NucleusError directly (e.g. NucleusSchemaError).
        raise
    except BaseException as exc:
        # Per v4.1 §6.4: every external exception MUST translate.
        # ``raise X from exc`` sets ``__cause__`` so debug-mode traces still
        # show the full chain via ``--debug`` on the CLI.
        raise translate(exc) from exc


def _commit_to_iceberg(
    value: Any,
    asset_key: str,
    warehouse_dir: Path,
    *,
    memory_limit_str: str | None = None,
    snapshot_retain_days: int = 30,
    snapshot_min_keep: int = 10,
) -> tuple[str, int]:
    """Commit a Polars DataFrame or PyArrow Table to a filesystem Iceberg table.

    Called by :func:`materialize_asset` for non-dry_run paths when
    ``warehouse_dir`` is provided. Per v4.1 §6.2 step 3 (catalog atomic commit)
    + ADR-001 (no custom commit service — catalog handles atomicity).

    v0.2 additions (ADR-024):
    * Applies ``SET memory_limit`` on the DuckDB connection (P0-1).
    * Calls ``expire_old_snapshots`` after a successful commit when the table
      has more than 100 snapshots (P0-3).

    Returns:
        ``(snapshot_id, row_count)`` — both sentinel-valued when ``value`` is
        not a committable type (``None`` or any non-DataFrame/Table value).

    Docs: https://py.iceberg.apache.org/api/#catalogs (pyiceberg==0.11.1)
    Docs: https://py.iceberg.apache.org/api/#tables
    Docs: https://docs.pola.rs/api/python/stable/ (polars==1.18.0)
    Docs: https://arrow.apache.org/docs/python/api.html (pyarrow==18.1.0)
    """
    # Lazy imports keep boot-time cost off the hot path per PoC #4.
    import duckdb  # Docs: https://duckdb.org/docs/api/python/overview (duckdb==1.2.2)
    import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/
    import pyarrow as pa  # Docs: https://arrow.apache.org/docs/python/api.html

    # ADR-024 P0-1 + perf doc §10 #2: apply memory_limit, temp_directory, and
    # threads at AMA connection init before any query.  Lowered RAM fraction
    # 0.80 → 0.60 in v0.2 — see _DUCKDB_RAM_FRACTION docstring.
    # Docs: https://duckdb.org/docs/guides/performance/how_to_tune_workloads.html
    #
    # The mkdir is wrapped in translate() to catch FileExistsError when the
    # warehouse path already exists as a non-directory entry (chaos J3 / CF-1
    # — see docs/release/chaos_test_results.md §J3).  Path.mkdir(exist_ok=True)
    # only suppresses FileExistsError when the existing entry IS a directory.
    # Docs: https://docs.python.org/3/library/pathlib.html#pathlib.Path.mkdir
    try:
        warehouse_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # noqa: BLE001 - boundary; translate() catches FileExistsError + others.
        raise translate(exc) from exc
    spill_dir = warehouse_dir.parent / ".nucleus" / "duckdb_spill"
    mem_limit = _compute_duckdb_memory_limit(memory_limit_str)
    _duckdb_conn = duckdb.connect()
    _apply_duckdb_memory_limit(_duckdb_conn, mem_limit, spill_dir)

    # Docs: https://py.iceberg.apache.org/api/catalog/ (pyiceberg==0.11.1)
    from pyiceberg.catalog import load_catalog
    from pyiceberg.exceptions import (
        CommitFailedException,
        NamespaceAlreadyExistsError,
        TableAlreadyExistsError,
    )

    # Iceberg schema types for manual schema construction from Arrow.
    # Docs: https://py.iceberg.apache.org/api/#schemas (pyiceberg==0.11.1)
    from pyiceberg.schema import Schema
    from pyiceberg.types import (
        BinaryType,
        BooleanType,
        DateType,
        DoubleType,
        FloatType,
        IntegerType,
        LongType,
        NestedField,
        StringType,
        TimestampType,
        TimestamptzType,
    )

    if isinstance(value, pl.DataFrame):
        pa_table = value.to_arrow()
    elif isinstance(value, pa.Table):
        pa_table = value
    else:
        # Asset returned None or a non-committable type. Return sentinels;
        # the body still ran successfully (side effects are preserved).
        return _NO_SNAPSHOT_YET, _NO_ROW_COUNT_YET

    row_count = pa_table.num_rows
    namespace, table_name = asset_key.split(".", 1)

    catalog_db = warehouse_dir / "catalog.db"

    def _arrow_type_to_iceberg(t: pa.DataType) -> Any:
        """Map a PyArrow DataType to the corresponding PyIceberg type."""
        if pa.types.is_boolean(t):
            return BooleanType()
        if pa.types.is_int8(t) or pa.types.is_int16(t) or pa.types.is_int32(t):
            return IntegerType()
        if (
            pa.types.is_int64(t)
            or pa.types.is_uint32(t)
            or pa.types.is_uint64(t)
            or pa.types.is_uint16(t)
            or pa.types.is_uint8(t)
        ):
            return LongType()
        if pa.types.is_float32(t):
            return FloatType()
        if pa.types.is_float64(t):
            return DoubleType()
        if pa.types.is_string(t) or pa.types.is_large_string(t):
            return StringType()
        if pa.types.is_binary(t) or pa.types.is_large_binary(t):
            return BinaryType()
        if pa.types.is_date32(t):
            return DateType()
        if pa.types.is_timestamp(t) and getattr(t, "tz", None):
            return TimestamptzType()
        if pa.types.is_timestamp(t):
            return TimestampType()
        # Fallback to StringType for complex/unsupported types (v0.1 scope).
        return StringType()

    iceberg_fields = [
        NestedField(i + 1, f.name, _arrow_type_to_iceberg(f.type), required=not f.nullable)
        for i, f in enumerate(pa_table.schema)
    ]
    ice_schema = Schema(*iceberg_fields)

    try:
        # Windows-safe two-slash URI form per copy_from.py and pyiceberg bug #1005.
        # RFC 8089 §E.2: https://datatracker.ietf.org/doc/html/rfc8089
        # Docs: https://py.iceberg.apache.org/configuration/#fileio
        catalog = load_catalog(
            "default",
            type="sql",
            uri=f"sqlite:///{catalog_db.resolve().as_posix()}",
            warehouse=f"file://{warehouse_dir.resolve().as_posix()}",
        )

        with contextlib.suppress(NamespaceAlreadyExistsError):
            catalog.create_namespace(namespace)

        identifier = (namespace, table_name)
        try:
            ice_table = catalog.create_table(identifier, schema=ice_schema)
        except TableAlreadyExistsError:
            ice_table = catalog.load_table(identifier)

        ice_table.append(pa_table)

        snapshot = ice_table.current_snapshot()
        snapshot_id = str(snapshot.snapshot_id) if snapshot is not None else _NO_SNAPSHOT_YET

        # ADR-024 P0-3: expire old snapshots after successful commit when count
        # exceeds the trigger threshold.  Failures are logged but do NOT roll
        # back the committed snapshot (maintenance is best-effort).
        # Docs: https://py.iceberg.apache.org/api/ (pyiceberg==0.11.1)
        try:
            from nucleus.coordination.snapshot_maintenance import (
                _TRIGGER_THRESHOLD,
                expire_old_snapshots,
            )

            if len(ice_table.snapshots()) > _TRIGGER_THRESHOLD:
                expired = expire_old_snapshots(
                    ice_table,
                    retain_days=snapshot_retain_days,
                    min_snapshots=snapshot_min_keep,
                )
                if expired:
                    logger.debug(
                        "snapshot_maintenance: expired %d snapshot(s) for %s",
                        expired,
                        asset_key,
                    )
        except Exception:
            # Maintenance failures are non-fatal — the commit already succeeded.
            logger.warning(
                "snapshot_maintenance: failed for %s (commit succeeded)",
                asset_key,
                exc_info=True,
            )

    except NucleusError:
        raise
    except CommitFailedException as exc:
        raise translate(exc) from exc
    except Exception as exc:
        raise translate(exc) from exc

    return snapshot_id, row_count


def materialize_asset(
    asset_key: str,
    *,
    partition: str | None = None,
    upstream: _UpstreamMode = "skip",
    timeout_seconds: int | None = None,  # noqa: ARG001 — accepted, not enforced (v0.1)
    dry_run: bool = False,
    warehouse_dir: Path | None = None,
    memory_limit: str | None = None,
    lock_timeout: float = 30.0,
    snapshot_retain_days: int = 30,
    snapshot_min_keep: int = 10,
    _via_mini_scheduler: bool = False,
) -> MaterializationResult:
    """Materialize a single Nucleus asset and return its outcome record.

    # Stability: Beta

    Coordination-layer entry point for the AMA per v4.1 §6.2.
    :func:`nucleus.materialize` (the SDK boundary) eagerly validates its
    inputs and delegates here once the asset is known to exist and
    ``upstream`` is ``"skip"``. Direct callers (e.g. the CLI ``nucleus run``)
    get the same surface but must accept the typed rejections this function
    emits when those preconditions don't hold.

    Args:
        asset_key: Canonical 2-level Nucleus key (``"schema.name"``).
            Must already be registered via ``@nucleus.asset``; unknown
            keys raise :class:`NucleusAssetNotFound` (NE3002 per
            ADR-013 §4).
        partition: Optional single partition value, propagated verbatim
            into :class:`MaterializationResult.partition`. v0.1 does not
            use this for Iceberg partition routing; the result-level
            contract is the testable surface today.
        upstream: One of ``"skip"`` / ``"materialize"`` / ``"validate"``.
            v0.1 supports ``"skip"`` only; the other two raise
            :class:`NucleusInternalError` with a "deferred to v0.3+"
            message per ADR-013 §NV #6.
        timeout_seconds: Wall-clock budget. Accepted but NOT enforced in
            v0.1 — cross-platform timeout requires machinery
            (threading/subprocess/signal) that the Anti-Over-Engineering
            directive defers until a v0.1 caller actually needs it.
        dry_run: When ``True``, executes the asset body but does NOT
            commit to Iceberg. Returns sentinel values for
            ``snapshot_id`` and ``row_count``.
        warehouse_dir: Filesystem path to the Iceberg warehouse root
            (same ``storage.warehouse`` as ``nucleus_project.yaml``).
            When ``None``, the Iceberg commit step is skipped and
            sentinel values are returned. The CLI ``nucleus run`` always
            provides this; direct SDK callers that omit it get the
            v0.1 deferred-commit behaviour.
        memory_limit: Override DuckDB ``SET memory_limit`` value, e.g.
            ``"8GB"``. When ``None``, 80 % of total RAM is used (clamped
            to [2 GB, 32 GB]).  Configurable via ``nucleus_project.yaml``
            ``memory_limit`` key. (ADR-024 P0-1.)
        lock_timeout: Seconds to wait for the advisory asset lock before
            raising :class:`~nucleus.errors.NucleusConcurrentRunError`
            (NE3008). Default 30 s.  (ADR-024 P0-2.)
        snapshot_retain_days: Snapshots older than this many days are
            eligible for expiry after a successful commit.  (ADR-024 P0-3.)
        snapshot_min_keep: Minimum number of recent snapshots to keep
            regardless of age.  (ADR-024 P0-3.)

    Returns:
        A frozen :class:`MaterializationResult` per ADR-013 §2.

    Raises:
        NucleusAssetNotFound: ``asset_key`` is not in the in-process
            registry.
        NucleusConcurrentRunError: Another run is already materialising
            this asset and the lock was not obtained within ``lock_timeout``.
        NucleusInternalError: ``upstream`` is not ``"skip"`` (v0.1 scope
            limit), or the AMA itself hit an invariant violation.
        NucleusError: Any other typed error produced by the
            :func:`nucleus.coordination.error_translation.translate`
            boundary when the asset body raises.
    """
    if upstream != "skip":
        raise NucleusInternalError(
            user_message=(
                f"materialize_asset(..., upstream={upstream!r}) is part of "
                "v0.3+ scope; v0.1 supports upstream='skip' only."
            ),
            fix_hint=(
                "Drop the upstream= kwarg or pass upstream='skip'. Recursive "
                "materialization lights up at v0.3+ per ADR-013 NV #6 once "
                "telemetry sets a safe-depth threshold."
            ),
            docs_url="https://nucleus.dev/errors/not-implemented",
            asset=asset_key,
        )

    # Composability swap proof (v4.1 §6.7 + §9.3): when the env var
    # NUCLEUS_USE_MINI_SCHEDULER=1 is exported, route through the
    # mini-scheduler entry point in ``coordination/daemon.py`` so the
    # alternative path is exercised end-to-end.  The ``_via_mini_scheduler``
    # private flag breaks the recursion when the daemon re-enters here.
    # The default path (env var unset) is unchanged — this is a strictly
    # gated, opt-in route used by the integration test in
    # ``tests/integration/test_dagster_to_mini_scheduler_swap.py``.
    if not _via_mini_scheduler and os.environ.get("NUCLEUS_USE_MINI_SCHEDULER") == "1":
        from nucleus.coordination.daemon import run_asset as _mini_run

        # _mini_run is annotated -> Any (alternative scheduler entry point); at
        # runtime it always returns a MaterializationResult shape.
        result: MaterializationResult = _mini_run(
            asset_key,
            partition=partition,
            dry_run=dry_run,
            warehouse_dir=warehouse_dir,
            memory_limit=memory_limit,
            lock_timeout=lock_timeout,
            snapshot_retain_days=snapshot_retain_days,
            snapshot_min_keep=snapshot_min_keep,
        )
        return result

    entry = _resolve_asset_from_registry(asset_key)

    # ADR-024 P0-2: acquire per-asset advisory lock before the commit path.
    # When warehouse_dir is None (dry_run / deferred-commit) we skip the lock
    # because there is nothing to race on.
    # Docs: nucleus.coordination.locks (stdlib fcntl / msvcrt)
    from nucleus.coordination.locks import asset_lock

    project_root = warehouse_dir.parent if warehouse_dir is not None else Path.cwd()
    lock_ctx = (
        asset_lock(project_root, asset_key, timeout=lock_timeout)
        if warehouse_dir is not None
        else contextlib.nullcontext()
    )

    # OpenLineage bookend hooks per v4.1 §6.2 step 4 + research/openlineage.md
    # §5.1. All emit calls are best-effort: lineage failure never fails
    # materialization.
    run_id = str(uuid.uuid4())
    lineage.emit_start(run_id, asset_key)

    try:
        with lock_ctx:
            started_at = datetime.now(UTC)
            t0 = time.perf_counter()

            value = _invoke_asset_body(entry)

            if dry_run or warehouse_dir is None:
                snapshot_id: str = _NO_SNAPSHOT_YET
                row_count: int = _NO_ROW_COUNT_YET
            else:
                snapshot_id, row_count = _commit_to_iceberg(
                    value,
                    asset_key,
                    warehouse_dir,
                    memory_limit_str=memory_limit,
                    snapshot_retain_days=snapshot_retain_days,
                    snapshot_min_keep=snapshot_min_keep,
                )

        duration_ms = int((time.perf_counter() - t0) * 1000)

        result = MaterializationResult(
            asset_key=asset_key,
            snapshot_id=snapshot_id,
            partition=partition,
            row_count=row_count,
            duration_ms=duration_ms,
            lineage_event_id=_NO_LINEAGE_YET,
            materialized_at=started_at,
        )

        # v4.1 §15 schema contracts: run every @nucleus.check body registered
        # against this asset_key AFTER successful materialization, then attach
        # the outcomes via dataclasses.replace (MaterializationResult is
        # frozen per ADR-013 §2). Placement is AFTER result construction so
        # the check sees a settled result, and BEFORE lineage.emit_complete
        # so v0.5 can include check counts in the OL event additively.
        # Skipped on dry_run because checks need real materialized data.
        if not dry_run:
            check_results = contracts.run_checks_for_asset(asset_key)
            if check_results:
                result = dataclasses.replace(result, checks=check_results)

    except NucleusError as exc:
        # FAIL emit before re-raise. Pass the typed error_code (or NE3001
        # fallback) and the clean user_message — never raw repr (no external
        # classnames leak via lineage).
        lineage.emit_fail(
            run_id,
            asset_key,
            error_code=getattr(exc, "error_code", "NE3001"),
            error_message=exc.user_message,
        )
        raise

    # COMPLETE emit. dry_run records synthetic outcome values so the lineage
    # log shows what would have happened.
    if dry_run:
        snapshot_for_lineage: str | None = "dry-run"
        rows_for_lineage: int | None = 0
    else:
        snapshot_for_lineage = result.snapshot_id or None
        rows_for_lineage = result.row_count or None
    lineage.emit_complete(
        run_id,
        asset_key,
        snapshot_id=snapshot_for_lineage,
        row_count=rows_for_lineage,
        materialized_at=result.materialized_at.isoformat(),
    )
    return result


__all__ = [
    "materialize_asset",
]
