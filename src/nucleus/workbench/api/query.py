"""POST /api/query — SQL query execution endpoint.

Wraps ``nucleus.ctx.sql`` (which in turn uses DuckDB + Jinja) and returns
rows + schema as JSON for the Workbench Query Editor page.

``nucleus_architecture_v4.1.md`` §8.1 (Layer 4 Experience) + §5.6.0 (ctx.sql).
ADR-016 §3 — Fork B API surface.

The caller must supply ``warehouse_dir`` pointing to a valid Nucleus warehouse.
In dev mode the workbench CLI resolves it from ``nucleus_project.yaml`` via
the same logic as ``nucleus.cli.main._locate_project_config``.

# Stability: Internal @ v0.2
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Docs: https://fastapi.tiangolo.com/tutorial/body/
from fastapi import APIRouter, HTTPException
from fastapi.responses import ORJSONResponse

# Docs: https://docs.pydantic.dev/latest/concepts/models/  (pydantic v2)
from pydantic import BaseModel, Field

from nucleus.coordination.error_translation import translate
from nucleus.errors import NucleusError

router = APIRouter(prefix="/api", tags=["query"])

_MAX_ROWS = 1_000  # hard cap per call; paging deferred to v0.3


class QueryRequest(BaseModel):
    """Request body for POST /api/query."""

    sql: str = Field(..., description="SQL string (Jinja {{ ref() }} supported).")
    warehouse_dir: str = Field(
        "",
        description=(
            "Absolute path to the warehouse root.  When empty the server "
            "attempts to discover nucleus_project.yaml from cwd."
        ),
    )
    limit: int = Field(
        default=200,
        ge=1,
        le=_MAX_ROWS,
        description=f"Row cap (1-{_MAX_ROWS}; default 200).",
    )


def _resolve_warehouse(warehouse_dir: str) -> Path:
    """Resolve the warehouse path, falling back to project YAML discovery."""
    if warehouse_dir:
        return Path(warehouse_dir)
    # Mirror logic from nucleus.cli.main._locate_project_config.
    import os

    here = Path(os.getcwd()).resolve()
    for candidate in (here, *here.parents)[:4]:
        cfg = candidate / "nucleus_project.yaml"
        if cfg.is_file():
            import yaml  # type: ignore[import-untyped]

            try:
                data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
                rel = data.get("warehouse_dir", "warehouse")
                return (candidate / rel).resolve()
            except Exception:
                pass
    return here / "warehouse"


@router.post("/query", response_class=ORJSONResponse)
def execute_query(req: QueryRequest) -> Any:
    """Execute SQL against the warehouse and return rows + schema.

    Returns a JSON object with:
    - ``columns``: list of column names
    - ``rows``: list of row-arrays (up to ``limit``)
    - ``row_count``: actual number of rows returned
    - ``truncated``: true if more rows exist beyond the limit

    All caught exceptions are translated to NucleusError JSON per v4.1 §6.4.
    """
    if not req.sql or not req.sql.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "NE2001",
                "user_message": "A SQL string is required.",
                "fix_hint": "Pass the query in the 'sql' field of the request body.",
            },
        )

    try:
        from nucleus.ctx.sql import sql as ctx_sql

        warehouse_path = _resolve_warehouse(req.warehouse_dir)
        lazy = ctx_sql(req.sql, warehouse_dir=warehouse_path)

        # Collect up to limit + 1 to detect truncation.
        # Docs: https://docs.pola.rs/api/python/stable/reference/lazyframe/api/polars.LazyFrame.collect.html
        df = lazy.limit(req.limit + 1).collect()
        truncated = len(df) > req.limit
        df = df.head(req.limit)

        columns = df.columns
        rows: list[list[Any]] = []
        for row_dict in df.iter_rows(named=False):
            rows.append(list(row_dict))

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }
    except NucleusError as err:
        status = 400 if "Syntax" in type(err).__name__ else 500
        raise HTTPException(
            status_code=status,
            detail={"error_code": err.error_code, "user_message": err.user_message, "fix_hint": err.fix_hint},  # type: ignore[attr-defined]
        ) from err
    except Exception as exc:
        err = translate(exc)
        raise HTTPException(
            status_code=500,
            detail={"error_code": err.error_code, "user_message": err.user_message, "fix_hint": err.fix_hint},  # type: ignore[attr-defined]
        ) from err
