"""``@nucleus.asset`` and ``@nucleus.check`` decorators (L4).

Per ``docs/specs/nucleus_ctx_sdk_spec.md`` §2.1 + §2.4 and
``docs/specs/nucleus_asset_model_spec.md`` §3 + §10. Both decorators register the
wrapped callable in the in-process registry under its canonical key, so
the CLI (``nucleus run <key>``) and :func:`nucleus.materialize` can
resolve the function later via :func:`get_asset` / :func:`get_check`.

v0.1.1 scope (per ``docs/architecture/v01_skeleton_plan.md`` §3.1 r6 +
ADR-017 §3 schedule exposure):
    - ``@nucleus.asset(key, deps=(), partitions=None, compute=None,
      contract=None, schedule=None)`` registers a function as the asset's
      body. The optional ``schedule=`` kwarg accepts a 5-field cron string
      or a shorthand alias (``@daily``, ``@hourly``, ``@weekly``,
      ``@monthly``, ``@yearly``); validation uses croniter at decoration
      time per ADR-017 §2.
    - ``@nucleus.check(asset, *, severity="error")`` registers a check
      body bound to a single asset.
    - Decorator-time validation rejects malformed input via
      :class:`NucleusInvalidAssetDefinition` (``error_translation.py``
      pattern).
    - Execution wiring is **deferred** to the Asset Materialization
      Adapter (``coordination/asset_materialization.py``,
      ``v01_skeleton_plan.md`` §3.1 r3); calling :func:`nucleus.materialize`
      here raises a structured ``NucleusInternalError`` until the AMA
      lands. Same convention as the ``cli/main.py`` skeleton stubs.

Stability tier (per ADR-005 §2)
-------------------------------
**Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0**, the same ladder as
:mod:`nucleus.sdk.materialize` and :mod:`nucleus.sdk.results`.

Forbidden APIs (NEEDS VERIFICATION on every change)
---------------------------------------------------
This module must not import :mod:`dagster`. Asset registration is a
plain in-process dict + frozen-shape value type; the orchestrator hooks
in only when the AMA wires `materialize_to_memory` per v4.1 §6.2. The
``scripts/dagster_leak_check.py`` CI guard enforces this.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, ParamSpec, TypeVar

from nucleus.errors import NucleusInvalidAssetDefinition, NucleusScheduleParseError

# v0.1 accepts 2-level keys (``schema.name``) per cli_spec §10 NV #6.
# 3-level (``catalog.schema.name``) is deferred to v0.3+.
# Mirrors ``coordination/sql_resolver.py:_REF_NAME_RE`` to keep the
# accept set identical between ``ctx.sql {{ ref() }}`` and decorator key.
_KEY_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

# ---------------------------------------------------------------------------
# Schedule kwarg support (ADR-017 + docs/specs/nucleus_ctx_sdk_spec.md §5 amendment)
# ---------------------------------------------------------------------------
# Standard cron shorthand aliases per POSIX cron convention.
# Normalised to 5-field form before storage in _AssetDefinition.schedule.
# Croniter docs: https://pypi.org/project/croniter/ (croniter==3.0.4 — pinned via dagster<4 transitive constraint)
_CRON_ALIASES: Final[dict[str, str]] = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}


# Severity values accepted by ``@nucleus.check`` per asset model spec §9.2
# (enforcement levels). v0.1 ships ``error`` + ``warn``; ``block_consumers``
# (asset model spec §9.2 row 3) is wired at v0.3+ once downstream-block
# semantics are spec'd in detail.
_VALID_SEVERITIES: Final[frozenset[str]] = frozenset({"error", "warn"})

# Marker attributes attached to decorated callables. Kept as plain
# string keys (no SDK class) so the registry survives reload + can be
# inspected by external tools without importing nucleus.sdk.
_ASSET_MARKER: Final[str] = "__nucleus_asset_key__"
_CHECK_MARKER: Final[str] = "__nucleus_check_target__"

# ParamSpec + TypeVar pair is the canonical type for decorators that
# return the wrapped callable unchanged (PEP 612 + mypy decorator-factory
# pattern). Using the older ``F = TypeVar("F", bound=Callable[..., Any])``
# would make ``nucleus.asset(...)``'s return type's ``F`` unbound at the
# outer call site, which mypy --strict's ``disallow_untyped_decorators``
# treats as "untyped decorator → wrapped function untyped".
P = ParamSpec("P")
R = TypeVar("R")


# ---------------------------------------------------------------------------
# Registration records (private; visible to coordination/ for AMA wiring)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AssetDefinition:
    """Internal record for one ``@nucleus.asset``-decorated function.

    # Stability: Internal

    Not part of the public surface; the Asset Materialization Adapter
    (``coordination/asset_materialization.py``) reads these via
    :func:`get_asset` to materialize an asset by key.

    Attributes:
        schedule: Normalized 5-field cron string, or ``None`` when no
            schedule was declared. Aliases (``@daily`` etc.) are expanded
            to their canonical form by ``_validate_schedule`` at decoration
            time per ADR-017 §3. Dagster wiring happens in
            ``coordination/schedules.py``; this field is storage only.
    """

    key: str
    fn: Callable[..., Any]
    deps: tuple[str, ...]
    partitions: Any | None
    compute: str | None
    contract: Any | None
    schedule: str | None = None


@dataclass(frozen=True)
class _CheckDefinition:
    """Internal record for one ``@nucleus.check``-decorated function.

    # Stability: Internal

    Aggregated by the AMA after materialization per asset model spec §10.
    """

    target_asset_key: str
    fn: Callable[..., Any]
    severity: Literal["error", "warn"]


_ASSETS: dict[str, _AssetDefinition] = {}
_CHECKS: dict[str, list[_CheckDefinition]] = {}


def _validate_key(key: object, *, role: str) -> str:
    """Validate ``key`` shape; raise structured error on miss.

    Centralised so :func:`asset` and :func:`check` produce identical
    diagnostics for the same class of mistake.
    """
    if not isinstance(key, str) or not key:
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"@nucleus.{role}(...) requires a non-empty string key as the "
                f"first argument; got {type(key).__name__!r}."
            ),
            fix_hint=(
                f"Pass the asset key as the first argument, e.g. "
                f"@nucleus.{role}('staging.orders'). "
                "v0.1 keys are 2-level (schema.name); 3-level lights up at v0.3+."
            ),
        )
    if not _KEY_RE.match(key):
        raise NucleusInvalidAssetDefinition(
            user_message=f"Asset key {key!r} is not a valid v0.1 2-level name.",
            fix_hint=(
                "Keys must match '<schema>.<name>' where each part starts with "
                "a lowercase letter and contains only lowercase letters, digits, "
                "or underscores. Example: 'marts.orders_clean'."
            ),
        )
    return key


def _validate_deps(deps: object, *, key: str) -> tuple[str, ...]:
    """Coerce ``deps`` to a frozen tuple of validated 2-level keys."""
    if deps is None:
        return ()
    if isinstance(deps, str) or not isinstance(deps, Iterable):
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"@nucleus.asset({key!r}, deps=...) must be an iterable of asset "
                f"keys; got {type(deps).__name__!r}."
            ),
            fix_hint=(
                "Pass a list or tuple of strings, e.g. deps=['raw.orders', 'dim.customers']."
            ),
        )
    out: list[str] = []
    for index, dep in enumerate(deps):
        if not isinstance(dep, str) or not dep:
            raise NucleusInvalidAssetDefinition(
                user_message=(
                    f"@nucleus.asset({key!r}, deps=...) entry #{index} must be a "
                    f"non-empty string; got {type(dep).__name__!r}."
                ),
                fix_hint="Each dep is a 2-level asset key string.",
            )
        if dep == key:
            raise NucleusInvalidAssetDefinition(
                user_message=(
                    f"Asset {key!r} declares itself in deps. Self-edges are "
                    "forbidden per docs/specs/nucleus_asset_model_spec.md §6.3."
                ),
                fix_hint="Remove the self-reference from deps=.",
            )
        if not _KEY_RE.match(dep):
            raise NucleusInvalidAssetDefinition(
                user_message=(
                    f"@nucleus.asset({key!r}, deps=...) entry #{index} {dep!r} is "
                    "not a valid v0.1 2-level key."
                ),
                fix_hint=(
                    "Each dep must match '<schema>.<name>' (lowercase, digits, "
                    "underscores). Example: 'raw.orders'."
                ),
            )
        out.append(dep)
    return tuple(out)


def _validate_compute(compute: object, *, key: str) -> str | None:
    """``compute=`` is the v4.1 §6.7 yield-to-giants dispatch hint.

    v0.1 only accepts ``None`` (default) and ``"local"``; ``"databricks"`` /
    ``"snowflake"`` light up at v0.3+ when Mode 2 hybrid compute lands.
    """
    if compute is None:
        return None
    if not isinstance(compute, str) or compute not in {"local"}:
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"@nucleus.asset({key!r}, compute={compute!r}) is not supported "
                "in v0.1. Only compute='local' (or unset) is accepted."
            ),
            fix_hint=(
                "Drop the compute= kwarg or set compute='local'. Hybrid dispatch "
                "(databricks / snowflake) lands at v0.3+ per v4.1 §6.7."
            ),
        )
    return compute


def _validate_schedule(schedule: object, *, key: str) -> str | None:
    """Validate and normalise the ``schedule=`` kwarg per ADR-017 §3.

    Accepts a 5-field cron string or a shorthand alias from ``_CRON_ALIASES``.
    Returns the normalised 5-field string (aliases are expanded) or ``None``
    when ``schedule`` is ``None``.

    Raises:
        NucleusScheduleParseError: The expression is not a valid cron string.

    Docs: https://pypi.org/project/croniter/ (croniter==3.0.4 — is_valid API)
    """
    if schedule is None:
        return None
    if not isinstance(schedule, str) or not schedule:
        raise NucleusScheduleParseError(
            user_message=(
                f"@nucleus.asset({key!r}, schedule=...) must be a non-empty string "
                f"or None; got {type(schedule).__name__!r}."
            ),
            fix_hint=(
                "Pass a cron string such as schedule='0 2 * * *' or a shorthand like "
                "schedule='@daily'. See https://nucleus.dev/errors/schedule-parse for examples."
            ),
            asset=key,
        )
    # Expand shorthand alias first.
    normalized = _CRON_ALIASES.get(schedule.strip(), schedule.strip())

    # v0.1 accepts only standard 5-field cron (minute hour day month weekday).
    # croniter 3.x supports 6-field (with seconds) and 7-field (with year);
    # we reject them here so users get a clear parse error rather than silently
    # accepting an unsupported extended format.
    field_count = len(normalized.split())
    if field_count != 5:
        raise NucleusScheduleParseError(
            user_message=(
                f"@nucleus.asset({key!r}, schedule={schedule!r}) must be a "
                f"5-field cron string (minute hour day month weekday); "
                f"got {field_count} field(s)."
            ),
            fix_hint=(
                "Use the standard 5-field format: 'minute hour day month weekday'. "
                "Example: '0 2 * * *' (daily at 2 AM). "
                "Or use a shorthand: @daily, @hourly, @weekly, @monthly, @yearly. "
                "6-field cron (with seconds) and year fields are not supported in v0.1. "
                "See https://nucleus.dev/errors/schedule-parse for the full reference."
            ),
            asset=key,
        )

    # Lazy import: croniter is a runtime dep pinned in pyproject.toml.
    # Docs: https://pypi.org/project/croniter/ (croniter==3.0.4)
    # croniter.is_valid() validates a 5-field cron expression.
    try:
        from croniter import croniter
    except ImportError as exc:
        raise NucleusScheduleParseError(
            user_message=(
                "The 'croniter' package is required to validate schedule expressions "
                "but it is not installed."
            ),
            fix_hint="Run `pip install croniter==3.0.4` or add it to your dependencies.",
            asset=key,
            cause=exc,
        ) from exc

    if not croniter.is_valid(normalized):
        raise NucleusScheduleParseError(
            user_message=(
                f"@nucleus.asset({key!r}, schedule={schedule!r}) is not a valid cron expression."
            ),
            fix_hint=(
                "Use a 5-field cron string (minute hour day month weekday), e.g. "
                "'0 2 * * *' for daily at 2 AM, or a shorthand: @daily, @hourly, "
                "@weekly, @monthly, @yearly. "
                "See https://nucleus.dev/errors/schedule-parse for the full reference."
            ),
            asset=key,
        )
    return normalized


def _ensure_function(fn: object, *, role: str, key: str) -> Callable[..., Any]:
    """Reject non-function targets (classes, lambdas, instances).

    Per ``docs/specs/nucleus_asset_model_spec.md`` §14 forbidden patterns row 6.
    Lambdas are rejected because their ``__name__`` is opaque and the
    code-version hash (asset model spec §8.1) becomes meaningless.
    """
    if not callable(fn):
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"@nucleus.{role}({key!r}) must decorate a callable; got {type(fn).__name__!r}."
            ),
            fix_hint="Apply the decorator directly above a `def` block.",
        )
    name = getattr(fn, "__name__", "")
    if name == "<lambda>":
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"@nucleus.{role}({key!r}) cannot decorate a lambda — only "
                "named def functions are supported."
            ),
            fix_hint=(
                "Replace the lambda with a `def` so the asset has a stable name "
                "and code-version hash. See docs/specs/nucleus_asset_model_spec.md §8.1."
            ),
        )
    return fn


# ---------------------------------------------------------------------------
# Public decorators
# ---------------------------------------------------------------------------


def asset(
    key: str,
    *,
    deps: Sequence[str] | None = None,
    partitions: Any | None = None,
    compute: str | None = None,
    contract: Any | None = None,
    schedule: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Register a function as a Nucleus asset's materialization body.

    # Stability: Beta

    Per ``docs/specs/nucleus_ctx_sdk_spec.md`` §2.1 +
    ``docs/specs/nucleus_asset_model_spec.md`` §3.1. The decorated function becomes
    the asset's compute step — the body the Asset Materialization Adapter
    (v4.1 §6.2) calls inside ``nucleus.materialize(<key>)``.

    Args:
        key: Canonical v0.1 2-level key (``"schema.name"``). Must match
            ``^[a-z][a-z0-9_]*\\.[a-z][a-z0-9_]*$``. The 3-level form
            (``catalog.schema.name``) is deferred to v0.3+ per
            ``docs/specs/nucleus_cli_spec.md`` §10 NV #6.
        deps: Explicit upstream asset keys. Optional — Nucleus auto-derives
            deps from ``ctx.read(...)`` calls inside the body
            (asset model spec §6.1). Use this kwarg only when the read
            pattern is dynamic (asset model spec §6.2).
        partitions: Partition definition (e.g. ``nucleus.daily(...)``).
            v0.1 accepts the value but partitioned execution is deferred
            to v0.3+ — calling ``materialize`` with ``partition=`` on a
            non-partitioned asset raises ``NucleusInternalError`` per
            ADR-013 NV #6.
        compute: Yield-to-giants dispatch hint per v4.1 §6.7. v0.1 only
            accepts ``None`` or ``"local"``; remote dispatch (Databricks,
            Snowflake) lights up at v0.3+.
        contract: Optional contract reference. v0.1 accepts the value
            but contract enforcement is deferred to ``coordination.contracts``
            per ``v01_skeleton_plan.md`` §3.1 r5.
        schedule: Cron expression declaring when this asset should run
            automatically. Accepts a 5-field cron string (``"0 2 * * *"``)
            or a shorthand alias (``"@daily"``, ``"@hourly"``, ``"@weekly"``,
            ``"@monthly"``, ``"@yearly"``). Aliases are normalised to their
            5-field equivalents before storage. Validated at decoration time
            via croniter (Docs: https://pypi.org/project/croniter/).
            ``None`` (default) means the asset has no declared schedule.

            Active scheduling (automatic execution) is deferred to v0.2 —
            declaring ``schedule=`` stores the expression and exposes it
            via ``nucleus schedule list`` / ``nucleus schedule preview``.
            Per ADR-017 §6 and the Anti-Over-Engineering directive.

    Returns:
        The decorator itself returns the original function unchanged
        (with marker attributes), so users can call the decorated body
        directly in unit tests without spinning the AMA.

    Raises:
        NucleusInvalidAssetDefinition: Any of the validation checks
            above failed at decoration time. Decoration-time errors are
            surfaced eagerly so users see them on import, not at run.

    Examples:
        Minimal asset::

            @nucleus.asset("staging.orders")
            def staging_orders(ctx):
                return ctx.read("raw.orders").filter(pl.col("amount") > 0)

        With explicit deps and contract::

            @nucleus.asset(
                "marts.orders_clean",
                deps=["staging.orders", "dim.customers"],
                contract=orders_contract,
            )
            def marts_orders_clean(ctx): ...
    """
    validated_key = _validate_key(key, role="asset")
    validated_deps = _validate_deps(deps, key=validated_key)
    validated_compute = _validate_compute(compute, key=validated_key)
    validated_schedule = _validate_schedule(schedule, key=validated_key)

    def _decorate(fn: Callable[P, R]) -> Callable[P, R]:
        validated_fn = _ensure_function(fn, role="asset", key=validated_key)
        if validated_key in _ASSETS and _ASSETS[validated_key].fn is not validated_fn:
            raise NucleusInvalidAssetDefinition(
                user_message=(
                    f"Asset {validated_key!r} is already defined by another function. "
                    "Two assets cannot share a key per docs/specs/nucleus_asset_model_spec.md §14."
                ),
                fix_hint=(
                    "Pick a unique key for the new function or remove the existing "
                    "definition. Use `nucleus list` (v0.1+) to inspect the registry."
                ),
            )
        record = _AssetDefinition(
            key=validated_key,
            fn=validated_fn,
            deps=validated_deps,
            partitions=partitions,
            compute=validated_compute,
            contract=contract,
            schedule=validated_schedule,
        )
        _ASSETS[validated_key] = record
        with contextlib.suppress(AttributeError, TypeError):
            setattr(validated_fn, _ASSET_MARKER, validated_key)
        return fn

    return _decorate


