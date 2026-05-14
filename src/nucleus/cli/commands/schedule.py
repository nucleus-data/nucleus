"""``nucleus schedule`` command group — ADR-017.

Exposes read-only schedule metadata from the in-process asset registry:

    nucleus schedule list               list all assets with a schedule
    nucleus schedule preview <key>      show next N run times for one asset
    nucleus schedule on <key>           [deferred v0.2]
    nucleus schedule off <key>          [deferred v0.2]
    nucleus schedule trigger <key>      [deferred v0.2]

Per ``nucleus_architecture_v4.1.md`` §8 L4 (CLI layer delegates all
business logic to the coordination / ctx layers). Active scheduling (Dagster
daemon-driven execution) is deferred to v0.2 per ADR-017 §6.

Stability tier: **Beta** — governed by ``nucleus_cli_spec.md`` §3 schedule section.
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
    help=(
        "Inspect and manage asset schedules (Beta). "
        "Active scheduling (daemon-driven execution) ships in v0.2."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _exit_schedule_error(err: NucleusError, code: int = 1) -> None:
    """Render a NucleusError to stderr and exit — mirrors ``cli/main.py`` pattern."""
    typer.echo(f"Error: {err.user_message}", err=True)
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
    from nucleus.cli.main import _import_assets_package, _load_project_config, _locate_project_config  # noqa: PLC0415

    try:
        config_path = _locate_project_config()
        _load_project_config(config_path)
        _import_assets_package(config_path.parent)
    except NucleusError:
        # No project config nearby — registry may still be populated by tests or
        # by a programmatic caller.  Don't fail: return and let the command
        # surface an empty list if no assets are registered.
        pass


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

    Active scheduling (automatic execution) requires v0.2; this command
    reads the declared intent from ``@nucleus.asset(schedule=...)`` decorators.

    Per [bold]ADR-017 §3[/bold].

    [bold]Examples[/bold]

        nucleus schedule list
        nucleus schedule list --format json
    """
    try:
        if format_ not in {"text", "json"}:
            from nucleus.errors import NucleusInvalidAssetDefinition  # noqa: PLC0415

            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported for `nucleus schedule list`.",
                fix_hint="Pass --format text (default) or --format json.",
            )

        _import_project_assets()

        from nucleus.coordination.schedules import list_schedules, preview_schedule  # noqa: PLC0415

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
        from nucleus.cli.rendering import render_schedule_list  # noqa: PLC0415

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
            help=(
                "Asset key to preview (``<schema>.<name>``), "
                "e.g. ``marts.daily_revenue``."
            ),
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
    ``@nucleus.asset(schedule=...)`` decorator; no Dagster daemon is required.

    Per [bold]ADR-017 §3[/bold]. Uses croniter
    (Docs: https://pypi.org/project/croniter/) for time arithmetic.

    [bold]Examples[/bold]

        nucleus schedule preview marts.daily_revenue
        nucleus schedule preview marts.daily_revenue --count 5
        nucleus schedule preview marts.daily_revenue --format json
    """
    try:
        if format_ not in {"text", "json"}:
            from nucleus.errors import NucleusInvalidAssetDefinition  # noqa: PLC0415

            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported for `nucleus schedule preview`.",
                fix_hint="Pass --format text (default) or --format json.",
            )

        _import_project_assets()

        from nucleus.coordination.schedules import preview_schedule  # noqa: PLC0415

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
# Deferred stubs: nucleus schedule on / off / trigger
# Per ADR-017 §6: active scheduling deferred to v0.2.
# ---------------------------------------------------------------------------


@schedule_app.command("on")
def schedule_on(
    asset_key: Annotated[
        str,
        typer.Argument(help="Asset key to enable the schedule for."),
    ],
) -> None:
    """[dim][deferred v0.2][/dim] Enable automatic execution for a scheduled asset.

    This command is reserved for v0.2 when the Dagster scheduler daemon
    wiring lands. In v0.1.1 it raises a structured error so users understand
    the roadmap.
    """
    _raise_deferred("on", asset_key)


@schedule_app.command("off")
def schedule_off(
    asset_key: Annotated[
        str,
        typer.Argument(help="Asset key to disable the schedule for."),
    ],
) -> None:
    """[dim][deferred v0.2][/dim] Disable automatic execution for a scheduled asset."""
    _raise_deferred("off", asset_key)


@schedule_app.command("trigger")
def schedule_trigger(
    asset_key: Annotated[
        str,
        typer.Argument(help="Asset key to trigger a one-off run for."),
    ],
) -> None:
    """[dim][deferred v0.2][/dim] Trigger an immediate one-off materialization for a scheduled asset."""
    _raise_deferred("trigger", asset_key)


def _raise_deferred(sub: str, asset_key: str) -> None:
    """Common deferred-feature stub for schedule on/off/trigger."""
    from nucleus.errors import NucleusFeatureDeferredError  # noqa: PLC0415

    _exit_schedule_error(
        NucleusFeatureDeferredError(
            user_message=(
                f"`nucleus schedule {sub}` is deferred to v0.2. "
                f"Declaring schedule= on @nucleus.asset('{asset_key}') stores the "
                "expression; active daemon-driven scheduling ships in v0.2."
            ),
            fix_hint=(
                "Use `nucleus run <key>` to materialise the asset manually now. "
                "Track v0.2 progress at https://nucleus.dev/roadmap."
            ),
            asset=asset_key,
        )
    )
