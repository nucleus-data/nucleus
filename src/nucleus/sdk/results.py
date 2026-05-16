"""Public value types for the Nucleus SDK surface (L4).

Per ``docs/specs/nucleus_architecture_v4.1.md`` §13.2 (Surface Summary table) and
``docs/decisions/ADR-013-ctx-materialize-api.md`` §2 (Return type), this
module owns the three frozen-shape value types end-users construct or
inspect by name:

    - :class:`MaterializationResult`   the outcome record returned by
                                       :func:`nucleus.materialize`
                                       (ADR-013 §1+§2; AGENTS.md §7
                                       distinguishes the *act*
                                       ``materialization`` from the
                                       *outcome record* with the ``Result``
                                       suffix per ADR-013 NV #4).
    - :class:`AssetRef`                a lightweight handle to a registered
                                       asset (``docs/specs/nucleus_ctx_sdk_spec.md``
                                       §3.1 + §12 frozen surface; ADR-013
                                       §1 accepts ``str | AssetRef``).
    - :class:`CheckResult`             the structured return type of every
                                       ``@nucleus.check`` body
                                       (``docs/specs/nucleus_asset_model_spec.md``
                                       §10; ``docs/specs/nucleus_ctx_sdk_spec.md``
                                       §2.4 + §12).

All three are ``@dataclass(frozen=True)`` per ADR-013 §2 — fields are
additive-only between Beta and Stable per ``ADR-005`` §1 (Beta tier may
break minor-to-minor) and ``ADR-013`` §3 (risk table: "field-add free
until Stable"). ``ADR-005`` §3 is the *breaking-change* protocol that
applies once a symbol reaches Stable or Frozen — field-add at Beta is
governed by §1, not §3. Mutating a field raises ``FrozenInstanceError``
which ``@nucleus.check`` and the materialize boundary intentionally rely
on.

Stability tier (per ADR-005 §2)
-------------------------------
All three are **Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0**, the same
ladder as ``ctx.read``/``ctx.write``/``ctx.sql``/``ctx.copy_from``. The
``# Stability:`` markers in each class docstring are read by
``scripts/check_api_stability.py``.

Placement decision
------------------
ADR-013 §2 names ``src/nucleus/sdk/types.py``; the founder action queue
overrides this to ``src/nucleus/sdk/results.py`` to keep frozen-shape
value types in one module (results) and reserve ``types.py`` for the
broader type-alias surface lighting up at v0.5+. Both ``AssetRef`` and
``CheckResult`` co-locate here for the same reason — they are public
types of identical shape discipline (frozen dataclasses, no behaviour).

Implementation notes
--------------------
Dependencies are stdlib only — :mod:`dataclasses` and :mod:`datetime`.
No engine, no catalog, no Dagster import on this module load path; the
data classes are the boundary between typed user code and the Asset
Materialization Adapter (v4.1 §6.2). Importing this module must stay
side-effect-free so CLI startup time and the v4.1 §11.2 cold-boot budget
are unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class AssetRef:
    """A lightweight reference to a registered Nucleus asset.

    # Stability: Beta

    Returned by ``ctx.asset`` (``docs/specs/nucleus_ctx_sdk_spec.md`` §3.1) and
    accepted as the first positional argument of :func:`nucleus.materialize`
    alongside the bare-string form (ADR-013 §1). Holds the canonical
    asset key — the v0.1 2-level (``schema.name``) form per
    ``docs/specs/nucleus_cli_spec.md`` §10 NV #6. The 3-level form (``catalog.schema.table``)
    lights up at v0.3+ alongside multi-catalog routing.

    Construction is normally done by the runtime, not user code; v0.1
    keeps the constructor public so smoke tests and PoC promotions can
    exercise the materialize signature without spinning a real asset graph.

    Attributes:
        key: The canonical asset key (e.g. ``"marts.orders_clean"``).
            Validated only at registration time — this dataclass does
            not re-check shape so consumers may carry parsing errors
            unchanged into a structured ``NucleusInvalidAssetDefinition``
            at the right boundary.
    """

    key: str

    def __str__(self) -> str:
        """Return the canonical key, so ``f"{ref}"`` works in user code."""
        return self.key


@dataclass(frozen=True)
class MaterializationResult:
    """Outcome record from a single ``nucleus.materialize(...)`` call.

    # Stability: Beta

    Per ``docs/decisions/ADR-013-ctx-materialize-api.md`` §2. The shape
    is field-additive between v0.1 (Beta) and v0.5 (Stable) per ADR-005
    §1 (Beta tier permits minor-to-minor breaks; field-add is the
    safest such change) + ADR-013 §3 risk row ("field-add free until
    Stable"). ADR-005 §3 covers the *removal/rename* protocol once a
    symbol reaches Stable or Frozen — it does NOT govern field-add at
    Beta. ``frozen=True`` blocks accidental in-place mutation by user
    code.

    The fields capture the v4.1 §6.2 five-step Asset Materialization
    Adapter result plus v4.1 §15 schema-contract enforcement:

    1. Identity — ``asset_key`` and (optional) ``partition``
    2. Storage — ``snapshot_id`` (Iceberg snapshot, v0.1; Lance version, v0.5+)
    3. Volume — ``row_count``, the rows landed in this materialization
    4. Cost — ``duration_ms``, wall-clock time of the AMA call
    5. Lineage — ``lineage_event_id`` from the OpenLineage RunEvent
       emitted at v4.1 §6.2 step 4
    6. Audit — ``materialized_at`` UTC timestamp recorded post-commit
    7. Quality — ``checks``, the outcome of every ``@nucleus.check`` body
       registered against ``asset_key`` (v4.1 §15 schema contracts; empty
       tuple when no checks are registered or on ``dry_run=True``)

    The internal :class:`coordination.RunResult` (``v01_skeleton_plan.md``
    §3.1 r3) is transformed into this public type at the SDK boundary
    per v4.1 §6.5 (Replaceability). Implementation lives in
    :mod:`nucleus.sdk.materialize`.
    """

    asset_key: str
    snapshot_id: str
    partition: str | None
    row_count: int
    duration_ms: int
    lineage_event_id: str
    materialized_at: datetime
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CheckResult:
    """Outcome record from a single ``@nucleus.check`` body.

    # Stability: Beta

    Per ``docs/specs/nucleus_ctx_sdk_spec.md`` §2.4 and ``docs/specs/nucleus_asset_model_spec.md``
    §10. Each ``@nucleus.check`` returns a :class:`CheckResult`; the
    coordination layer aggregates them into the run's quality verdict
    (v4.1 §6.3 +  asset model spec §10).

    Attributes:
        passed: Whether the assertion held. ``False`` typically routes
            to a quarantine path — the severity attached at decoration
            time decides whether the materialization is rejected,
            allowed-with-warning, or blocks downstream consumers
            (``docs/specs/nucleus_asset_model_spec.md`` §9.2 enforcement levels).
        metric: A single numeric measurement that summarizes the check
            (e.g. row-count of bad rows, sum-diff, freshness lag in
            seconds). Float by convention so divergence from integer
            counts (rates, ratios, deltas) is representable. Missing
            metrics use ``0.0`` per the spec's "always populate" rule.
        message: Optional human-readable summary. Empty by default;
            populated when the check author wants the user-facing text
            to be richer than just the metric value.
    """

    passed: bool
    metric: float = 0.0
    message: str = field(default="")


__all__ = [
    "AssetRef",
    "CheckResult",
    "MaterializationResult",
]
