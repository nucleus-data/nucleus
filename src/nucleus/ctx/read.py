"""``ctx.read()`` — lazy Iceberg table reader (L4).

Per ``docs/specs/nucleus_architecture_v4.1.md`` §5.4 (Physics layer — Iceberg read
path) and ``docs/specs/nucleus_ctx_sdk_spec.md`` §4 (Read API). Provides a standalone
``read()`` function that opens a filesystem Iceberg table and returns its
data in the format requested by the caller.

v0.1 scope:
    - Reads materialized assets from the filesystem catalog (filesystem SQL
      catalog via PyIceberg + Arrow scan).
    - Supported output formats: ``"polars"`` (default, ``pl.LazyFrame``),
      ``"arrow"`` (``pyarrow.Table``), and ``"duckdb"``
      (``duckdb.DuckDBPyRelation`` — eagerly evaluated via Arrow).
    - Snapshot time-travel (``snapshot=``, ``version=``) deferred to v0.3+.
    - Partition push-down (``partitions=``) deferred to v0.3+.
    - Dependency auto-tracking (DAG edge injection) deferred to v0.3+
      when the ctx runtime object is wired (v01_skeleton_plan §3.1 r4).

Stability (per ADR-005 §2):
    Beta @ v0.1 → Stable @ v0.5 → Frozen @ v1.0

Architecture refs:
    docs/specs/nucleus_architecture_v4.1.md §5.4 (Iceberg read path via PyIceberg+Arrow)
    docs/specs/nucleus_architecture_v4.1.md §6.4 (Error Translation Discipline)
    docs/specs/nucleus_ctx_sdk_spec.md §4.1 (ctx.read signature + as_ formats)
    docs/specs/nucleus_ctx_sdk_spec.md §4.2 (dependency tracking — deferred)
    docs/decisions/ADR-005-api-stability-tiering.md §2 (Beta tier)

Pins / docs:
    pyiceberg==0.11.1 — https://py.iceberg.apache.org/api/catalog/
    pyarrow==18.1.0 — https://arrow.apache.org/docs/python/api.html
    polars==1.18.0  — https://docs.pola.rs/api/python/stable/reference/lazyframe/
    duckdb==1.1.3   — https://duckdb.org/docs/api/python/dbapi
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nucleus.errors import (
    NucleusAssetNotMaterialized,
    NucleusCatalogError,
    NucleusConfigError,
    NucleusError,
    NucleusInvalidAssetDefinition,
    NucleusIOError,
)
from nucleus.sdk.results import AssetRef

# Accepted as_ values per spec §4.1.
# "pandas" is intentionally last-resort and deferred in v0.1 — users should
# reach for "polars" or "arrow" instead (see spec §4.1 "pd.DataFrame (last resort)").
_SUPPORTED_FORMATS: frozenset[str] = frozenset({"polars", "arrow", "duckdb", "pandas"})


def _convert_arrow(arrow_table: Any, *, as_: str) -> Any:
    """Convert a ``pyarrow.Table`` to the output format requested by ``as_``.

    Centralises all format-dispatch branches so ``read()`` stays under the
    ruff PLR0912 branch limit.  Internal helper — not part of the public surface.

    Args:
        arrow_table: The pyarrow.Table produced by the Iceberg scan.
        as_: One of the ``_SUPPORTED_FORMATS`` values.
    """
    if as_ == "arrow":
        # Docs: https://arrow.apache.org/docs/python/api/tables.html  (pyarrow==18.1.0)
        return arrow_table

    if as_ == "polars":
        # Docs: https://docs.pola.rs/api/python/stable/reference/lazyframe/  (polars==1.18.0)
        import polars as pl  # pin: 1.18.0

        # pl.from_arrow returns DataFrame | Series; an arrow Table always
        # converts to DataFrame at runtime (Series is only returned for
        # ChunkedArray inputs).  Cast to keep the public typed surface.
        df = pl.from_arrow(arrow_table)
        # pl.from_arrow returns DataFrame | Series; narrow for the public typed surface.
        assert isinstance(df, pl.DataFrame)
        return df.lazy()

    if as_ == "duckdb":
        # Eagerly load into DuckDB via Arrow to avoid connection-lifetime issues.
        # The relation is created from the in-memory arrow_table; DuckDB does not
        # need the Iceberg catalog to stay open after this point.
        # Docs: https://duckdb.org/docs/api/python/dbapi  (duckdb==1.1.3)
        import duckdb  # pin: 1.1.3

        return duckdb.from_arrow(arrow_table)

    # as_ == "pandas" — last resort per spec §4.1; requires pandas installed.
    # pandas is not a pinned runtime dep in pyproject.toml; availability is not
    # guaranteed so we catch the import error and surface a NucleusConfigError.
    try:
        return arrow_table.to_pandas()
    except Exception as exc:
        raise NucleusConfigError(
            user_message=("ctx.read(..., as_='pandas') requires pandas to be installed."),
            fix_hint=(
                "Install pandas: pip install pandas. "
                "Or use as_='polars' (default) or as_='arrow' instead."
            ),
            cause=exc,
        ) from exc


def read(
    asset_ref: str | AssetRef,
    *,
    warehouse_dir: str | Path,
    as_: str = "polars",
) -> Any:
    """Read a materialized Iceberg asset into the requested format.

    # Stability: Beta

    Per ``docs/specs/nucleus_ctx_sdk_spec.md`` §4.1 and
    ``docs/specs/nucleus_architecture_v4.1.md`` §5.4 (Physics layer Iceberg read path).
    Opens the filesystem catalog at ``warehouse_dir``, locates the asset by
    key, and returns its data in the format selected by ``as_``.

    Default output is ``polars.LazyFrame`` — encourages lazy evaluation and
    push-down optimization per spec §4.1 (Design note: "default: pl.LazyFrame
    — encourages lazy + push-down optimization").

    Args:
        asset_ref: Asset key in ``<namespace>.<name>`` form (e.g.
            ``"raw.orders"``), or an :class:`nucleus.AssetRef`. Must match
            the 2-level v0.1 key pattern.
        warehouse_dir: Filesystem catalog warehouse root directory.
        as_: Output format selector. One of:
            - ``"polars"`` (default) → ``polars.LazyFrame``
            - ``"arrow"`` → ``pyarrow.Table``
            - ``"duckdb"`` → ``duckdb.DuckDBPyRelation`` (eagerly evaluated)
            - ``"pandas"`` → ``pandas.DataFrame`` (last resort; requires
              pandas installed; deferred to v0.3+ in v0.1 docs)

    Returns:
        The asset data in the requested format.

    Raises:
        NucleusConfigError: ``as_`` is not a recognised format value.
            NE5001.
        NucleusAssetNotMaterialized: The asset is not found in the warehouse
            catalog (not ingested / not materialized yet). NE3003.
        NucleusCatalogError: The warehouse catalog could not be opened.
            NE1007.
        NucleusIOError: Filesystem read failure while scanning the Iceberg
            table. NE1005.
    """
    # Normalise asset_ref to a string key per ADR-013 §1 + spec §3.1.
    if isinstance(asset_ref, AssetRef):
        asset_key = asset_ref.key
    elif isinstance(asset_ref, str) and asset_ref:
        asset_key = asset_ref
    else:
        raise NucleusInvalidAssetDefinition(
            user_message=(
                f"ctx.read() requires a non-empty asset key (or AssetRef); "
                f"got {type(asset_ref).__name__!r}."
            ),
            fix_hint=("Pass a 2-level key string, e.g. ctx.read('raw.orders'), or an AssetRef."),
        )

    if as_ not in _SUPPORTED_FORMATS:
        raise NucleusConfigError(
            user_message=f"ctx.read(..., as_={as_!r}) is not a supported output format.",
            fix_hint=(
                f"Pass one of {sorted(_SUPPORTED_FORMATS)!r}. Default: 'polars' (polars.LazyFrame)."
            ),
        )

    # Parse asset_key → namespace, table_name.
    if "." not in asset_key or asset_key.count(".") != 1:
        raise NucleusInvalidAssetDefinition(
            user_message=(f"Asset key {asset_key!r} must be in '<namespace>.<name>' form."),
            fix_hint=(
                "v0.1 keys are 2-level (schema.name). "
                "3-level (catalog.schema.name) is deferred to v0.3+."
            ),
        )
    namespace, table_name = asset_key.split(".", 1)
    warehouse_path = Path(warehouse_dir)

    # Lazy imports — not at module level (keeps boot time clean per v4.1 §11.2).
    # Docs: https://py.iceberg.apache.org/api/catalog/  (pyiceberg==0.11.1)
    # Docs: https://arrow.apache.org/docs/python/api.html  (pyarrow==18.1.0)
    # Docs: https://docs.pola.rs/api/python/stable/reference/lazyframe/  (polars==1.18.0)
    from nucleus.ctx.copy_from import _open_catalog

    # -- Step 1: open filesystem catalog ----------------------------------------
    try:
        catalog = _open_catalog(warehouse_path)
    except NucleusError:
        raise
    except Exception as exc:
        raise NucleusCatalogError(
            user_message=(f"Failed to open warehouse catalog at '{warehouse_path}': {exc}"),
            fix_hint=(
                "Verify that warehouse_dir points to a valid Nucleus warehouse. "
                "Run 'nucleus init <name>' to create one."
            ),
            cause=exc,
        ) from exc

    # -- Step 2: load the Iceberg table -----------------------------------------
    # Docs: https://py.iceberg.apache.org/api/#load-a-table  (pyiceberg==0.11.1)
    try:
        ice_table = catalog.load_table((namespace, table_name))
    except NucleusError:
        raise
    except Exception as exc:
        # pyiceberg 0.8.1 raises NoSuchTableError (not in the public API on all
        # backends); treat any lookup failure as "not materialized".
        raise NucleusAssetNotMaterialized(
            user_message=(
                f"Asset '{asset_key}' is not found in the warehouse at "
                f"'{warehouse_path}'. It may not have been ingested yet."
            ),
            fix_hint=(
                f"Run 'nucleus ingest <source> --as {asset_key}' first, or "
                "call ctx.copy_from(..., target=...) to populate the asset."
            ),
            asset=asset_key,
            cause=exc,
        ) from exc

    # -- Step 3: scan to Arrow (common base format) ------------------------------
    # Docs: https://py.iceberg.apache.org/api/#read-a-table  (pyiceberg==0.11.1)
    # Docs: https://arrow.apache.org/docs/python/api/tables.html  (pyarrow==18.1.0)
    try:
        arrow_table = ice_table.scan().to_arrow()
    except NucleusError:
        raise
    except Exception as exc:
        raise NucleusIOError(
            user_message=f"Failed to scan Iceberg table '{asset_key}': {exc}",
            fix_hint=(
                "Check that the warehouse directory is accessible and the "
                "Iceberg metadata files are not corrupted."
            ),
            asset=asset_key,
            cause=exc,
        ) from exc

    # -- Step 4: convert to requested output format -----------------------------
    return _convert_arrow(arrow_table, as_=as_)


__all__ = ["read"]
