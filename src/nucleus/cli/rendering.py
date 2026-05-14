"""CLI output rendering helpers — text / NDJSON / CSV.

Per ``nucleus_cli_spec.md`` §5 (output format contract). Public functions
accept an optional ``console`` so tests can capture output via
``rich.console.Console(record=True)`` without monkey-patching stdout.

Per ``nucleus_architecture_v4.1.md`` §6.4 + AGENTS.md §11.7: zero
external classnames (``dagster.``, ``duckdb.``, ``polars.``,
``pyiceberg.``) appear here. Plain English column headers only.

Pins/docs (per AGENTS.md §11.12):
    - rich==13.9.4 — https://rich.readthedocs.io/
    - csv (stdlib) — https://docs.python.org/3/library/csv.html
    - json (stdlib) — https://docs.python.org/3/library/json.html
    - croniter==3.0.4 — https://pypi.org/project/croniter/ (used by
      render_schedule_list for next-run preview via coordination.schedules)
"""

from __future__ import annotations

import csv
import json
import sys
from collections.abc import Iterable
from typing import Any, Literal

from rich.console import Console
from rich.table import Table

from nucleus.coordination.schedules import ScheduleEntry
from nucleus.sdk.results import MaterializationResult

_TRUNCATE_AT = 80


def _truncate(value: Any) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= _TRUNCATE_AT else text[: _TRUNCATE_AT - 1] + "\u2026"


def render_materialization_result(
    result: MaterializationResult,
    *, status: str = "success",
    format_: Literal["text", "json"] = "text",
    console: Console | None = None,
) -> None:
    """Render a single :class:`MaterializationResult` to text or NDJSON."""
    out = console or Console(file=sys.stdout, soft_wrap=False)
    if format_ == "json":
        payload = {
            "_schema_version": 1, "asset_key": result.asset_key, "status": status,
            "snapshot_id": result.snapshot_id, "row_count": result.row_count,
            "duration_ms": result.duration_ms, "lineage_event_id": result.lineage_event_id,
            "partition": result.partition,
            "materialized_at": result.materialized_at.isoformat(),
        }
        # Bypass Rich for JSON to avoid soft-wrapping single-line NDJSON.
        sys.stdout.write(json.dumps(payload) + "\n")
        return
    table = Table(title="Materialization", show_lines=False)
    # no_wrap=True on the asset column ensures the key is never elided by Rich's
    # responsive layout even when snapshot_id is a long numeric ID.
    table.add_column("asset", no_wrap=True)
    for header in ("status", "snapshot", "rows", "duration_ms", "lineage_event"):
        table.add_column(header)
    # Snapshot IDs are 18-19 digit numbers; cap at 16 chars for display
    # to keep the table scannable in narrow terminals.
    _snap = result.snapshot_id
    snap_display = (_snap[:16] + "…" if len(_snap) > 16 else _snap) or "-"
    table.add_row(
        result.asset_key, status, snap_display,
        str(result.row_count), str(result.duration_ms),
        _truncate(result.lineage_event_id) or "-",
    )
    out.print(table)


def render_query_rows(
    columns: list[str],
    rows: Iterable[tuple[Any, ...]],
    *,
    format_: Literal["text", "json", "csv"] = "text",
    limit: int = 100,
    console: Console | None = None,
) -> int:
    """Render query rows; return the count actually emitted (≤``limit``)."""
    out_console = console or Console(file=sys.stdout, soft_wrap=False)
    if format_ == "json":
        emitted = 0
        for row in rows:
            if emitted >= limit:
                break
            payload = {**dict(zip(columns, row, strict=False)), "_schema_version": 1}
            sys.stdout.write(json.dumps(payload, default=str) + "\n")
            emitted += 1
        return emitted
    if format_ == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(columns)
        emitted = 0
        for row in rows:
            if emitted >= limit:
                break
            writer.writerow(["" if c is None else c for c in row])
            emitted += 1
        return emitted
    table = Table(show_lines=False)
    for header in columns:
        table.add_column(header)
    emitted, extra = 0, False
    for row in rows:
        if emitted >= limit:
            extra = True
            break
        table.add_row(*[_truncate(c) for c in row])
        emitted += 1
    out_console.print(table)
    if extra:
        out_console.print(f"[dim](truncated to first {limit} rows)[/dim]")
    return emitted


