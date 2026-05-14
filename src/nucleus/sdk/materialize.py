"""``nucleus.materialize(...)`` — the public materialize-an-asset entry point.

Per ``docs/decisions/ADR-013-ctx-materialize-api.md`` §1 (signature) +
§2 (return type) + §4 (NE-code allocations) +
``nucleus_architecture_v4.1.md`` §6.2 (Asset Materialization Adapter,
the runtime this function front-runs) + §13.2 (the Surface Summary row
this module publishes).

v0.1 implementation strategy
----------------------------
This module is the **public type-stable face** of the AMA. It validates
inputs eagerly per the ADR-013 signature, looks up the asset definition
in the in-process registry (:mod:`nucleus.sdk.decorators`), and
delegates to :func:`nucleus.coordination.asset_materialization.materialize_asset`
to drive the v4.1 §6.2 pipeline behind the wrapped Dagster runtime.

Validation errors that are *user-fixable* (bad key, bad upstream value,
bad timeout) are routed to typed ``NucleusError`` subclasses per
ADR-013 §4 here at the SDK boundary; library-origin failures inside
the asset body are translated to typed ``NucleusError`` subclasses at
the Dagster boundary inside the AMA via
:func:`nucleus.coordination.error_translation.translate` per v4.1 §6.4.
Zero Dagster types cross out of either layer.

Stability tier (per ADR-005 §2)
-------------------------------
**Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0**, the same ladder as
:mod:`nucleus.sdk.results`.

NE-code use (per ADR-006 §Initial code assignment + ADR-013 §4)
---------------------------------------------------------------
The error subclasses raised here all already exist in
:mod:`nucleus.errors` — this module does NOT add new subclasses. The
two new codes ADR-013 §4 calls out (``NE3004``
``NucleusMaterializationError``; ``NE3005`` for ``NucleusTimeoutError``)
are co-acceptance-gated with ADR-006 and land in the parallel
governance worker's PR.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, get_args

from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusInternalError,
    NucleusInvalidAssetDefinition,
)
from nucleus.sdk.decorators import get_asset
from nucleus.sdk.results import AssetRef, MaterializationResult

# The three accepted upstream= kwarg values per ADR-013 §1. ``Literal``
# narrows the call site for mypy --strict; runtime validation below
# preserves the same accept-set when callers supply a bare string.
UpstreamMode = Literal["skip", "materialize", "validate"]

# Default for v0.1 per ADR-013 §1 + §NV #6 ("v0.1 accepts upstream='skip'
# only; 'materialize'/'validate' deferred to v0.3+ once telemetry sets a
# safe-depth threshold").
_DEFAULT_UPSTREAM: Final[UpstreamMode] = "skip"
_VALID_UPSTREAMS: Final[tuple[str, ...]] = get_args(UpstreamMode)


def _coerce_asset_key(asset: str | AssetRef) -> str:
    """Validate and unwrap ``asset`` to a bare key.

    Per ADR-013 §1 ``asset`` accepts ``str | AssetRef``; both forms are
    normalised to ``str`` before lookup so the registry lookup path is
    one shape only.
    """
    if isinstance(asset, AssetRef):
        return asset.key
    if isinstance(asset, str) and asset:
        return asset
    raise NucleusInvalidAssetDefinition(
        user_message=(
            f"nucleus.materialize(asset=...) requires a non-empty asset key "
            f"(or AssetRef); got {type(asset).__name__!r}."
        ),
        fix_hint=(
            "Pass the canonical 2-level key, e.g. "
            "nucleus.materialize('staging.orders'). "
            "AssetRef is also accepted (nucleus_ctx_sdk_spec.md §3.1)."
        ),
    )


def _validate_upstream(upstream: str) -> UpstreamMode:
    """Reject unknown ``upstream=`` values eagerly per ADR-013 §1."""
    if upstream not in _VALID_UPSTREAMS:
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"nucleus.materialize(..., upstream={upstream!r}) is not a "
                "supported value."
            ),
            fix_hint=(
                "upstream must be one of "
                f"{sorted(_VALID_UPSTREAMS)!r}. "
                "v0.1 accepts only 'skip' (default); 'materialize'/'validate' "
                "land at v0.3+ per ADR-013 NV #6."
            ),
        )
    return upstream  # type: ignore[return-value]


def _validate_timeout(timeout_seconds: int | None) -> int | None:
    """Reject non-positive timeouts before they reach the AMA."""
    if timeout_seconds is None:
        return None
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"nucleus.materialize(..., timeout_seconds={timeout_seconds!r}) "
                "must be a positive integer or None."
            ),
            fix_hint="Pass a wall-clock budget in whole seconds, e.g. timeout_seconds=600.",
        )
    if timeout_seconds <= 0:
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"nucleus.materialize(..., timeout_seconds={timeout_seconds}) "
                "must be > 0."
            ),
            fix_hint="Pass None to disable the timeout, or a positive number of seconds.",
        )
    return timeout_seconds


def materialize(
    asset: str | AssetRef,
    *,
    partition: str | None = None,
    upstream: str = _DEFAULT_UPSTREAM,
    timeout_seconds: int | None = None,
    warehouse_dir: Path | None = None,
) -> MaterializationResult:
    """Materialize a Nucleus asset to its declared destination.

    # Stability: Beta

    Public entry point per
    ``docs/decisions/ADR-013-ctx-materialize-api.md`` §1 +
    ``nucleus_architecture_v4.1.md`` §6.2 (the AMA five-step pipeline:
    validate → partition-enforce → catalog atomic commit (ADR-001) →
    OpenLineage emit → registry update).

    Args:
        asset: Asset to materialize. Either the canonical 2-level v0.1
            key (``"schema.name"``) or an :class:`AssetRef`. Unknown
            keys raise :class:`NucleusAssetNotFound` (NE3002) per
            ADR-013 §4.
        partition: Single partition value (e.g. ``"2026-05-13"``).
            ``None`` (default) materializes all eligible partitions.
            Tuple-form partitions land at v0.3+ alongside multi-partition
            keys (ADR-013 §Open Question 2).
        upstream: One of ``"skip"`` (default — fail loud if upstream
            unmaterialized), ``"materialize"`` (recurse upstream), or
            ``"validate"`` (assert upstream readiness without recursion).
            v0.1 ships ``"skip"`` only; the other two values raise
            :class:`NucleusInternalError` at the boundary until v0.3+
            (ADR-013 §NV #6).
        timeout_seconds: Wall-clock budget. ``None`` (default) means no
            timeout. Exceeded → :class:`NucleusTimeoutError` per
            ADR-013 §4 (NE3005 reservation pending ADR-006 co-acceptance).
        warehouse_dir: Optional filesystem path to the Iceberg warehouse
            root. When provided, the asset's return value (Polars DataFrame
            or PyArrow Table) is committed to Iceberg. When ``None``
            (default), the commit step is skipped and sentinel values are
            returned for ``snapshot_id`` + ``row_count``. The CLI always
            provides this; direct Python callers may omit it for side-effect-
            only assets or tests that do not need an Iceberg commit.

    Returns:
        A :class:`MaterializationResult` per ADR-013 §2: asset_key,
        snapshot_id, partition, row_count, duration_ms, lineage_event_id,
        materialized_at.

    Raises:
        NucleusInvalidAssetDefinition: An input argument failed eager
            validation (bad key shape, bad upstream value, bad timeout).
        NucleusAssetNotFound: ``asset`` is not registered in the in-process
            asset registry (NE3002 per ADR-013 §4).
        NucleusInternalError: ``upstream`` is ``"materialize"`` or
            ``"validate"`` — deferred to v0.3+ per ADR-013 §NV #6.
        NucleusError: Any typed error raised inside the asset body and
            translated at the Dagster boundary (NE1xxx / NE2xxx /
            NE3xxx per v4.1 §6.4 + ADR-006).

    Examples:
        Materialize a registered asset by key::

            result = nucleus.materialize("staging.orders")
            print(result.snapshot_id, result.row_count)

        With an :class:`AssetRef` (typically obtained via ``ctx.asset``)::

            result = nucleus.materialize(ctx.asset, partition="2026-05-13")

        Wall-clock budget::

            result = nucleus.materialize("marts.orders_clean", timeout_seconds=600)
    """
    asset_key = _coerce_asset_key(asset)
    upstream_norm = _validate_upstream(upstream)
    _validate_timeout(timeout_seconds)
    if partition is not None and not isinstance(partition, str):
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"nucleus.materialize(..., partition={partition!r}) must be a "
                "string or None."
            ),
            fix_hint=(
                "Pass a single-string partition value, e.g. partition='2026-05-13'. "
                "Tuple-form partitions land at v0.3+ per ADR-013 Open Question 2."
            ),
        )

    if get_asset(asset_key) is None:
        raise NucleusAssetNotFound(
            user_message=f"Asset {asset_key!r} is not defined.",
            fix_hint=(
                "Register the asset with @nucleus.asset(<key>) and import the "
                "module that defines it, then call materialize again. List "
                "registered assets with `nucleus list` (v0.1+)."
            ),
            asset=asset_key,
        )

    if upstream_norm != "skip":
        raise NucleusInternalError(
            user_message=(
                f"nucleus.materialize(..., upstream={upstream_norm!r}) is part of "
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

    # Delegate to the Asset Materialization Adapter (v4.1 §6.2). The
    # AMA is the only Coordination-layer module permitted to import
    # ``dagster``; this SDK module never sees a Dagster type cross its
    # return boundary per v4.1 §6.5. ADR-013 §1 + ADR-013 §5 promise
    # this delegation as the wired v0.1 path.
    from nucleus.coordination.asset_materialization import materialize_asset as _ama

    return _ama(
        asset_key,
        partition=partition,
        upstream=upstream_norm,
        timeout_seconds=timeout_seconds,
        warehouse_dir=warehouse_dir,
    )


__all__ = [
    "materialize",
]
