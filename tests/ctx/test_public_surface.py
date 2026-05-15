"""Pin the public ``nucleus.ctx`` surface contract.

Per Phase D verifier HIGH #2 (2026-05-14): the 39 Phase D tests all import
from submodules (``nucleus.ctx._dispatch``, ``nucleus.ctx.sql``,
``nucleus.ctx.read``), so they do NOT exercise the documented user contract
``import nucleus.ctx as ctx; ctx.copy_from(...)``. This file closes that gap
with cheap regression assertions that would have caught the Phase D builder
``__init__.py`` hallucination (where the file appeared edited in the
completion report but was actually unchanged on disk).

The Python submodule-vs-attribute resolution for ``nucleus.ctx.copy_from``
is particularly subtle: there is BOTH a ``copy_from.py`` submodule AND a
``copy_from`` function re-exported in ``__init__.py``. After the
``__init__.py`` imports, ``nucleus.ctx.copy_from`` resolves to the FUNCTION
(the unified dispatcher) — not the module. These tests pin that behavior.

Per AGENTS.md §11.7 + nucleus_architecture_v4.1.md §13.1 (the ctx SDK is
the single stable surface from v1.0 onward; anything else is internal).

# Stability: Internal (test-only)
"""

from __future__ import annotations

import pytest


def test_ctx_module_imports_cleanly() -> None:
    """``import nucleus.ctx`` must succeed without side effects."""
    from nucleus import ctx

    assert ctx is not None
    assert hasattr(ctx, "__all__")


def test_public_all_contains_required_v01_symbols() -> None:
    """``__all__`` must expose the v0.1 contract (copy_from, sql, read, NucleusError)."""
    from nucleus import ctx

    expected = {"NucleusError", "copy_from", "sql", "read"}
    actual = set(ctx.__all__)
    missing = expected - actual
    assert not missing, f"Public ctx surface missing v0.1 symbols: {missing}"


def test_copy_from_resolves_to_function_not_submodule() -> None:
    """``nucleus.ctx.copy_from`` MUST be the unified dispatcher function.

    Regression guard: this attribute is also a submodule path
    (``src/nucleus/ctx/copy_from.py``). After ``__init__.py`` re-imports
    ``from nucleus.ctx._dispatch import copy_from``, the package-level
    attribute MUST resolve to the function (per spec), not the submodule.
    """
    from nucleus import ctx

    assert callable(ctx.copy_from), (
        f"ctx.copy_from must be callable; got {type(ctx.copy_from).__name__}. "
        "This usually means __init__.py is missing the re-export."
    )
    # The function lives in nucleus.ctx._dispatch — confirm we got that one
    # (not a copy_from.py submodule export).
    assert ctx.copy_from.__module__ == "nucleus.ctx._dispatch", (
        f"ctx.copy_from must be from nucleus.ctx._dispatch; got {ctx.copy_from.__module__}."
    )


def test_sql_resolves_to_function() -> None:
    """``nucleus.ctx.sql`` MUST be the SQL execution function."""
    from nucleus import ctx

    assert callable(ctx.sql)
    assert ctx.sql.__module__ == "nucleus.ctx.sql"


def test_read_resolves_to_function() -> None:
    """``nucleus.ctx.read`` MUST be the lazy reader function."""
    from nucleus import ctx

    assert callable(ctx.read)
    assert ctx.read.__module__ == "nucleus.ctx.read"


def test_nucleus_error_is_exception_class() -> None:
    """``nucleus.ctx.NucleusError`` MUST be the base exception class for
    ``except nucleus.ctx.NucleusError as exc:`` use."""
    from nucleus import ctx

    assert isinstance(ctx.NucleusError, type)
    assert issubclass(ctx.NucleusError, Exception)


def test_deferred_v01_symbols_not_exported() -> None:
    """``ctx.write`` / ``ctx.log`` / ``ctx.params`` MUST NOT be in v0.1 ``__all__``.

    Per Phase D scope decision (2026-05-14): these three are deferred to
    v0.2+ with practical substitutes (asset body return, stdlib logging,
    CLI flags). The public surface MUST NOT advertise them.
    """
    from nucleus import ctx

    deferred = {"write", "log", "params"}
    leaked = deferred & set(ctx.__all__)
    assert not leaked, (
        f"v0.2+ deferred ctx symbols leaked into v0.1 __all__: {leaked}. "
        "Either ratify them as v0.1 features (with ADR) or remove from __all__."
    )


def test_copy_from_unsupported_scheme_via_public_surface() -> None:
    """End-to-end smoke through ``ctx.copy_from`` (not via submodule)."""
    from nucleus import ctx

    with pytest.raises(ctx.NucleusError) as exc_info:
        ctx.copy_from(
            "http://example.com/data",
            table="orders",
            target="bronze.orders",
            warehouse_dir="./nonexistent_warehouse",
        )
    # error_code is set by the NucleusConfigError subclass per ADR-006
    assert exc_info.value.error_code.startswith("NE"), (
        f"NucleusError must carry an NE-code; got {exc_info.value.error_code!r}"
    )