def render_ingest_summary(
    asset_key: str, rows_written: int, snapshot_id: str,
    preview_columns: list[str], preview_rows: list[tuple[Any, ...]],
    *, console: Console | None = None,
) -> None:
    """Render the ``nucleus ingest`` summary + 10-row preview."""
    out_console = console or Console(file=sys.stdout, soft_wrap=False)
    summary = Table(title="Ingest summary", show_lines=False)
    for header in ("asset", "rows", "snapshot"):
        summary.add_column(header)
    summary.add_row(asset_key, str(rows_written), _truncate(snapshot_id) or "-")
    out_console.print(summary)
    if not preview_columns:
        return
    preview = Table(title="Preview (first 10 rows)", show_lines=False)
    for header in preview_columns:
        preview.add_column(header)
    for row in preview_rows[:10]:
        preview.add_row(*[_truncate(c) for c in row])
    out_console.print(preview)


def render_runtime_endpoint_table(
    rows: list[tuple[str, str]],
    *,
    title: str = "Local stack",
    console: Console | None = None,
) -> None:
    """Print service name + reachable URL pairs after ``nucleus up``."""
    out = console or Console(file=sys.stdout, soft_wrap=False)
    table = Table(title=title, show_lines=False)
    table.add_column("service")
    table.add_column("endpoint")
    for name, endpoint in rows:
        table.add_row(name, endpoint)
    out.print(table)


def render_asset_list(
    keys: tuple[str, ...],
    *,
    format_: Literal["text", "json"] = "text",
    console: Console | None = None,
) -> None:
    """Render registered asset keys for ``nucleus list``.

    Per ``nucleus_cli_spec.md`` §3 list section + poc5-blocker-list-discoverability.
    Each row shows the asset key and its namespace (left of the ``.``).
    Empty registry prints a hint directing users to ``nucleus init``.
    """
    if format_ == "json":
        payload = {"_schema_version": 1, "assets": list(keys)}
        sys.stdout.write(json.dumps(payload) + "\n")
        return
    out = console or Console(file=sys.stdout, soft_wrap=False)
    if not keys:
        out.print(
            "[dim]No assets registered. "
            "Add @nucleus.asset(...) to a file under assets/ and run again.[/dim]"
        )
        return
    table = Table(title=f"Registered assets ({len(keys)})", show_lines=False)
    table.add_column("asset key", no_wrap=True)
    table.add_column("namespace")
    for key in keys:
        ns = key.split(".")[0] if "." in key else "-"
        table.add_row(key, ns)
    out.print(table)


def render_schedule_list(
    entries: tuple[ScheduleEntry, ...],
    *,
    console: Console | None = None,
) -> None:
    """Render the ``nucleus schedule list`` table.

    Shows: asset key, cron expression, and the next scheduled run (UTC).
    An empty table is rendered with a hint when no assets have schedules.

    Per ADR-017 §3 + ``nucleus_cli_spec.md`` §3 schedule section.
    """
    from nucleus.coordination.schedules import preview_schedule  # noqa: PLC0415
    from nucleus.errors import NucleusError  # noqa: PLC0415

    out = console or Console(file=sys.stdout, soft_wrap=False)

    if not entries:
        out.print(
            "[dim]No scheduled assets found. "
            "Add schedule='<cron>' to a @nucleus.asset decorator.[/dim]"
        )
        return

    table = Table(title="Scheduled assets (Beta)", show_lines=False)
    table.add_column("asset", no_wrap=True)
    table.add_column("cron")
    table.add_column("next run (UTC)")

    for entry in entries:
        try:
            runs = preview_schedule(entry.asset_key, n=1)
            next_run = runs[0] if runs else "-"
        except NucleusError:
            next_run = "-"
        table.add_row(entry.asset_key, entry.cron_expression, _truncate(next_run))

    out.print(table)
