"""PoC #2 tests — 16 cases after the v0.2 hardening pass.

Original 7 (kept verbatim):
    - Single ``{{ ref('schema.name') }}`` renders to the resolved string
    - Multiple refs in one template, returned in encounter order
    - Duplicate refs deduplicated in the returned list (not the SQL)
    - Jinja's ``StrictUndefined`` → ``NucleusSQLSyntaxError`` (cause set)
    - Malformed name → ``NucleusSQLSyntaxError`` with clear ``fix_hint``
    - Plain SQL (no refs) → ``(template_unchanged, [])``
    - No ``"jinja2"`` substring leaks into rendered error output
      (mirrors PoC #1's §2.5 leak check; v4.1 §6.4)

Hardening 9 (T1-T5, T7-T10 per parity-with-PoC-#1 pass):
    T1  Unquoted ref argument → NucleusSQLSyntaxError
    T2  Missing argument        → NucleusSQLSyntaxError (asset-name hint)
    T3  Extra arguments         → NucleusSQLSyntaxError (1-arg hint)
    T4  Unknown asset           → NucleusAssetNotFound + suggestion list
    T5  Whitespace tolerance    → identical to no-whitespace (positive)
    T7  Jinja block comments    → stripped (positive)
    T8  Injection-shaped name   → rejected at validation, ref_resolver
                                  never called
    T9  Circular ref            → NucleusInvalidAssetDefinition, cites cycle
    T10 Empty asset name        → NucleusSQLSyntaxError
"""

from __future__ import annotations

import pytest

from nucleus.coordination.sql_resolver import resolve_sql
from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusInvalidAssetDefinition,
    NucleusSQLSyntaxError,
)


def _resolve(name: str) -> str:
    """Test stub — wraps the asset name in a marker for assertions."""
    return f"<<{name}>>"


def test_simple_ref_renders_to_resolved_string() -> None:
    sql, refs = resolve_sql("SELECT * FROM {{ ref('staging.orders') }}", _resolve)

    assert sql == "SELECT * FROM <<staging.orders>>"
    assert refs == ["staging.orders"]


def test_multiple_refs_in_one_template() -> None:
    template = (
        "SELECT * FROM {{ ref('staging.orders') }} "
        "JOIN {{ ref('staging.customers') }} USING (id) "
        "JOIN {{ ref('marts.regions') }} USING (region_id)"
    )
    sql, refs = resolve_sql(template, _resolve)

    assert "<<staging.orders>>" in sql
    assert "<<staging.customers>>" in sql
    assert "<<marts.regions>>" in sql
    assert refs == ["staging.orders", "staging.customers", "marts.regions"]


def test_duplicate_refs_deduplicated_in_returned_list() -> None:
    template = (
        "SELECT * FROM {{ ref('staging.orders') }} "
        "WHERE id IN (SELECT id FROM {{ ref('staging.orders') }})"
    )
    sql, refs = resolve_sql(template, _resolve)

    assert sql.count("<<staging.orders>>") == 2
    assert refs == ["staging.orders"]


def test_unknown_jinja_variable_raises_nucleus_sql_syntax_error() -> None:
    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql("SELECT {{ undefined_var }}", _resolve)

    assert exc_info.value.__cause__ is not None
    assert "undefined" in exc_info.value.user_message.lower()


def test_malformed_ref_name_raises_nucleus_sql_syntax_error() -> None:
    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql("SELECT * FROM {{ ref('Bad Name') }}", _resolve)

    err = exc_info.value
    assert "Bad Name" in err.user_message
    assert "schema" in err.fix_hint.lower()
    assert "name" in err.fix_hint.lower()


def test_no_refs_returns_empty_list() -> None:
    template = "SELECT 1 AS one, 2 AS two"
    sql, refs = resolve_sql(template, _resolve)

    assert sql == template
    assert refs == []


def test_renderer_does_not_leak_jinja_classnames_in_error_message() -> None:
    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql("SELECT {{ undefined_var }}", _resolve)

    err = exc_info.value
    rendered = err.rendered()
    assert "jinja2" not in err.user_message.lower()
    assert "jinja2" not in rendered.lower(), (
        f"jinja2 type leaked into rendered output:\n{rendered}"
    )


# ---------------------------------------------------------------------------
# Hardening pass (T1-T5, T7-T10) — parity-with-PoC-#1 error-path coverage.
# Every error path raises a typed NucleusError subclass; no library class
# names leak into ``user_message`` or ``fix_hint`` (v4.1 §6.4).
# ---------------------------------------------------------------------------


def test_unquoted_ref_argument_raises_nucleus_sql_syntax_error() -> None:
    """T1: ``ref(staging_orders)`` (no quotes) — StrictUndefined OR non-string path."""
    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql("SELECT * FROM {{ ref(staging_orders) }}", _resolve)
    err = exc_info.value
    msg, hint = err.user_message.lower(), err.fix_hint.lower()
    assert "undefined" in msg or "quoted" in msg or "quotes" in hint, (
        f"Unexpected wording: {err.user_message!r} / {err.fix_hint!r}"
    )


def test_ref_with_no_arguments_raises_nucleus_sql_syntax_error() -> None:
    """T2: ``{{ ref() }}`` — arity check rejects, hint points at asset name."""
    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql("SELECT * FROM {{ ref() }}", _resolve)
    err = exc_info.value
    assert "0 positional" in err.user_message
    assert "asset name" in err.fix_hint.lower()


