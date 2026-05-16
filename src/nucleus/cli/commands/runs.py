"""``nucleus runs`` command group — ADR-025 §P0-2.

Exposes the durable run ledger via CLI subcommands:

    nucleus runs list   [--limit N] [--asset KEY] [--status STATUS]
                        [--since ISO_TS]   [--format json]
    nucleus runs show   RUN_ID             [--format json]
    nucleus runs cancel RUN_ID
    nucleus runs tail   [-n N]             [--follow]

Per ``docs/specs/nucleus_architecture_v4.1.md`` §8 L4 (CLI layer delegates all
business logic to the coordination layer).  The durable ledger lives at
``<project_root>/.nucleus/runs/runs.ndjson`` (ADR-025 §P0-2).

Stability: **Beta**
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Annotated

import typer

from nucleus.errors import NucleusError

# ---------------------------------------------------------------------------
# Typer sub-application
# ---------------------------------------------------------------------------
# Docs: https://typer.tiangolo.com/tutorial/subcommands/add-typer/
runs_app = typer.Typer(
    name="runs",
    help=(
        "Inspect asset run history from the durable ledger (Beta, ADR-025). "
        "History persists at ``<project_root>/.nucleus/runs/runs.ndjson``."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _exit_runs_error(err: NucleusError, code: int = 1) -> None:
    """Render NucleusError to stderr and exit — mirrors ``schedule.py`` pattern.

    UX audit Rec #3 (2026-05-15): bracket-prefix the NE-code so users can
    grep ``NE3011`` from terminal output like ``[ERROR_CONDITION]`` in
    Databricks or ``nnnnnn (sqlstate):`` in Snowflake.
    """
    code_tag = getattr(err, "error_code", "") or "NE3001"
    typer.echo(f"Error [{code_tag}]: {err.user_message}", err=True)
    if err.fix_hint:
        typer.echo(f"Fix:   {err.fix_hint}", err=True)
    typer.echo(f"Docs:  {err.docs_url}", err=True)
    raise typer.Exit(code=code)


def _get_ledger() -> RunLedger:  # type: ignore[return]  # noqa: F821
    """Locate project root and return a :class:`RunLedger` for it.

    Falls back to ``cwd`` when no ``nucleus_project.yaml`` is found
    (e.g. programmatic callers and tests).
    """
    from nucleus.cli.main import _locate_project_config
    from nucleus.coordination.run_ledger import RunLedger

    try:
        config_path = _locate_project_config()
        return RunLedger(config_path.parent)
    except NucleusError:
        return RunLedger(Path.cwd())


# Status → Rich markup dot
_STATUS_DOT: dict[str, str] = {
    "success": "[green]●[/green]",
    "failed": "[red]●[/red]",
    "running": "[yellow]●[/yellow]",
    "cancelled": "[dim]●[/dim]",
}

# UX audit Rec #1 (2026-05-15): Title-Case status words next to the dot so
# Databricks Lakeflow / Snowflake Task users see the same vocabulary they
# already memorised. Databricks ships `Succeeded / Failed / Running /
# Cancelled`; Snowflake ships the same set; we render Title-Case "success"
# → "Succeeded" so the visible word matches both giants.
_STATUS_DISPLAY: dict[str, str] = {
    "success": "Succeeded",
    "failed": "Failed",
    "running": "Running",
    "cancelled": "Cancelled",
}


def _dot(status: str) -> str:
    return _STATUS_DOT.get(status, "●")


def _status_label(status: str) -> str:
    """Return Title-Case status label per UX audit Rec #1."""
    return _STATUS_DISPLAY.get(status, status.title() if status else "Unknown")


def _fmt_duration(ms: int | None) -> str:
    if ms is None:
        return "-"
    if ms < 1000:
        return f"{ms}ms"
    return f"{ms / 1000:.1f}s"


def _fmt_ts(ts: str | None) -> str:
    """Trim ISO 8601 to ``YYYY-MM-DD HH:MM:SS`` for table display."""
    if not ts:
        return "-"
    return ts[:19].replace("T", " ")


# ---------------------------------------------------------------------------
# nucleus runs list
# ---------------------------------------------------------------------------


