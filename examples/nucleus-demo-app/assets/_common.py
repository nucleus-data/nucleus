"""Shared helpers for the Nucleus demo assets.

Centralises the warehouse path, the Postgres connection string, and the
SQL-template loader so the individual asset modules read top-to-bottom
without ``Path()`` plumbing.

Per ``docs/specs/nucleus_ctx_sdk_spec.md`` §0 (``ctx`` is the only thing users
import) — these helpers wrap nothing extra; they just resolve filesystem
paths so ``ctx.copy_from`` and ``ctx.sql`` calls stay one-liners.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE_DIR = str(PROJECT_ROOT / "data" / "warehouse")
SQL_DIR = PROJECT_ROOT / "sql"

# Demo Postgres credentials match docker-compose.yaml. Override via env vars
# for local debugging without editing source.
POSTGRES_URL = os.environ.get(
    "NUCLEUS_DEMO_POSTGRES_URL",
    "postgresql://nucleus:nucleus@127.0.0.1:5433/nucleus_demo",
)


def load_sql(name: str) -> str:
    """Read a SQL template from the project's ``sql/`` directory.

    Parameters
    ----------
    name:
        File stem under ``sql/`` (without the ``.sql`` extension), e.g.
        ``"silver_daily_revenue"`` resolves to ``sql/silver_daily_revenue.sql``.
    """
    sql_path = SQL_DIR / f"{name}.sql"
    return sql_path.read_text(encoding="utf-8")
