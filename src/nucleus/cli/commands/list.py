"""``nucleus list`` — registered-asset discoverability (PoC #5 Checkpoint 7).

Per ``docs/specs/nucleus_cli_spec.md`` §3 (CLI surface) and the PoC #5 feedback form
(``docs/poc/p5_beachhead/FEEDBACK_FORM.md`` Friction #5 + "What would make
me a paying user" #3): external testers had no way to discover registered
assets without reading source files. This command closes that gap by
listing every ``@nucleus.asset`` and ``@nucleus.check`` entry, with
materialization status pulled from the Iceberg catalog.

Architecture refs: ``docs/specs/nucleus_architecture_v4.1.md`` §8 L4 (CLI delegates
business logic to coordination/SDK layers), §6.4 (Error Translation — user
output must never contain Dagster / DuckDB / pyiceberg class names).

Stability tier (ADR-005 §2): **Beta @ v0.2 → Stable @ v0.5 → Frozen @ v1.0**.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from nucleus.errors import NucleusError, NucleusInvalidAssetDefinition

# Typer sub-application — mounted by ``cli/main.py`` via
# ``app.add_typer(_list_app, name="list")``.  ``invoke_without_command=True``
# on the callback below makes ``nucleus list`` invoke the listing logic
# directly (no required subcommand) per the single-callback pattern in the
# Typer docs.
# Docs: https://typer.tiangolo.com/tutorial/commands/callback/
app = typer.Typer(
    no_args_is_help=False,
    rich_markup_mode="rich",
    add_completion=False,
)


def _exit_list_error(err: NucleusError, code: int = 1) -> None:
    """Render a NucleusError to stderr per ``docs/specs/nucleus_cli_spec.md`` §5.4.

    Mirrors ``cli/main.py:_exit_nucleus_error`` so error rendering is
    visually identical across every command.  UX audit Rec #3 (2026-05-15):
    bracket-prefix the NE-code so users can grep ``NE3004`` directly.
    """
    code_tag = getattr(err, "error_code", "") or "NE3001"
    typer.echo(f"Error [{code_tag}]: {err.user_message}", err=True)
    if err.fix_hint:
        typer.echo(f"Fix:   {err.fix_hint}", err=True)
    typer.echo(f"Docs:  {err.docs_url}", err=True)
    raise typer.Exit(code=code)


def _truncate(text: str | None, limit: int = 60) -> str:
    """First non-empty line of ``text``, truncated to ``limit`` chars."""
    if not text:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped if len(stripped) <= limit else stripped[: limit - 1] + "\u2026"
    return ""


def _relative_time(then_ms: int | None) -> str:
    """Render ``then_ms`` (epoch milliseconds) as a coarse relative phrase."""
    if then_ms is None:
        return "-"
    now_ms = datetime.now(UTC).timestamp() * 1000.0
    delta_s = max(0.0, (now_ms - then_ms) / 1000.0)
    if delta_s < 60:
        return f"{int(delta_s)}s ago"
    if delta_s < 3600:
        return f"{int(delta_s // 60)}m ago"
    if delta_s < 86400:
        return f"{int(delta_s // 3600)}h ago"
    return f"{int(delta_s // 86400)}d ago"


def _catalog_materialization_index(warehouse_dir: Path) -> dict[str, int]:
    """Return ``{asset_key: snapshot_timestamp_ms}`` for every catalog table.

    Returns ``{}`` when the catalog has not been initialized yet (e.g. the
    user has not run ``nucleus up`` or any ``nucleus run`` yet — no
    warehouse on disk).  All pyiceberg failures are routed through
    :func:`nucleus.coordination.error_translation.translate` so the public
    output never carries pyiceberg or DuckDB class names per v4.1 §6.4.

    Docs: https://py.iceberg.apache.org/api/ (pyiceberg==0.11.1)
    """
    if not warehouse_dir.is_dir() or not (warehouse_dir / "catalog.db").exists():
        return {}
    from nucleus.cli.main import _open_iceberg_catalog
    from nucleus.coordination.error_translation import translate

    index: dict[str, int] = {}
    try:
        catalog = _open_iceberg_catalog(warehouse_dir)
        for ns_tuple in catalog.list_namespaces():
            ns = ns_tuple[0] if ns_tuple else ""
            if not ns:
                continue
            for ident in catalog.list_tables(ns):
                key = f"{ident[0]}.{ident[-1]}"
                snap = catalog.load_table(ident).current_snapshot()
                if snap is not None:
                    index[key] = int(getattr(snap, "timestamp_ms", 0))
    except NucleusError:
        raise
    except Exception as exc:
        raise translate(exc) from exc
    return index


def _collect_rows(namespace: str | None, mat_index: dict[str, int]) -> list[dict[str, Any]]:
    """Walk the in-process asset + check registries; return list-row dicts.

    Filtered by ``namespace`` when given (``key.startswith(f"{namespace}.")``).
    """
    from nucleus.sdk.decorators import _ASSETS, _CHECKS

    rows: list[dict[str, Any]] = []
    for key in sorted(_ASSETS):
        if namespace and not key.startswith(f"{namespace}."):
            continue
        defn = _ASSETS[key]
        snap_ts = mat_index.get(key)
        rows.append(
            {
                "key": key,
                "type": "asset",
                "namespace": key.split(".", 1)[0],
                "materialized": snap_ts is not None,
                "last_materialized_ms": snap_ts,
                "last_materialized_relative": _relative_time(snap_ts),
                "description": _truncate(getattr(defn.fn, "__doc__", None)),
            }
        )
    for asset_key, check_list in sorted(_CHECKS.items()):
        if namespace and not asset_key.startswith(f"{namespace}."):
            continue
        rows.extend(
            {
                "key": asset_key,
                "type": "check",
                "namespace": asset_key.split(".", 1)[0],
                "materialized": False,
                "last_materialized_ms": None,
                "last_materialized_relative": "-",
                "description": _truncate(getattr(check.fn, "__doc__", None)),
            }
            for check in check_list
        )
    return rows


def _render_text(rows: list[dict[str, Any]], namespace: str | None) -> None:
    """Render ``rows`` as a Rich table on stdout."""
    # Docs: https://rich.readthedocs.io/en/stable/tables.html
    from rich.console import Console
    from rich.table import Table

    console = Console(file=sys.stdout, soft_wrap=False)
    if not rows:
        if namespace:
            console.print(
                f"[dim]No assets registered in namespace '{namespace}'.\n"
                "Check the spelling or drop --namespace to see every asset.[/dim]"
            )
        else:
            console.print(
                "[dim]No assets found. "
                "Add @nucleus.asset(...) to a file under assets/, "
                "or run `nucleus init <project>` to scaffold one.[/dim]"
            )
        return
    title = (
        f"Registered assets in '{namespace}' ({len(rows)})"
        if namespace
        else f"Registered assets ({len(rows)})"
    )
    table = Table(title=title, show_lines=False)
    table.add_column("asset key", no_wrap=True)
    table.add_column("type", no_wrap=True)
    table.add_column("materialized", no_wrap=True)
    table.add_column("last materialized", no_wrap=True)
    table.add_column("description")
    for r in rows:
        table.add_row(
            r["key"],
            r["type"],
            "yes" if r["materialized"] else "no",
            r["last_materialized_relative"],
            r["description"],
        )
    console.print(table)


@app.callback(invoke_without_command=True)
def list_assets(
    namespace: Annotated[
        str | None,
        typer.Option(
            "--namespace",
            "-n",
            help="Filter to assets whose key starts with ``<namespace>.``.",
        ),
    ] = None,
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
    """List registered assets in the current project with materialization status.

    Imports the project's ``assets/`` package so every ``@nucleus.asset`` and
    ``@nucleus.check`` registers, opens the Iceberg catalog (read-only) to
    check which assets have a committed snapshot, and renders one row per
    registry entry.

    Per [bold]docs/specs/nucleus_cli_spec.md §3[/bold]. Closes
    PoC #5 Checkpoint 7 (docs/poc/p5_beachhead/FEEDBACK_FORM.md Friction #5).

    [bold]Examples[/bold]

        nucleus list
        nucleus list --namespace raw
        nucleus list --format json
        nucleus list --format jsonl | jq .
    """
    try:
        # UX audit Rec #8 (2026-05-15): accept ``jsonl`` as a synonym of ``json``.
        if format_ not in {"text", "json", "jsonl"}:
            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported for `nucleus list`.",
                fix_hint=(
                    "Pass --format text (default), --format json (NDJSON), "
                    "or --format jsonl (alias)."
                ),
            )
        is_json = format_ in {"json", "jsonl"}

        # Lazy imports keep `nucleus list --help` boot cheap per PoC #4 budget.
        from nucleus.cli.main import (
            _import_assets_package,
            _load_project_config,
            _locate_project_config,
            _resolve_warehouse_dir,
        )

        config_path = _locate_project_config()
        config = _load_project_config(config_path)
        project_root = config_path.parent
        warehouse_dir = _resolve_warehouse_dir(config, project_root)
        _import_assets_package(project_root)

        mat_index = _catalog_materialization_index(warehouse_dir)
        rows = _collect_rows(namespace, mat_index)

        if is_json:
            # Bypass Rich for NDJSON to avoid soft-wrapping single-line payloads.
            for r in rows:
                payload = {**r, "_schema_version": 1}
                sys.stdout.write(json.dumps(payload, default=str) + "\n")
            return

        _render_text(rows, namespace)
    except NucleusError as err:
        _exit_list_error(err)