@runs_app.command("list")
def runs_list(
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum runs to show (default 50)."),
    ] = 50,
    asset_key: Annotated[
        str | None,
        typer.Option("--asset", help="Filter by asset key, e.g. ``raw.orders``."),
    ] = None,
    status_filter: Annotated[
        str | None,
        typer.Option(
            "--status",
            help="Filter by status: ``success`` | ``failed`` | ``running`` | ``cancelled``.",
        ),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help=(
                "ISO 8601 UTC lower bound, e.g. ``2026-05-01T00:00:00+00:00``. "
                "Runs started before this timestamp are excluded."
            ),
        ),
    ] = None,
    format_: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            envvar="NUCLEUS_FORMAT",
            help="Output format: [bold]text[/bold] | json (NDJSON) | jsonl (alias).",
        ),
    ] = "text",
) -> None:
    """List recent asset runs from the durable ledger, newest first.

    Per [bold]ADR-025 §P0-2[/bold]. Reads from
    ``<project_root>/.nucleus/runs/runs.ndjson``.

    [bold]Examples[/bold]

        nucleus runs list
        nucleus runs list --limit 10 --asset raw.orders
        nucleus runs list --status failed --format json
    """
    try:
        # UX audit Rec #8 (2026-05-15): accept ``jsonl`` as a synonym of ``json``
        # — `nucleus runs list` already emits NDJSON, jq's ecosystem uses .jsonl.
        if format_ not in {"text", "json", "jsonl"}:
            from nucleus.errors import NucleusInvalidAssetDefinition

            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported for `nucleus runs list`.",
                fix_hint="Pass --format text (default), --format json (NDJSON), or --format jsonl (alias).",
            )

        ledger = _get_ledger()
        records = ledger.list(
            limit=limit,
            asset_key=asset_key,
            status=status_filter,
            since=since,
        )

        if format_ in {"json", "jsonl"}:
            for r in records:
                sys.stdout.write(json.dumps(r.to_dict()) + "\n")
            return

        if not records:
            typer.echo("No runs recorded yet.  Materialise an asset with `nucleus run <key>`.")
            return

        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(show_lines=False, pad_edge=False)
        # UX audit Rec #1: status dot + Title-Case word so DB/SF users see
        # the same vocabulary they memorised.
        table.add_column("")  # status dot
        table.add_column("status", no_wrap=True)
        table.add_column("run id", no_wrap=True)
        table.add_column("asset", no_wrap=True)
        table.add_column("duration", justify="right")
        table.add_column("started", no_wrap=True)
        table.add_column("trigger")

        for r in records:
            table.add_row(
                _dot(r.status),
                _status_label(r.status),
                r.run_id[:8],
                r.asset_key,
                _fmt_duration(r.duration_ms),
                _fmt_ts(r.started_at),
                r.trigger,
            )
        console.print(table)
    except NucleusError as err:
        _exit_runs_error(err)


# ---------------------------------------------------------------------------
# nucleus runs show
# ---------------------------------------------------------------------------


@runs_app.command("show")
def runs_show(
    run_id: Annotated[
        str,
        typer.Argument(help="Run ID (or 8-char prefix) to inspect."),
    ],
    format_: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            envvar="NUCLEUS_FORMAT",
            help="Output format: [bold]text[/bold] | json | jsonl (alias).",
        ),
    ] = "text",
) -> None:
    """Show all fields for one run, including error details and fix hint.

    Per [bold]ADR-025 §P0-2[/bold]. Raises [bold]NE3011[/bold] if the
    run ID is not found in the ledger.

    [bold]Examples[/bold]

        nucleus runs show 01HXX1234
        nucleus runs show 01HXX1234 --format json
    """
    try:
        # UX audit Rec #8 (2026-05-15): accept ``jsonl`` as a synonym.
        if format_ not in {"text", "json", "jsonl"}:
            from nucleus.errors import NucleusInvalidAssetDefinition

            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported for `nucleus runs show`.",
                fix_hint="Pass --format text (default), --format json, or --format jsonl (alias).",
            )

        ledger = _get_ledger()
        record = ledger.get(run_id)

        if record is None:
            from nucleus.errors import NucleusRunNotFoundError

            raise NucleusRunNotFoundError(
                user_message=f"Run {run_id!r} not found in the ledger.",
                fix_hint="Use `nucleus runs list` to see available run IDs.",
            )

        if format_ in {"json", "jsonl"}:
            sys.stdout.write(json.dumps(record.to_dict()) + "\n")
            return

        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()
        lines = [
            f"run id:     {record.run_id}",
            f"asset:      {record.asset_key}",
            f"status:     {record.status}",
            f"trigger:    {record.trigger}",
            f"started:    {_fmt_ts(record.started_at)}",
            f"finished:   {_fmt_ts(record.finished_at)}",
            f"duration:   {_fmt_duration(record.duration_ms)}",
            f"rows:       {record.row_count if record.row_count is not None else '-'}",
            f"snapshot:   {record.snapshot_id or '-'}",
        ]
        if record.error_code:
            lines.append(f"error code: {record.error_code}")
        if record.error_message:
            lines.append(f"error:      {record.error_message}")

        title_style = {
            "success": "green",
            "failed": "red",
            "running": "yellow",
            "cancelled": "dim",
        }.get(record.status, "white")

        console.print(
            Panel(
                Text("\n".join(lines)),
                title=f"[{title_style}]{record.status}[/{title_style}]",
            )
        )
        if record.fix_hint:
            console.print(f"\n[yellow]Fix:[/yellow] {record.fix_hint}")
    except NucleusError as err:
        _exit_runs_error(err)