def check(
    asset: str,
    *,
    severity: str = "error",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Register a function as a quality check bound to an asset.

    # Stability: Beta

    Per ``docs/specs/nucleus_ctx_sdk_spec.md`` §2.4 +
    ``docs/specs/nucleus_asset_model_spec.md`` §10. The decorated body runs after
    the target asset materializes; the function MUST return a
    :class:`nucleus.CheckResult` recording pass/fail and a metric.

    Args:
        asset: Asset key the check is bound to (2-level v0.1 form).
        severity: Either ``"error"`` (default; failed check rejects the
            materialization) or ``"warn"`` (failed check emits a warning
            but allows the materialization to commit). The third
            enforcement level ``"block_consumers"`` (asset model spec
            §9.2) is deferred to v0.3+.

    Returns:
        The decorator returns the original function with marker
        attributes so unit tests can call it directly.

    Raises:
        NucleusInvalidAssetDefinition: Bad key, unknown severity, or
            non-callable target.

    Examples:
        Basic check::

            @nucleus.check("sales.orders")
            def check_no_negative_amounts(ctx):
                df = ctx.read("sales.orders")
                bad = df.filter(pl.col("amount") < 0)
                return nucleus.CheckResult(
                    passed=len(bad) == 0,
                    metric=len(bad),
                    message=f"{len(bad)} negative amounts found",
                )

        Soft check (warn-only)::

            @nucleus.check("sales.orders", severity="warn")
            def check_freshness(ctx): ...
    """
    validated_key = _validate_key(asset, role="check")
    if not isinstance(severity, str) or severity not in _VALID_SEVERITIES:
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"@nucleus.check({asset!r}, severity={severity!r}) is not a "
                "supported v0.1 severity."
            ),
            fix_hint=(
                "Pass severity='error' (default) or severity='warn'. "
                "severity='block_consumers' lights up at v0.3+ per "
                "docs/specs/nucleus_asset_model_spec.md §9.2."
            ),
        )
    severity_lit: Literal["error", "warn"] = "error" if severity == "error" else "warn"

    def _decorate(fn: Callable[P, R]) -> Callable[P, R]:
        validated_fn = _ensure_function(fn, role="check", key=validated_key)
        record = _CheckDefinition(
            target_asset_key=validated_key,
            fn=validated_fn,
            severity=severity_lit,
        )
        _CHECKS.setdefault(validated_key, []).append(record)
        with contextlib.suppress(AttributeError, TypeError):
            setattr(validated_fn, _CHECK_MARKER, validated_key)
        return fn

    return _decorate


# ---------------------------------------------------------------------------
# Internal registry accessors (consumed by coordination/asset_materialization)
# ---------------------------------------------------------------------------


def get_asset(key: str) -> _AssetDefinition | None:
    """Return the registered asset definition for ``key`` or ``None``.

    # Stability: Internal

    Used by the Asset Materialization Adapter to look up the body for
    ``nucleus.materialize(key)``. Public accessor on a private record;
    do not rely on the return type from user code.
    """
    return _ASSETS.get(key)


def get_checks(asset_key: str) -> tuple[_CheckDefinition, ...]:
    """Return all checks bound to ``asset_key`` (empty if none).

    # Stability: Internal

    Order is registration order; the AMA runs them after the asset
    commits and aggregates results per asset model spec §10.
    """
    return tuple(_CHECKS.get(asset_key, ()))


def _registered_keys() -> tuple[str, ...]:
    """Snapshot of registered asset keys (sorted for stable output).

    # Stability: Internal

    Helper for tests + the eventual ``nucleus list`` CLI command.
    """
    return tuple(sorted(_ASSETS))


def get_scheduled_assets() -> tuple[_AssetDefinition, ...]:
    """Return all registered assets that have a ``schedule`` declared (sorted).

    # Stability: Internal

    Consumed by ``coordination/schedules.py`` to build ``ScheduleEntry``
    records for ``nucleus schedule list`` + ``nucleus schedule preview``.
    Returns the definitions in ascending key order for stable CLI output.
    """
    return tuple(defn for key in sorted(_ASSETS) if (defn := _ASSETS[key]).schedule is not None)


def _reset_registry_for_tests() -> None:
    """Clear both registries — TEST-ONLY helper.

    # Stability: Internal

    Production code never calls this. Tests use it to keep cross-test
    isolation since both registries are module-level dicts.
    """
    _ASSETS.clear()
    _CHECKS.clear()


__all__ = [
    "asset",
    "check",
    "get_asset",
    "get_checks",
    "get_scheduled_assets",
]
