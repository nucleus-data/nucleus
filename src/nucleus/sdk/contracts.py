"""Schema-contracts runtime — execute ``@nucleus.check`` bodies (L4 SDK).

Per ``docs/specs/nucleus_architecture_v4.1.md`` §15 (schema contracts) +
``docs/specs/nucleus_asset_model_spec.md`` §10 (check semantics). Closes the v0.1
loop on quality checks: the ``@nucleus.check`` decorator already
registers check bodies (``sdk/decorators.py``), the ``CheckResult``
value type already exists (``sdk/results.py``), and ``MaterializationResult``
already carries a ``checks`` tuple — this module is the runtime that
fills that tuple at materialization time.

What this module does (v0.1 scope)
----------------------------------
Three module-level functions wrap the in-process check registry so the
Asset Materialization Adapter
(:mod:`nucleus.coordination.asset_materialization`) can attach the
outcome of every registered check to the returned
:class:`MaterializationResult`:

    - :func:`run_checks_for_asset`   executes every registered check for
                                     an asset_key and returns a tuple
                                     of :class:`CheckResult`
    - :func:`list_registered_checks` returns the qualified names of
                                     registered checks (for the eventual
                                     ``nucleus list`` CLI surface)
    - :func:`_execute_one_check`     internal helper that runs a single
                                     check and normalises the result

What this module is NOT (anti-over-engineering, founder directive 2026-05-13)
-----------------------------------------------------------------------------
* No ``CheckRunner`` class — three free functions, second caller will
  trigger refactor per the founder directive
* No async / threading / parallel execution — sequential per
  registration order. v0.5 may parallelize if telemetry demands.
* No ``CheckSeverity`` enum or ``CheckPolicy`` knobs — the decorator's
  ``severity={"error","warn"}`` is the v0.1 surface. ``block_consumers``
  + downstream-blocking semantics land at v0.3+ per
  ``docs/specs/nucleus_asset_model_spec.md`` §9.2.
* No ``fail_fast=True`` option — v0.1 always runs all registered checks
  and returns the full picture so users see every failure at once.
  Failing checks DO NOT raise; they're captured as
  ``CheckResult(passed=False, ...)``. v0.5 may add a fail-fast knob if
  user telemetry surfaces the need.
* No retry logic — checks are deterministic per ``asset_model_spec`` §10.
  Retries are a runner concern, not a contracts concern.

Error translation discipline (per AGENTS.md §11.7 + v4.1 §6.4)
--------------------------------------------------------------
Every raise inside a check body is captured. NucleusError subclasses
are preserved verbatim (no double-translation). Any other ``Exception``
becomes a :class:`NucleusCheckExecutionError` (NE3007, Coordination layer
per ADR-006 §1 carve-out). The translated error's code and message are encoded in
the returned ``CheckResult.message`` so the user-facing surface stays
on the public ``CheckResult`` shape — no leak of Dagster / DuckDB /
Polars / pyiceberg / sqlalchemy class names. ``BaseException``
subclasses (``KeyboardInterrupt``, ``SystemExit``) propagate per
the Python convention — checks are user code; user-initiated cancel
must reach the caller.

Stability tier (per ADR-005 §2)
-------------------------------
Public functions are **Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0**,
the same ladder as ``ctx.read``/``ctx.write``/``ctx.sql``. The internal
``_execute_one_check`` helper is **Internal** and may change shape
without an ADR.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nucleus.errors import NucleusCheckExecutionError, NucleusError
from nucleus.sdk.decorators import get_checks
from nucleus.sdk.results import CheckResult


def run_checks_for_asset(asset_key: str) -> tuple[CheckResult, ...]:
    """Execute every check registered for ``asset_key`` and return the outcomes.

    # Stability: Beta

    Per ``docs/specs/nucleus_architecture_v4.1.md`` §15 + ``docs/specs/nucleus_asset_model_spec.md``
    §10. Each check is invoked with no arguments; check functions are
    expected to pull data via the SDK's own context (``ctx.sql``,
    ``ctx.read``, etc.) when materialization is complete. v0.1 does not
    pass arguments; v0.5 will pass a context handle once the per-asset
    ``Ctx`` runtime is wired (``docs/architecture/v01_skeleton_plan.md``
    §3.1 r4).

    Order is registration order (Python 3.7+ dict insertion order is
    preserved); the underlying registry stores checks as an append-only
    list per asset_key.

    A failing check does NOT abort the run — the corresponding
    :class:`CheckResult` carries ``passed=False`` and remaining checks
    still execute. A check body raising an unhandled exception is
    translated to :class:`NucleusCheckExecutionError` (NE3007) and
    wrapped as a failing ``CheckResult`` so the user sees the full
    picture of every check outcome in one materialization.

    Args:
        asset_key: Canonical 2-level Nucleus key (``"schema.name"``).
            No validation is performed here — the AMA's caller
            (:func:`nucleus.coordination.asset_materialization.materialize_asset`)
            already filtered the key through the registry lookup.

    Returns:
        A tuple of :class:`CheckResult` records in registration order.
        Empty tuple when no checks are registered for ``asset_key``.
    """
    records = get_checks(asset_key)
    if not records:
        return ()
    out: list[CheckResult] = []
    for record in records:
        name: str = (
            getattr(record.fn, "__qualname__", None)
            or getattr(record.fn, "__name__", None)
            or repr(record.fn)
        )
        out.append(_execute_one_check(name, record.fn))
    return tuple(out)


def list_registered_checks(asset_key: str) -> tuple[str, ...]:
    """Return the qualified names of checks registered for ``asset_key``.

    # Stability: Beta

    Names are :attr:`function.__qualname__` snapshots taken at registration
    time. Useful for introspection (the eventual ``nucleus list``
    command per ``docs/specs/nucleus_cli_spec.md``) and for debugging which check
    fired which result.

    Args:
        asset_key: Canonical 2-level Nucleus key.

    Returns:
        Tuple of qualified-name strings in registration order. Empty
        tuple when no checks are registered.
    """
    records = get_checks(asset_key)
    if not records:
        return ()
    names: list[str] = [
        (
            getattr(record.fn, "__qualname__", None)
            or getattr(record.fn, "__name__", None)
            or repr(record.fn)
        )
        for record in records
    ]
    return tuple(names)


def _execute_one_check(name: str, func: Callable[[], Any]) -> CheckResult:
    """Run one check function and normalise the return to :class:`CheckResult`.

    # Stability: Internal

    Per v4.1 §6.4 + AGENTS.md §11.7, every raise inside the check body
    is captured here so the contracts runtime never propagates a typed
    error up to the AMA — failing checks are data, not exceptions, per
    the v0.1 contract. ``BaseException`` subclasses (``KeyboardInterrupt``,
    ``SystemExit``) intentionally bypass the catch so user-initiated
    cancellation still reaches the caller per the Python convention.

    Accepts the following return shapes from ``func``:

    - :class:`CheckResult` — passed through unchanged.
    - ``bool``             — wrapped as ``CheckResult(passed=<bool>)``.
    - Anything else (incl. ``None``, ``dict``, raw numbers) — surfaced
      as a failing ``CheckResult`` with a clear "unsupported return"
      message; the contract is documented on :func:`run_checks_for_asset`.

    Translation rules:

    - :class:`NucleusError` subclasses raise → captured verbatim (no
      double-translate) so the original ``error_code`` is preserved.
    - Any other ``Exception`` raise → wrapped as
      :class:`NucleusCheckExecutionError` (NE3007); the original
      exception is preserved on the returned message string for
      debugging. ``__cause__`` chaining is NOT used here because the
      contracts runtime does not raise — the typed error is constructed
      only to source its ``error_code`` constant.

    Args:
        name: A human-readable identifier for the check (typically
            ``func.__qualname__``); used in the failure ``message`` so
            the user knows which check produced which outcome.
        func: The zero-argument callable registered via
            ``@nucleus.check``. Arity is NOT enforced here; an arity-1
            body produces a ``TypeError`` which is captured as a failing
            ``CheckResult`` per the rules above (v0.1 strict
            zero-args contract; v0.5 will pass a context handle).

    Returns:
        A :class:`CheckResult` describing the check outcome. Never
        raises (except for ``BaseException`` propagation noted above).
    """
    try:
        result = func()
    except NucleusError as exc:
        # error_code is declared as ClassVar[str] on every NucleusError subclass
        # (see nucleus/errors.py); base NucleusError omits it so static analysis
        # can't see the attribute on the bound instance type.
        return CheckResult(
            passed=False,
            metric=0.0,
            message=f"[{exc.error_code}] {name}: {exc.user_message}",  # type: ignore[attr-defined]
        )
    except Exception as exc:
        return CheckResult(
            passed=False,
            metric=0.0,
            message=(
                f"[{NucleusCheckExecutionError.error_code}] {name}: {type(exc).__name__}: {exc}"
            ),
        )

    if isinstance(result, CheckResult):
        return result
    if isinstance(result, bool):
        return CheckResult(passed=result)

    return CheckResult(
        passed=False,
        metric=0.0,
        message=(
            f"[{NucleusCheckExecutionError.error_code}] {name}: "
            f"unsupported return type {type(result).__name__!r} "
            "(expected nucleus.CheckResult or bool)"
        ),
    )


__all__ = [
    "list_registered_checks",
    "run_checks_for_asset",
]
