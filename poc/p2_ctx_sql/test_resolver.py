"""PoC #2 tests — 7 cases, not 70. Iterate from here.

Verifies ``resolve_sql()``:
    - Renders a single ``{{ ref('schema.name') }}`` to the resolved string
    - Renders multiple refs and returns them in encounter order
    - Deduplicates refs that appear twice (returned list, not the SQL itself)
    - Translates Jinja's ``StrictUndefined`` error → ``NucleusSQLSyntaxError``
    - Rejects malformed names with a clear ``fix_hint``
    - Returns ``(template_unchanged, [])`` for plain SQL (no refs)
    - Never leaks the substring ``"jinja2"`` into NucleusSQLSyntaxError output
      (mirrors PoC #1's §2.5 leak check; v4.1 §6.4)
"""

from __future__ import annotations

import pytest

from nucleus.errors import NucleusSQLSyntaxError
from poc.p2_ctx_sql.resolver import resolve_sql


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