def test_ref_with_extra_arguments_raises_nucleus_sql_syntax_error() -> None:
    """T3: ``{{ ref('a.b', 'extra') }}`` — arity check rejects 2-arg call."""
    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql("SELECT * FROM {{ ref('staging.orders', 'extra') }}", _resolve)
    err = exc_info.value
    assert "1 positional" in err.user_message and "2 positional" in err.user_message


def test_unknown_asset_lists_available_assets() -> None:
    """T4: unknown asset → NucleusAssetNotFound + suggestion list; KeyError hidden."""

    def _strict(name: str) -> str:
        raise KeyError(name)

    with pytest.raises(NucleusAssetNotFound) as exc_info:
        resolve_sql(
            "SELECT * FROM {{ ref('staging.unknown') }}",
            _strict,
            available=["staging.orders", "staging.customers", "marts.regions"],
        )
    err = exc_info.value
    assert "staging.unknown" in err.user_message
    for n in ("staging.orders", "staging.customers", "marts.regions"):
        assert n in err.fix_hint
    assert "KeyError" not in err.user_message and "KeyError" not in err.fix_hint
    assert err.__cause__ is not None


def test_whitespace_in_ref_call_resolves_identically() -> None:
    """T5: whitespace inside ``{{ ... }}`` around the call is irrelevant."""
    sql, refs = resolve_sql(
        "SELECT * FROM {{   ref(  'staging.orders'  )   }}", _resolve
    )
    assert sql == "SELECT * FROM <<staging.orders>>"
    assert refs == ["staging.orders"]


def test_jinja_block_comments_are_stripped() -> None:
    """T7: ``{# ... #}`` block comments are removed from the rendered SQL."""
    sql, refs = resolve_sql(
        "{# header note — internal use only #}\nSELECT 1 AS one", _resolve
    )
    assert "internal use only" not in sql
    assert "SELECT 1 AS one" in sql
    assert refs == []


def test_sql_injection_shape_rejected_at_validation() -> None:
    """T8: injection-shaped name fails the name regex BEFORE ref_resolver runs."""
    called_with: list[str] = []

    def _watching(name: str) -> str:
        called_with.append(name)
        return f"<<{name}>>"

    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql(
            """SELECT * FROM {{ ref('\"; DROP TABLE x; --') }}""", _watching
        )
    assert called_with == [], "ref_resolver must NOT be invoked for invalid names"
    assert "valid asset name" in exc_info.value.user_message.lower()


def test_circular_ref_raises_nucleus_invalid_asset_definition() -> None:
    """T9: name already in caller-supplied ``_resolving`` set → cycle raised."""
    with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
        resolve_sql(
            "SELECT * FROM {{ ref('marts.a') }}",
            _resolve,
            _resolving=frozenset({"marts.a"}),
        )
    err = exc_info.value
    msg = err.user_message.lower()
    assert "marts.a" in err.user_message
    assert "circular" in msg or "cycle" in msg


def test_empty_asset_name_raises_nucleus_sql_syntax_error() -> None:
    """T10: ``{{ ref('') }}`` — empty string rejected before lookup."""
    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql("SELECT * FROM {{ ref('') }}", _resolve)
    msg = exc_info.value.user_message.lower()
    assert "non-empty" in msg or "empty" in msg


# ---------------------------------------------------------------------------
# User bindings (Phase D verifier MEDIUM #5, 2026-05-14):
# additive ``bindings`` parameter so ``ctx.sql`` can consolidate on this
# resolver instead of maintaining a second Jinja env.
# ---------------------------------------------------------------------------


def test_resolve_sql_with_bindings_renders_user_variable() -> None:
    """Happy path: a binding is substituted as a Jinja global."""
    rendered, refs = resolve_sql(
        "SELECT * FROM {{ ref('staging.orders') }} WHERE id > {{ min_id }}",
        _resolve,
        bindings={"min_id": 42},
    )
    assert "<<staging.orders>>" in rendered
    assert "42" in rendered
    assert refs == ["staging.orders"]


def test_resolve_sql_bindings_none_unchanged_behavior() -> None:
    """Regression guard: ``bindings=None`` MUST be a no-op (same output as no kw)."""
    sql_default, refs_default = resolve_sql(
        "SELECT * FROM {{ ref('staging.orders') }}", _resolve
    )
    sql_explicit, refs_explicit = resolve_sql(
        "SELECT * FROM {{ ref('staging.orders') }}", _resolve, bindings=None
    )
    assert sql_default == sql_explicit
    assert refs_default == refs_explicit


def test_resolve_sql_bindings_collision_with_ref_raises_syntax_error() -> None:
    """Reserved-name guard: ``bindings={'ref': ...}`` is rejected up front."""
    with pytest.raises(NucleusSQLSyntaxError) as exc_info:
        resolve_sql(
            "SELECT 1",
            _resolve,
            bindings={"ref": "anything"},
        )
    err = exc_info.value
    assert "ref" in err.user_message
    assert "reserved" in err.user_message.lower()
    # No external classname leaks into the user wording (v4.1 §6.4).
    rendered = err.rendered()
    assert "jinja2" not in rendered.lower()
