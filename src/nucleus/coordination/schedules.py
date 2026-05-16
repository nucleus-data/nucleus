"""Schedule façade — L2 Coordination layer (ADR-017).

Wraps Dagster's ``ScheduleDefinition`` for v0.2+ daemon-driven execution.
In v0.1.1, exposes read-only schedule metadata:

    - :class:`ScheduleEntry` — immutable schedule record for CLI display.
    - :func:`list_schedules` — reads the in-process registry and returns one
      ``ScheduleEntry`` per ``@nucleus.asset(schedule=...)``-decorated asset.
    - :func:`preview_schedule` — returns the next N run times for an asset
      (uses ``croniter`` directly; no Dagster daemon needed).
    - :func:`to_dagster_schedule` — wraps a ``ScheduleDefinition`` for the
      v0.2 active-scheduling path (PROPOSED; stub in v0.1.1).

Per ``docs/specs/nucleus_architecture_v4.1.md`` §6.3 (Coordination layer) and
ADR-017 §1 (wrap Dagster, don't build a custom scheduler).

# Stability: Internal

Zero Dagster types cross outbound through :class:`ScheduleEntry` or
:func:`list_schedules`/:func:`preview_schedule` — enforced by
``scripts/dagster_leak_check.py`` in CI.

Docs (Dagster ScheduleDefinition):
    https://docs.dagster.io/api/python-api/schedules-sensors#dagster.ScheduleDefinition
Docs (croniter):
    https://pypi.org/project/croniter/ (croniter==3.0.4)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from nucleus.errors import NucleusScheduleNotFoundError
from nucleus.sdk.decorators import _AssetDefinition, get_asset, get_scheduled_assets


@dataclass(frozen=True)
class ScheduleEntry:
    """Immutable schedule record for one ``@nucleus.asset(schedule=...)`` asset.

    # Stability: Internal

    Contains only Python scalars — no Dagster types leak outward per v4.1 §6.4.
    Used by ``nucleus schedule list`` and ``nucleus schedule preview``.
    """

    asset_key: str
    cron_expression: str
    description: str = ""


def list_schedules() -> tuple[ScheduleEntry, ...]:
    """Return one :class:`ScheduleEntry` per asset that has a declared schedule.

    Reads the in-process ``@nucleus.asset`` registry (in-memory; populated
    at import time via decorator execution). Returns an empty tuple when no
    assets carry a ``schedule=`` kwarg.

    Per ADR-017 §3 the stored ``cron_expression`` is always the 5-field
    normalised form (shorthand aliases are expanded at decoration time by
    ``sdk.decorators._validate_schedule``).

    # Stability: Internal
    """
    return tuple(
        ScheduleEntry(
            asset_key=defn.key,
            cron_expression=defn.schedule,  # type: ignore[arg-type]  # non-None guaranteed by get_scheduled_assets
        )
        for defn in get_scheduled_assets()
    )


def preview_schedule(asset_key: str, *, n: int = 3) -> tuple[str, ...]:
    """Return the next ``n`` run times for the scheduled asset ``asset_key``.

    Uses ``croniter.get_next()`` from the current UTC clock so the preview
    is deterministic relative to when it is called (no Dagster daemon needed).

    Args:
        asset_key: A 2-level Nucleus key (``"schema.name"``).  Must be
            registered with ``@nucleus.asset(schedule=...)``; both
            "asset not in registry" and "asset has no schedule" raise
            :class:`NucleusScheduleNotFoundError` (NE5006).
        n: Number of upcoming run times to return (default 3, max 20).
            Clamped to 1-20.

    Returns:
        Tuple of ``n`` ISO-8601 UTC datetime strings, e.g.::

            ("2026-05-15T02:00:00+00:00", "2026-05-16T02:00:00+00:00", ...)

    Raises:
        NucleusScheduleNotFoundError: Asset not in registry, or registered
            without a ``schedule=`` kwarg.

    Docs (croniter): https://pypi.org/project/croniter/ (croniter==3.0.4)

    # Stability: Internal
    """
    defn: _AssetDefinition | None = get_asset(asset_key)
    if defn is None or defn.schedule is None:
        if defn is None:
            detail = f"Asset {asset_key!r} is not registered."
            hint = (
                "Register the asset with @nucleus.asset(<key>) and import the module "
                "that defines it before calling preview_schedule."
            )
        else:
            detail = f"Asset {asset_key!r} does not have a declared schedule."
            hint = (
                f"Add schedule='<cron>' to the @nucleus.asset('{asset_key}') decorator. "
                "Examples: schedule='@daily', schedule='0 2 * * *'."
            )
        raise NucleusScheduleNotFoundError(
            user_message=detail,
            fix_hint=hint,
            asset=asset_key,
        )

    # Croniter docs: https://pypi.org/project/croniter/ (croniter==3.0.4)
    # croniter(expr, start_time).get_next(datetime) → next datetime after start_time.
    try:
        from croniter import croniter
    except ImportError as exc:
        # Re-raise as a typed error so the CLI can render it cleanly.
        from nucleus.errors import NucleusInternalError

        raise NucleusInternalError(
            user_message=(
                "The 'croniter' package is required for schedule preview but is not installed."
            ),
            fix_hint="Run `pip install croniter==3.0.4`.",
            asset=asset_key,
            cause=exc,
        ) from exc

    count = max(1, min(n, 20))
    base = datetime.now(UTC)
    itr = croniter(defn.schedule, base)
    return tuple(itr.get_next(datetime).isoformat() for _ in range(count))


def to_dagster_schedule(defn: _AssetDefinition) -> Any:
    """Wrap ``defn`` in a Dagster ``ScheduleDefinition`` (v0.2 active-scheduling path).

    This function is the thin Dagster façade per ADR-017 §1. In v0.1.1 it is
    a fully-implemented helper but is NOT called from any CLI path — the
    active-scheduling daemon wiring is deferred to v0.2.

    Returns a ``dagster.ScheduleDefinition`` targeting the asset's key.
    Dagster types do NOT cross the outbound coordination boundary (never
    stored in ``ScheduleEntry`` or passed to CLI callers).

    Per ``docs/specs/nucleus_architecture_v4.1.md`` §6.3 (Coordination — Dagster wrap)
    and ADR-017 §1 (wrap, don't build).

    Docs (ScheduleDefinition):
        https://docs.dagster.io/api/python-api/schedules-sensors#dagster.ScheduleDefinition
        (dagster==1.9.5)

    # Stability: Internal
    """
    if defn.schedule is None:
        from nucleus.errors import NucleusInvalidAssetDefinition

        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"Cannot create a Dagster schedule for asset {defn.key!r}: "
                "no schedule= expression was declared."
            ),
            fix_hint=(
                f"Add schedule='<cron>' to @nucleus.asset('{defn.key}'). "
                "Example: schedule='0 2 * * *'."
            ),
            asset=defn.key,
        )

    # Docs: https://docs.dagster.io/api/python-api/schedules-sensors#dagster.ScheduleDefinition
    # ScheduleDefinition parameters confirmed from dagster==1.9.5 docs:
    #   name: str — unique schedule name (slugified asset key)
    #   cron_schedule: str — standard 5-field cron string
    #   job_name: str — the Dagster job this schedule targets
    #   description: str — human-readable description
    # Dagster is a HIDDEN implementation detail — ScheduleDefinition is
    # NOT exposed outside coordination/. Zero Dagster types reach user output.
    import dagster  # Docs: https://docs.dagster.io/api/

    schedule_name = defn.key.replace(".", "__") + "_schedule"
    job_name = defn.key.replace(".", "__") + "_job"

    return dagster.ScheduleDefinition(
        name=schedule_name,
        cron_schedule=defn.schedule,
        job_name=job_name,
        description=f"Nucleus auto-schedule for asset '{defn.key}'.",
    )


__all__ = [
    "ScheduleEntry",
    "list_schedules",
    "preview_schedule",
    "to_dagster_schedule",
]
