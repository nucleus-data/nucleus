"""``nucleus schedule`` command group — ADR-017 (v0.2.1 active scheduling).

Exposes schedule metadata and the mini-scheduler daemon lifecycle:

    nucleus schedule list               list all assets with a schedule
    nucleus schedule preview <key>      show next N run times for one asset
    nucleus schedule on [--foreground]  start the mini-scheduler daemon
    nucleus schedule off                stop the running daemon
    nucleus schedule trigger <key>      one-shot materialization (no daemon)
    nucleus schedule status             show daemon state + active schedules

Per ``nucleus_architecture_v4.1.md`` §8 L4 (CLI layer delegates all
business logic to the coordination layer). Active scheduling now wires
the mini-scheduler fallback per ADR-017 §v0.2.1 amendment.

Stability tier: **Beta** — governed by ``nucleus_cli_spec.md`` §3.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from nucleus.errors import NucleusError

# ---------------------------------------------------------------------------
# Typer sub-application
# ---------------------------------------------------------------------------
# Docs: https://typer.tiangolo.com/tutorial/subcommands/add-typer/
schedule_app = typer.Typer(
    name="schedule",
    help="Inspect and manage asset schedules (Beta).",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _exit_schedule_error(err: NucleusError, code: int = 1) -> None:
    """Render a NucleusError to stderr and exit — mirrors ``cli/main.py`` pattern.

    UX audit Rec #3 (2026-05-15): bracket-prefix the NE-code so users can
    grep ``NE5005`` from terminal output like ``[ERROR_CONDITION]`` in
    Databricks or ``nnnnnn (sqlstate):`` in Snowflake.
    """
    code_tag = getattr(err, "error_code", "") or "NE3001"
    typer.echo(f"Error [{code_tag}]: {err.user_message}", err=True)
    if err.fix_hint:
        typer.echo(f"Fix:   {err.fix_hint}", err=True)
    typer.echo(f"Docs:  {err.docs_url}", err=True)
    raise typer.Exit(code=code)


def _import_project_assets() -> None:
    """Load the current project's assets so @nucleus.asset decorators register.

    Mirrors the ``_locate_project_config`` + ``_import_assets_package`` pattern
    from ``cli/main.py`` — without duplicating that logic, we import the helpers
    lazily here so the schedule commands work inside a project directory.

    Silently no-ops when no ``nucleus_project.yaml`` is found so that
    ``nucleus schedule list`` still works when called programmatically from
    tests that register assets directly.
    """
    from nucleus.cli.main import (
        _import_assets_package,
        _load_project_config,
        _locate_project_config,
    )

    try:
        config_path = _locate_project_config()
        _load_project_config(config_path)
        _import_assets_package(config_path.parent)
    except NucleusError:
        # No project config nearby — registry may still be populated by tests or
        # by a programmatic caller.  Don't fail: return and let the command
        # surface an empty list if no assets are registered.
        pass


def _locate_project_root() -> Path | None:
    """Return the project root path, or None if no project config is found."""

    from nucleus.cli.main import _locate_project_config

    try:
        config_path = _locate_project_config()
        return config_path.parent
    except NucleusError:
        return None


# ---------------------------------------------------------------------------
# nucleus schedule list
# ---------------------------------------------------------------------------


@schedule_app.command("list")
def schedule_list(
    format_: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            envvar="NUCLEUS_FORMAT",
            help="Output format: [bold]text[/bold] | json.",
        ),
    ] = "text",
) -> None:
    """List all assets that declare a ``schedule=`` expression.

    Shows the asset key, cron expression, and the next scheduled run time.
    Assets without a ``schedule=`` kwarg are excluded from the list.

    Per [bold]ADR-017 §3[/bold].

    [bold]Examples[/bold]

        nucleus schedule list
        nucleus schedule list --format json
    """
    try:
        if format_ not in {"text", "json"}:
            from nucleus.errors import NucleusInvalidAssetDefinition

            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported for `nucleus schedule list`.",
                fix_hint="Pass --format text (default) or --format json.",
            )

        _import_project_assets()

        from nucleus.coordination.schedules import list_schedules, preview_schedule

        entries = list_schedules()

        if format_ == "json":
            rows = []
            for entry in entries:
                try:
                    next_runs = preview_schedule(entry.asset_key, n=1)
                    next_run = next_runs[0] if next_runs else None
                except NucleusError:
                    next_run = None
                rows.append(
                    {
                        "asset_key": entry.asset_key,
                        "cron_expression": entry.cron_expression,
                        "next_run": next_run,
                    }
                )
            typer.echo(json.dumps(rows, indent=2))
            return

        # Text mode — Rich table via rendering helper.
        from nucleus.cli.rendering import render_schedule_list

        render_schedule_list(entries)
    except NucleusError as err:
        _exit_schedule_error(err)


# ---------------------------------------------------------------------------
# nucleus schedule preview
# ---------------------------------------------------------------------------


@schedule_app.command("preview")
def schedule_preview(
    asset_key: Annotated[
        str,
        typer.Argument(
            help=("Asset key to preview (``<schema>.<name>``), e.g. ``marts.daily_revenue``."),
        ),
    ],
    n: Annotated[
        int,
        typer.Option(
            "--count",
            "-n",
            help="Number of upcoming run times to show (1-20, default 3).",
        ),
    ] = 3,
    format_: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            envvar="NUCLEUS_FORMAT",
            help="Output format: [bold]text[/bold] | json.",
        ),
    ] = "text",
) -> None:
    """Show the next N scheduled run times for one asset.

    Calculates future run times from the cron expression stored on the
    ``@nucleus.asset(schedule=...)`` decorator; no daemon is required.

    Per [bold]ADR-017 §3[/bold]. Uses croniter
    (Docs: https://pypi.org/project/croniter/) for time arithmetic.

    [bold]Examples[/bold]

        nucleus schedule preview marts.daily_revenue
        nucleus schedule preview marts.daily_revenue --count 5
        nucleus schedule preview marts.daily_revenue --format json
    """
    try:
        if format_ not in {"text", "json"}:
            from nucleus.errors import NucleusInvalidAssetDefinition

            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported for `nucleus schedule preview`.",
                fix_hint="Pass --format text (default) or --format json.",
            )

        _import_project_assets()

        from nucleus.coordination.schedules import preview_schedule

        run_times = preview_schedule(asset_key, n=n)

        if format_ == "json":
            typer.echo(
                json.dumps(
                    {"asset_key": asset_key, "next_runs": list(run_times)},
                    indent=2,
                )
            )
            return

        # Text mode.
        typer.echo(f"Next {len(run_times)} run time(s) for [bold]{asset_key}[/bold]:")
        for i, ts in enumerate(run_times, start=1):
            typer.echo(f"  {i}. {ts}")
    except NucleusError as err:
        _exit_schedule_error(err)


# ---------------------------------------------------------------------------
# nucleus schedule on
# ---------------------------------------------------------------------------


@schedule_app.command("on")
def schedule_on(
    foreground: Annotated[
        bool,
        typer.Option(
            "--foreground",
            help="Run the daemon in the foreground (blocking). Default: background.",
        ),
    ] = False,
    max_iters: Annotated[
        int | None,
        typer.Option(
            "--max-iters",
            hidden=True,
            help="Debug: stop daemon after this many poll iterations.",
        ),
    ] = None,
) -> None:
    """Start the mini-scheduler daemon.

    The daemon polls declared asset schedules every 5 seconds and calls
    ``materialize_asset`` for any cron expressions that fall due.  It runs
    as a detached background process by default; use ``--foreground`` for
    interactive debugging.

    Per [bold]ADR-017 §v0.2.1[/bold] (mini-scheduler fallback).

    [bold]Examples[/bold]

        nucleus schedule on
        nucleus schedule on --foreground
    """
    try:
        _import_project_assets()
        project_root = _locate_project_root()
        if project_root is None:
            from pathlib import Path

            project_root = Path.cwd()

        from nucleus.coordination.daemon import start_daemon

        pid = start_daemon(project_root, foreground=foreground, max_iters=max_iters)
        if not foreground:
            typer.echo(f"Nucleus scheduler daemon started (pid {pid}).")
    except NucleusError as err:
        _exit_schedule_error(err)


# ---------------------------------------------------------------------------
# nucleus schedule off
# ---------------------------------------------------------------------------


@schedule_app.command("off")
def schedule_off(
    timeout: Annotated[
        int,
        typer.Option(
            "--timeout",
            help="Seconds to wait for graceful shutdown before escalating.",
        ),
    ] = 10,
) -> None:
    """Stop the running mini-scheduler daemon.

    Sends SIGTERM and waits for a clean exit.  Escalates to SIGKILL after
    ``--timeout`` seconds if the daemon does not respond.

    Per [bold]ADR-017 §v0.2.1[/bold].

    [bold]Examples[/bold]

        nucleus schedule off
        nucleus schedule off --timeout 30
    """
    try:
        project_root = _locate_project_root()
        if project_root is None:
            from pathlib import Path

            project_root = Path.cwd()

        from nucleus.coordination.daemon import stop_daemon

        stop_daemon(project_root, timeout=timeout)
        typer.echo("Nucleus scheduler daemon stopped.")
    except NucleusError as err:
        _exit_schedule_error(err)


# ---------------------------------------------------------------------------
# nucleus schedule trigger
# ---------------------------------------------------------------------------


@schedule_app.command("trigger")
def schedule_trigger(
    asset_key: Annotated[
        str, typer.Argument(help="Asset key to trigger immediately (``<schema>.<name>``).")
    ],
) -> None:
    """Trigger an immediate one-shot materialization for an asset.

    Does NOT require the daemon to be running.  Materialises the asset right
    now regardless of its cron schedule.  Prints the snapshot ID on success.

    Per [bold]ADR-017 §v0.2.1[/bold].

    [bold]Examples[/bold]

        nucleus schedule trigger marts.daily_revenue
    """
    try:
        _import_project_assets()
        project_root = _locate_project_root()
        warehouse_dir = None
        if project_root is not None:
            from pathlib import Path

            from nucleus.cli.main import (
                _load_project_config,
                _locate_project_config,
            )

            try:
                cfg_path = _locate_project_config()
                cfg = _load_project_config(cfg_path)
                raw = cfg.get("storage", {}).get("warehouse", "")
                if raw:
                    warehouse_dir = Path(raw).expanduser()
                    if not warehouse_dir.is_absolute():
                        warehouse_dir = (project_root / warehouse_dir).resolve()
            except NucleusError:
                pass

        from nucleus.coordination.daemon import trigger_asset

        result = trigger_asset(asset_key, warehouse_dir=warehouse_dir)
        snap = result.snapshot_id or "(no snapshot)"
        typer.echo(
            f"Triggered materialization of '{asset_key}': "
            f"snapshot={snap}, rows={result.row_count}, "
            f"duration={result.duration_ms}ms"
        )
    except NucleusError as err:
        _exit_schedule_error(err)


# ---------------------------------------------------------------------------
# nucleus schedule status
# ---------------------------------------------------------------------------


@schedule_app.command("status")
def schedule_status() -> None:
    """Show the daemon's running state and active schedule list.

    Displays whether the mini-scheduler daemon is running (with its PID),
    plus a table of all scheduled assets with their next run times.

    Per [bold]ADR-017 §v0.2.1[/bold].

    [bold]Examples[/bold]

        nucleus schedule status
    """
    try:
        _import_project_assets()
        project_root = _locate_project_root()
        if project_root is None:
            from pathlib import Path

            project_root = Path.cwd()

        from nucleus.coordination.daemon import get_daemon_status

        status = get_daemon_status(project_root)

        if status.running:
            typer.echo(f"Daemon: [running] pid={status.pid}")
        else:
            typer.echo("Daemon: [stopped]")

        if not status.schedules:
            typer.echo("No scheduled assets found.")
            return

        # Render a simple table; Rich not required for status.
        typer.echo(f"\n{'Asset':<32} {'Cron':<15} {'Next run (UTC)'}")
        typer.echo("-" * 72)
        for entry in status.schedules:
            next_run = status.next_runs.get(entry.asset_key, "-")
            # Truncate next_run for readability (first 19 chars of ISO-8601).
            next_run_short = next_run[:19] if len(next_run) > 19 else next_run
            typer.echo(f"{entry.asset_key:<32} {entry.cron_expression:<15} {next_run_short}")
    except NucleusError as err:
        _exit_schedule_error(err)
