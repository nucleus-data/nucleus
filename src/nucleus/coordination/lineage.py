"""OpenLineage asset-level emitter (L2 Coordination).

Per ``nucleus_architecture_v4.1.md`` §6.2 step 4 (post-write OpenLineage
emit) + §13.2 (asset-level lineage at v0.1; column-level deferred to
v0.5+) + ``.cursor/rules/nucleus.mdc`` lineage row (OpenLineage + sqlglot,
Tier 0 immortal). Companion research notes:
``docs/research/openlineage.md``.

What this module does (v0.1 scope)
----------------------------------
Three module-level functions wrap the OpenLineage Python SDK so the
Asset Materialization Adapter (:mod:`nucleus.coordination.asset_materialization`)
can record a START / COMPLETE / FAIL ``RunEvent`` for every
``nucleus.materialize(...)`` call. Events land as one JSON object per
line in ``<NUCLEUS_LINEAGE_DIR>/<run_id>.ndjson`` (default
``.nucleus/lineage/`` relative to :func:`pathlib.Path.cwd`).

The emitter is **best-effort**: any failure during emission is wrapped
in a :class:`NucleusLineageEmissionError`, logged at WARN, and swallowed.
A lineage failure MUST NOT fail the materialization itself — that
invariant is asserted in ``tests/coordination/test_lineage.py``.

What this module is NOT (anti-over-engineering, founder directive 2026-05-13)
-----------------------------------------------------------------------------
* No HTTP / Kafka / Marquez transport — v0.5+ per
  ``docs/research/openlineage.md`` §5.3
* No column-level lineage — v0.5+ via sqlglot per v4.1 §13.2
* No async emit / queue — sync FileTransport, one ``client.emit()`` per call
* No batching — NDJSON is append-safe; one line per event
* No ``LineageEmitter`` class — three free functions, second caller will
  trigger refactor per the founder directive

Soft-dependency stance (v0.1)
-----------------------------
``openlineage-python`` is pinned in ``pyproject.toml``; a clean install
always has it. If a user uninstalls it, this module degrades gracefully
(``_OL_AVAILABLE = False``; every emit becomes a logged warning + no-op).
Tested via :mod:`tests.coordination.test_lineage` ``TestSoftDependency``.

Producer + namespace constants
------------------------------
Per OpenLineage spec, every ``RunEvent`` carries a ``producer`` URI
identifying the emitter. The recommended form is a git URL with a tag.
v0.1 ships pre-launch with no public URL yet — ``https://nucleus.dev/v0.1``
is the working default per ADR-002 §8.1; flagged for founder review.
"""

from __future__ import annotations

import logging
import os
import pathlib
from datetime import UTC, datetime
from typing import Any

from nucleus.errors import NucleusLineageEmissionError

_LOG = logging.getLogger(__name__)

# Stable identifiers per OpenLineage spec; see docs/research/openlineage.md §4.
# PRODUCER URI is reviewed by founder per task surfacing; JOB_NAMESPACE matches
# the asset-graph identity Nucleus owns forever (AGENTS.md §0).
PRODUCER: str = "https://nucleus.dev/v0.1"
JOB_NAMESPACE: str = "nucleus"

# Soft-dep import per docs/research/openlineage.md §10 (use event_v2 — the
# legacy openlineage.client.run path emits DeprecationWarning at import).
# Docs: https://openlineage.io/docs/client/python  (pinned: 1.47.1)
try:
    from openlineage.client import OpenLineageClient
    from openlineage.client.event_v2 import Job, Run, RunEvent, RunState
    from openlineage.client.facet_v2 import RunFacet
    from openlineage.client.generated.error_message_run import ErrorMessageRunFacet
    from openlineage.client.generated.parent_run import ParentRunFacet
    from openlineage.client.transport.file import FileConfig, FileTransport

    _OL_AVAILABLE = True
except ImportError:
    _OL_AVAILABLE = False
    # Bind placeholders so static analysis + downstream symbol probes don't
    # crash on attribute lookups; runtime code paths gate on _OL_AVAILABLE.
    OpenLineageClient = None  # type: ignore[assignment,misc]
    Job = Run = RunEvent = RunState = None  # type: ignore[assignment,misc]
    RunFacet = None  # type: ignore[assignment,misc]
    ErrorMessageRunFacet = None  # type: ignore[assignment,misc]
    ParentRunFacet = None  # type: ignore[assignment,misc]
    FileConfig = FileTransport = None  # type: ignore[assignment,misc]


def _lineage_dir() -> pathlib.Path:
    """Resolve the lineage NDJSON output directory.

    # Stability: Internal

    Honors the ``NUCLEUS_LINEAGE_DIR`` environment variable; otherwise
    defaults to ``.nucleus/lineage/`` under :func:`pathlib.Path.cwd`.
    The directory is created on demand by the emit helpers — this
    function does NOT create it (callers may probe the default path
    in dry contexts).
    """
    env = os.environ.get("NUCLEUS_LINEAGE_DIR")
    if env:
        return pathlib.Path(env)
    return pathlib.Path.cwd() / ".nucleus" / "lineage"


def _build_outcome_facet(**properties: Any) -> Any:
    """Build a Nucleus-namespaced RunFacet carrying v0.1 outcome data.

    Per OpenLineage spec, custom facets are explicitly supported via
    ``BaseFacet.with_additional_properties(**kwargs)``. v0.5+ will move
    ``snapshotId`` onto a proper ``DatasetVersionDatasetFacet`` once the
    Iceberg writer lands and there is a real OutputDataset to attach it
    to (see ``docs/research/openlineage.md`` §5.1).
    """
    return RunFacet().with_additional_properties(**properties)