# ---------------------------------------------------------------------------
# nucleus runs cancel
# ---------------------------------------------------------------------------


@runs_app.command("cancel")
def runs_cancel(
    run_id: Annotated[
        str,
        typer.Argument(help="Run ID to mark as cancelled in the ledger."),
    ],
) -> None:
    """Mark a running run as cancelled in the ledger (marker only).

    This does **not** terminate any live process — send SIGTERM to the
    ``nucleus run`` process for that.

    Per [bold]ADR-025 §P0-2[/bold].

    [bold]Examples[/bold]

        nucleus runs cancel 01HXX1234
    """
    try:
        ledger = _get_ledger()
        ok = ledger.cancel(run_id)
        if not ok:
            record = ledger.get(run_id)
            if record is None:
                from nucleus.errors import NucleusRunNotFoundError

                raise NucleusRunNotFoundError(
                    user_message=f"Run {run_id!r} not found in the ledger.",
                    fix_hint="Use `nucleus runs list` to see available run IDs.",
                )
            typer.echo(
                f"Run {run_id[:8]} is already in terminal state "
                f"'{record.status}' — nothing to cancel.",
                err=True,
            )
            raise typer.Exit(code=1)
        typer.echo(f"Run {run_id[:8]} marked as cancelled.")
    except NucleusError as err:
        _exit_runs_error(err)


# ---------------------------------------------------------------------------
# nucleus runs tail
# ---------------------------------------------------------------------------


@runs_app.command("tail")
def runs_tail(
    n: Annotated[
        int,
        typer.Option(
            "-n",
            "--count",
            help="Number of most-recent runs to show (default 20).",
        ),
    ] = 20,
    follow: Annotated[
        bool,
        typer.Option(
            "--follow",
            "-f",
            help="Poll every 1 s for new runs and print additions (Ctrl-C to stop).",
        ),
    ] = False,
) -> None:
    """Show the N most recent runs; optionally follow in real time.

    Per [bold]ADR-025 §P0-2[/bold].

    [bold]Examples[/bold]

        nucleus runs tail
        nucleus runs tail -n 5
        nucleus runs tail --follow
    """
    try:
        ledger = _get_ledger()

        def _print_record(r: object) -> None:
            # UX audit Rec #1 (2026-05-15): include the Title-Case status
            # word next to the dot so non-TTY tails (CI logs, piped output)
            # carry the status without ANSI dot interpretation.
            typer.echo(
                f"{_dot(r.status)} {_status_label(r.status):<10}  "  # type: ignore[attr-defined]
                f"{r.run_id[:8]}  "  # type: ignore[attr-defined]
                f"{r.asset_key:<28}  "  # type: ignore[attr-defined]
                f"{_fmt_duration(r.duration_ms):>8}  "  # type: ignore[attr-defined]
                f"{_fmt_ts(r.started_at)}"  # type: ignore[attr-defined]
            )

        if not follow:
            records = ledger.tail(n)
            if not records:
                typer.echo("No runs yet.  Run `nucleus run <key>` to start one.")
                return
            for r in records:
                _print_record(r)
            return

        # --follow: print previously unseen records every 1 s.
        seen_ids: set[str] = set()
        while True:
            for r in ledger.tail(n):
                if r.run_id not in seen_ids:
                    seen_ids.add(r.run_id)
                    _print_record(r)
            time.sleep(1)
    except KeyboardInterrupt:
        raise typer.Exit(code=0)
    except NucleusError as err:
        _exit_runs_error(err)
