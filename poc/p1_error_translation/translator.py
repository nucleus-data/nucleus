"""Minimal Dagster error translator — PoC #1 (steps 2-3 of README §3).

Scope (deliberately minimal):
    - 3 handlers + a fallback. Not 50 cases.
    - Just enough to prove the contract works end-to-end.
    - Will graduate to ``src/nucleus/coordination/error_translation.py``
      after the PoC acceptance criteria (README §2) pass.

Pins/docs:
    - dagster==1.9.5  (see ``docs/research/dagster.md``)
    - ``nucleus_architecture_v4.1.md`` §6.4 — Error Translation Discipline
    - ``docs/architecture/sequence_error_translation.md`` — the spec
"""

from __future__ import annotations

from typing import Callable

from nucleus.errors import (
    NucleusError,
    NucleusInternalError,
    NucleusSchemaError,
    NucleusSourceConnectionError,
)

# A handler takes the original exception and returns a typed NucleusError.
# Handlers MUST NOT raise; if translation fails, return NucleusInternalError.
Handler = Callable[[BaseException], NucleusError]


# Bounded depth so a malformed __cause__ chain can't loop forever.
_MAX_CAUSE_DEPTH = 8


def _unwrap_cause(exc: BaseException) -> BaseException:
    """Walk ``__cause__`` to find the innermost real exception.

    Dagster wraps user-code exceptions in ``DagsterExecutionStepExecutionError``;
    the real cause is usually one or two ``__cause__`` levels deeper.
    """
    current = exc
    for _ in range(_MAX_CAUSE_DEPTH):
        if current.__cause__ is None:
            return current
        current = current.__cause__
    return current


def _dagster_step_handler(exc: BaseException) -> NucleusError:
    """Translate a Dagster step-execution failure based on its inner cause."""
    inner = _unwrap_cause(exc)
    inner_type = type(inner).__name__
    inner_msg = str(inner) or "(no message)"

    if isinstance(inner, ConnectionError):
        return NucleusSourceConnectionError(
            user_message=f"Could not connect to source: {inner_msg}",
            fix_hint="Check host, port, and credentials in your source config.",
            cause=exc,
        )

    if isinstance(inner, (TypeError, ValueError)) and "schema" in inner_msg.lower():
        return NucleusSchemaError(
            user_message=f"Schema validation failed: {inner_msg}",
            fix_hint="Verify column types and nullability in your asset's return value.",
            cause=exc,
        )

    return NucleusInternalError(
        user_message=f"Asset execution failed ({inner_type}): {inner_msg}",
        fix_hint=(
            "If this is unexpected, please file a bug. "
            "Run with --debug to see the full traceback."
        ),
        cause=exc,
    )


# Lazy registry: avoids importing dagster at module load. Built on first call.
# NEEDS VERIFICATION on first PoC run: confirm
# ``dagster.DagsterExecutionStepExecutionError`` is the exact class name and
# import path in 1.9.5. Log any rename to docs/research/ai_hallucinations.md.
_HANDLERS: dict[type, Handler] | None = None


def _registry() -> dict[type, Handler]:
    global _HANDLERS
    if _HANDLERS is None:
        import dagster as dg

        _HANDLERS = {
            dg.DagsterExecutionStepExecutionError: _dagster_step_handler,
        }
    return _HANDLERS


def translate(exc: BaseException) -> NucleusError:
    """Translate any exception to a NucleusError.

    Order:
        1. Already a NucleusError? Return unchanged (idempotent).
        2. Walk the registry; first matching class (incl. subclasses) wins.
        3. Fallback: NucleusInternalError with the original chained as ``__cause__``.
    """
    if isinstance(exc, NucleusError):
        return exc

    for exc_type, handler in _registry().items():
        if isinstance(exc, exc_type):
            return handler(exc)

    return NucleusInternalError(
        user_message=f"Unexpected error ({type(exc).__name__}): {exc}",
        fix_hint="No translator registered for this exception type. Please file a bug.",
        cause=exc,
    )