def _emit(
    run_id: str,
    asset_key: str,
    *,
    state_label: str,
    state: Any,
    event_time: str,
    parent_run_id: str | None,
    extra_facets: dict[str, Any] | None = None,
) -> None:
    """Construct + emit one RunEvent. Best-effort; never raises.

    Any failure is wrapped in :class:`NucleusLineageEmissionError`,
    logged at WARN, and swallowed. The AMA bookend hooks depend on
    this never-fail contract per v4.1 §6.2 step 4.
    """
    if not _OL_AVAILABLE:
        _LOG.warning(
            "lineage: openlineage-python not installed; skipping %s event "
            "for asset %r (run %s)",
            state_label,
            asset_key,
            run_id,
        )
        return

    try:
        lineage_dir = _lineage_dir()
        lineage_dir.mkdir(parents=True, exist_ok=True)
        log_path = lineage_dir / f"{run_id}.ndjson"

        facets: dict[str, Any] = dict(extra_facets or {})
        if parent_run_id is not None:
            # Docs: https://openlineage.io/docs/spec/facets/run-facets/parent_run/
            # ParentRunFacet.create() is deprecated since openlineage-python 1.x; use constructor.
            facets["parent"] = ParentRunFacet(
                run=Run(runId=parent_run_id),
                job=Job(namespace=JOB_NAMESPACE, name=asset_key),
            )

        run = Run(runId=run_id, facets=facets or None)
        job = Job(namespace=JOB_NAMESPACE, name=asset_key)
        event = RunEvent(
            eventType=state,
            eventTime=event_time,
            run=run,
            job=job,
            producer=PRODUCER,
        )

        # Docs: https://openlineage.io/docs/client/python/usage  (FileTransport
        # with append=True writes one JSON line per event to log_file_path).
        config = FileConfig(log_file_path=str(log_path), append=True)
        client = OpenLineageClient(transport=FileTransport(config))
        client.emit(event)
    except Exception as exc:
        translated = NucleusLineageEmissionError(
            user_message=(
                f"Lineage emission failed for asset {asset_key!r} "
                f"(run {run_id})."
            ),
            fix_hint=(
                "Check that the lineage directory is writable "
                "(NUCLEUS_LINEAGE_DIR or default .nucleus/lineage/). "
                "Materialization itself was not affected — this is a "
                "best-effort audit step."
            ),
            asset=asset_key,
            cause=exc,
        )
        _LOG.warning("%s", translated.rendered())


def emit_start(
    run_id: str,
    asset_key: str,
    *,
    parent_run_id: str | None = None,
) -> None:
    """Emit a START RunEvent before materialization begins.

    # Stability: Beta
    """
    _emit(
        run_id,
        asset_key,
        state_label="START",
        state=RunState.START if _OL_AVAILABLE else None,
        event_time=datetime.now(UTC).isoformat(),
        parent_run_id=parent_run_id,
    )


def emit_complete(
    run_id: str,
    asset_key: str,
    *,
    snapshot_id: str | None,
    row_count: int | None,
    materialized_at: str,
    parent_run_id: str | None = None,
) -> None:
    """Emit a COMPLETE RunEvent after a successful materialization.

    Per OpenLineage spec the ``runId`` MUST match the prior START event.
    ``materialized_at`` is the ISO-8601 timestamp the AMA captured for
    :class:`nucleus.MaterializationResult.materialized_at`.

    # Stability: Beta
    """
    extras: dict[str, Any] = {}
    if _OL_AVAILABLE:
        extras["_nucleusOutcome"] = _build_outcome_facet(
            snapshotId=snapshot_id,
            rowCount=row_count,
        )
    _emit(
        run_id,
        asset_key,
        state_label="COMPLETE",
        state=RunState.COMPLETE if _OL_AVAILABLE else None,
        event_time=materialized_at,
        parent_run_id=parent_run_id,
        extra_facets=extras,
    )


def emit_fail(
    run_id: str,
    asset_key: str,
    *,
    error_code: str,
    error_message: str,
    parent_run_id: str | None = None,
) -> None:
    """Emit a FAIL RunEvent after a failed materialization.

    Uses the standard OpenLineage ``errorMessage`` facet so any spec-
    compliant consumer (Marquez v0.3+, Atlan, Datadog) surfaces the
    typed :class:`nucleus.NucleusError` cleanly. The Nucleus-specific
    ``errorCode`` (e.g. ``"NE3002"``) is attached as an additional
    property on the same facet — keeps the spec-required ``message`` /
    ``programmingLanguage`` / ``stackTrace`` shape intact.

    # Stability: Beta
    """
    extras: dict[str, Any] = {}
    if _OL_AVAILABLE:
        # Docs: https://openlineage.io/docs/spec/facets/run-facets/error-message/
        extras["errorMessage"] = ErrorMessageRunFacet(
            message=error_message,
            programmingLanguage="python",
            stackTrace=None,
        ).with_additional_properties(errorCode=error_code)
    _emit(
        run_id,
        asset_key,
        state_label="FAIL",
        state=RunState.FAIL if _OL_AVAILABLE else None,
        event_time=datetime.now(UTC).isoformat(),
        parent_run_id=parent_run_id,
        extra_facets=extras,
    )


__all__ = [
    "emit_complete",
    "emit_fail",
    "emit_start",
]
