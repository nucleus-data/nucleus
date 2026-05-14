"""``ctx.sql()`` — Jinja-resolved SQL execution via DuckDB (L4).

Per ``nucleus_architecture_v4.1.md`` §5.6.0 (native ctx.sql scope) and
``nucleus_ctx_sdk_spec.md`` §6 (SQL API). Provides a standalone
``sql()`` function that:

    1. Opens the filesystem catalog at ``warehouse_dir`` and registers each
       Iceberg table as an Arrow-backed DuckDB view (same pattern as the
       CLI's ``_execute_sql`` in ``nucleus.cli.main``).
    2. Delegates ``{{ ref('schema.name') }}`` rendering and user-supplied
       Jinja ``**bindings`` to the canonical L3 resolver in
       ``nucleus.coordination.sql_resolver.resolve_sql`` (single Jinja env,
       ``StrictUndefined``, cycle detection, "did you mean" suggestions).
       Consolidated 2026-05-14 per Phase D verifier MEDIUM #5 — the second
       caller of the resolver, the right time to deduplicate per
       ``.cursor/rules/nucleus.mdc`` ("wrap when a second caller appears").
    3. Executes the rendered SQL via DuckDB and returns a
       ``polars.LazyFrame`` (v0.1 Beta; spec §6.1 targets
       ``duckdb.DuckDBPyRelation`` at Stable — deferred because connection
       lifetime management across caller scope is a v0.3+ design concern).

v0.1 scope ceiling (per v4.1 §5.6.0):
    - ``{{ ref('schema.name') }}`` only — ``source()``, ``config()``, and
      user macros are deferred to v0.3+.
    - Single in-memory DuckDB connection per call — not connection-pooled.

Stability (per ADR-005 §2):
    Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0

Architecture refs:
    nucleus_architecture_v4.1.md §5.6.0 (ctx.sql scope)
    nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    nucleus_ctx_sdk_spec.md §6.1 (SQL API — ref resolution + return type)
    nucleus_ctx_sdk_spec.md §6.2 ({{ ref() }} resolution semantics)

Pins / docs:
    duckdb==1.1.3 — https://duckdb.org/docs/api/python/dbapi
    jinja2==3.1.5 — https://jinja.palletsprojects.com/en/stable/api/
    pyiceberg==0.11.1 — https://py.iceberg.apache.org/api/catalog/
    polars==1.18.0 — https://docs.pola.rs/api/python/stable/reference/lazyframe/
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from nucleus.errors import (
    NucleusCatalogError,
    NucleusError,
)

_logger = logging.getLogger(__name__)


def _build_catalog_views(
    warehouse_path: Path,
) -> tuple[Any, dict[str, str]]:
    """Open the filesystem catalog and register tables as DuckDB Arrow views.

    Returns ``(conn, refs)`` where ``conn`` is an open DuckDB connection and
    ``refs`` maps ``"ns.tbl"`` asset keys to quoted DuckDB view names.
    The caller is responsible for closing ``conn`` via a ``try/finally``.

    Per ``nucleus_architecture_v4.1.md`` §5.6.0 (ctx.sql scope); mirrors the
    ``_register_catalog_in_duckdb`` pattern from ``nucleus.cli.main ~L399``.
    """
    import duckdb  # Docs: https://duckdb.org/docs/api/python/dbapi; pin: 1.1.3

    from nucleus.ctx.copy_from import _open_catalog  # filesystem catalog opener

    try:
        catalog = _open_catalog(warehouse_path)
    except NucleusError:
        raise
    except Exception as exc:
        raise NucleusCatalogError(
            user_message=(
                f"Failed to open warehouse catalog at '{warehouse_path}': {exc}"
            ),
            fix_hint=(
                "Verify that warehouse_dir points to a valid Nucleus warehouse. "
                "Run 'nucleus init <name>' to create one, or 'nucleus up' to "
                "start the stack."
            ),
            cause=exc,
        ) from exc

    refs: dict[str, str] = {}
    conn = duckdb.connect(":memory:")
    for ns_tuple in catalog.list_namespaces():
        ns = ns_tuple[0] if ns_tuple else ""
        if not ns:
            continue
        try:
            conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{ns}"')
        except Exception as exc:
            _logger.warning(
                "skipped namespace %r during catalog view registration: %s",
                ns,
                exc,
            )
            continue
        for ident in catalog.list_tables(ns):
            tbl = ident[-1]
            try:
                ice_table = catalog.load_table(ident)
                arrow_t = ice_table.scan().to_arrow()
                view_name = f"_arrow_{ns}_{tbl}"
                conn.register(view_name, arrow_t)
                conn.execute(
                    f'CREATE OR REPLACE VIEW "{ns}"."{tbl}" '
                    f'AS SELECT * FROM "{view_name}"'
                )
                refs[f"{ns}.{tbl}"] = f'"{ns}"."{tbl}"'
            except Exception as exc:
                _logger.warning(
                    "skipped asset %r during catalog view registration: %s. "
                    "queries that {{ ref(%r) }} this asset will raise "
                    "NucleusAssetNotFound; investigate via 'nucleus query "
                    "\"SELECT * FROM %s.%s\"' or check warehouse_dir layout.",
                    f"{ns}.{tbl}",
                    exc,
                    f"{ns}.{tbl}",
                    ns,
                    tbl,
                )
                continue
    return conn, refs


def _render_template(
    query: str,
    refs: dict[str, str],
    bindings: dict[str, object],
) -> str:
    """Render the Jinja SQL template via the canonical L3 resolver.

    Consolidated 2026-05-14 per Phase D verifier MEDIUM #5: delegates to
    ``nucleus.coordination.sql_resolver.resolve_sql`` instead of maintaining
    a second Jinja env. Inherits cycle detection, "did you mean" suggestions,
    and the single source of truth for ``ref()`` arity / name validation.

    Both ``{{ ref('...') }}`` and ``{{ key }}`` bindings are resolved in a
    single Jinja pass with ``StrictUndefined`` so undeclared variables raise
    ``NucleusSQLSyntaxError`` immediately (v4.1 §6.4 translation discipline).
    """
    # Local import to keep the L2 dependency edge explicit at the call site;
    # ctx (L4) -> coordination (L2) is a downward import per layering rules
    # in scripts/check_layering.py (verified clean).
    from nucleus.coordination.sql_resolver import resolve_sql

    rendered, _ordered = resolve_sql(
        query,
        ref_resolver=lambda name: refs[name],
        available=refs.keys(),
        bindings=bindings or None,
    )
    return rendered


def sql(
    query: str,
    *,
    warehouse_dir: str | Path,
    **bindings: object,
) -> Any:
    """Execute a Jinja-templated SQL string against the warehouse via DuckDB.

    # Stability: Beta

    Per ``nucleus_ctx_sdk_spec.md`` §6.1 + §6.2 and
    ``nucleus_architecture_v4.1.md`` §5.6.0. Renders
    ``{{ ref('schema.name') }}`` macros using the filesystem catalog at
    ``warehouse_dir``, resolves user-supplied ``**bindings`` as Jinja
    template variables, then executes the rendered SQL via DuckDB.

    Args:
        query: SQL string, optionally templated with ``{{ ref('...') }}``
            macros and ``{{ key }}`` Jinja expressions.
        warehouse_dir: Filesystem catalog warehouse root directory. All
            Iceberg tables at this location are available via their asset key
            inside ``{{ ref() }}`` expressions.
        **bindings: Jinja template variables substituted as literals.
            E.g. ``start_date="2024-01-01"`` replaces ``{{ start_date }}``
            in the template before DuckDB execution.

    Returns:
        ``polars.LazyFrame`` (v0.1 Beta). Call ``.collect()`` to materialise
        all rows. The return type upgrades to ``duckdb.DuckDBPyRelation`` at
        Stable (v0.5+) per ADR-005 §2 and spec §6.1.

    Raises:
        NucleusSQLSyntaxError: Template rendering failed (unknown variable,
            malformed braces, invalid ref() call) or DuckDB rejected the
            rendered SQL (parse / bind error).  NE2002.
        NucleusAssetNotFound: A ``{{ ref('...') }}`` argument is not
            registered in the warehouse catalog.  NE3002.
        NucleusCatalogError: The warehouse catalog at ``warehouse_dir`` could
            not be opened.  NE1007.
        NucleusEngineError: DuckDB raised a non-syntax execution failure.
            NE2005.
    """
    import polars as pl  # Docs: https://docs.pola.rs/api/python/stable/reference/; pin: 1.18.0

    warehouse_path = Path(warehouse_dir)
    conn, refs = _build_catalog_views(warehouse_path)
    try:
        rendered_sql = _render_template(query, refs, bindings)
        # Execute rendered SQL via DuckDB.
        # Docs: https://duckdb.org/docs/api/python/dbapi#execute  (duckdb==1.1.3)
        try:
            rel = conn.sql(rendered_sql)
            # Eagerly convert to Polars LazyFrame before closing the connection.
            # v0.1 Beta: spec §6.1 targets duckdb.DuckDBPyRelation at Stable;
            # deferred due to connection lifetime semantics across caller scope.
            arrow_result = rel.arrow()
            return pl.from_arrow(arrow_result).lazy()
        except NucleusError:
            raise
        except Exception as exc:
            # Translate DuckDB failures at the layer boundary per v4.1 §6.4.
            from nucleus.coordination.error_translation import translate

            raise translate(exc) from exc
    finally:
        conn.close()


__all__ = ["sql"]
