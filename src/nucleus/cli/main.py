"""Nucleus CLI — main entry point.

This module exposes the Typer ``app`` that ``pyproject.toml`` wires as the
``nucleus`` console script.  Each command is a thin operator wrapper over one
``ctx.*`` call; per docs/specs/nucleus_architecture_v4.1.md §8 L4 the CLI delegates all
business logic to the coordination / ctx layers.

Typical invocations::

    nucleus --version
    nucleus --help
    nucleus init my-stack
    nucleus up
    nucleus run raw.users
    nucleus ingest postgres://u:p@host/db --table public.users --as raw.users
    nucleus query "SELECT * FROM raw.users LIMIT 10"
    nucleus version

See ``docs/specs/nucleus_cli_spec.md`` for the full command surface, flag conventions,
exit-code contract (§8), and stability tier of each command.

Architecture refs: docs/specs/nucleus_architecture_v4.1.md §8 L4 (CLI layer), §6.4
(Error Translation — user-facing strings must never contain Dagster/DuckDB
class names), §5.5.1 (ctx.copy_from for ingest), §5.6 (ctx.sql for query).
"""

from __future__ import annotations

import importlib
import re
import sys
import time
from datetime import date
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from importlib.resources import files as _resource_files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Annotated, Any, NoReturn
from urllib.parse import urlparse

import typer
import yaml  # type: ignore[import-untyped]  # PyYAML ships no py.typed marker as of 6.0.

from nucleus import __version__
from nucleus.cli._compose import (
    compose_service_names,
    detect_compose_runner,
    minio_console_url,
    minio_health_base_url,
    project_compose_file,
    run_compose,
    should_poll_minio_ready,
    translate_compose_process_failure,
)
from nucleus.errors import (
    NucleusConfigError,
    NucleusError,
    NucleusInternalError,
    NucleusInvalidAssetDefinition,
    NucleusIOError,
    NucleusTimeoutError,
)

# NEEDS VERIFICATION: NucleusNotImplementedError is absent from nucleus.errors
# (confirmed 2026-05-13 against src/nucleus/errors.py — no such class defined).
# Per task instructions, NucleusInternalError is used as the closest available
# class for all stub commands. Replace when NucleusNotImplementedError is added
# per docs/specs/nucleus_cli_spec.md §10 NV #4 and ADR-006 §Initial L4 allocations.

# The Typer app — this is the symbol ``pyproject.toml`` references as
#   nucleus = "nucleus.cli.main:app"  # noqa: ERA001 — example, not commented-out code.
# Docs: https://typer.tiangolo.com/
app = typer.Typer(
    name="nucleus",
    help=(
        "Nucleus — ship data products from a laptop. "
        "Local-first Python SDK + CLI for Iceberg-native pipelines."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,  # NucleusError renders itself; suppress Typer default.
)


# ==============================================================================
# Internal helpers
# ==============================================================================


def _version_callback(value: bool) -> None:
    """Print version and exit when ``--version`` is passed."""
    if value:
        typer.echo(f"nucleus {__version__}")
        raise typer.Exit()


def _exit_nucleus_error(err: NucleusError, code: int = 1) -> NoReturn:
    """Render a NucleusError to stderr per docs/specs/nucleus_cli_spec.md §5.4 and exit.

    Output format (stderr only):

        Error [NE3002]: <user_message>
        Fix:            <fix_hint>       (line omitted when fix_hint is empty)
        Docs:           <docs_url>

    The bracket-prefix NE-code mirrors Databricks ``[ERROR_CONDITION]`` and
    Snowflake ``nnnnnn (sqlstate):`` so DB/SF converts can grep the code
    directly from terminal output (UX audit Rec #3, 2026-05-15).

    Per §12 forbidden patterns: no Typer, Click, Dagster, or DuckDB class names
    may appear in this output — only user-language strings from NucleusError.
    """
    code_tag = getattr(err, "error_code", "") or "NE3001"
    typer.echo(f"Error [{code_tag}]: {err.user_message}", err=True)
    if err.fix_hint:
        typer.echo(f"Fix:   {err.fix_hint}", err=True)
    typer.echo(f"Docs:  {err.docs_url}", err=True)
    raise typer.Exit(code=code)


# ==============================================================================
# `nucleus init` helpers (docs/specs/nucleus_cli_spec.md §3.1)
# ==============================================================================
# Per the founder anti-over-engineering directive (.cursor/rules/nucleus.mdc
# 2026-05-13): the init command is intentionally a thin file-copy + str.format
# pass. No Jinja, no shellouts, no interactive prompts. One template ("default").

# Project-name pattern: alphanumeric + hyphen + underscore, 1-64 chars.
# Cited by NucleusInvalidAssetDefinition.fix_hint when validation fails.
_PROJECT_NAME_RE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Bundled template keys. v0.1 ships only "default" (alias of v01); per
# docs/specs/nucleus_cli_spec.md §3.1 the spec lists minimal/postgres/csv as future
# variants — those are deferred until empirical user demand justifies the
# branching cost (founder directive 2026-05-13: no speculative code).
_TEMPLATE_KEYS: dict[str, str] = {"default": "v01"}

# Template files are stored under src/nucleus/templates/v01/ with
# dot-prefix-free names so editable + wheel installs both ship them.
# At scaffold time these are renamed to their canonical destinations.
_TEMPLATE_NAME_RENAMES: dict[str, str] = {
    "gitignore": ".gitignore",
    "gitkeep": ".gitkeep",
}


def _validate_project_name(name: str | None) -> str:
    """Validate ``name`` against ``_PROJECT_NAME_RE``; raise on miss.

    Raises ``NucleusInvalidAssetDefinition`` (NE3004) with a fix_hint that
    cites the exact rule the user violated.
    """
    if name is None or not isinstance(name, str) or not name.strip():
        raise NucleusInvalidAssetDefinition(
            user_message="A project name is required for `nucleus init`.",
            fix_hint=(
                "Pass a name as the first argument, e.g. `nucleus init my-stack`. "
                "Names must be 1-64 characters of letters, digits, '-' or '_'."
            ),
        )
    cleaned = name.strip()
    if not _PROJECT_NAME_RE.match(cleaned):
        raise NucleusInvalidAssetDefinition(
            user_message=f"Project name {cleaned!r} is not a valid identifier.",
            fix_hint=(
                "Use 1-64 characters from [A-Za-z0-9_-] only. "
                "Examples: 'my-stack', 'demo_project', 'team42'."
            ),
        )
    return cleaned


def _resolve_template_root(template: str) -> Traversable:
    """Look up the bundled template subdirectory for ``template``.

    Uses ``importlib.resources.files`` so editable + wheel installs both work.
    Docs: https://docs.python.org/3/library/importlib.resources.html
    """
    if template not in _TEMPLATE_KEYS:
        raise NucleusInvalidAssetDefinition(
            user_message=f"Template {template!r} is not bundled with this Nucleus version.",
            fix_hint=(
                f"v0.1 ships exactly one template: {sorted(_TEMPLATE_KEYS)}. "
                "Drop the `--template` flag (the default works) or pass `--template default`."
            ),
        )
    return _resource_files("nucleus.templates").joinpath(_TEMPLATE_KEYS[template])


def _ensure_target_writable(target: Path) -> None:
    """Verify ``target`` either does not exist or is an empty directory.

    Translates non-empty / file-collision cases to ``NucleusIOError`` (NE1005).
    """
    if not target.exists():
        return
    if target.is_file():
        raise NucleusIOError(
            user_message=f"A file already exists at {target} — cannot scaffold a project there.",
            fix_hint="Remove the existing file or choose a different project name.",
        )
    try:
        if any(target.iterdir()):
            raise NucleusIOError(
                user_message=f"Directory {target} already exists and is not empty.",
                fix_hint="Remove the existing directory or choose a different name.",
            )
    except OSError as exc:
        raise NucleusIOError(
            user_message=f"Cannot inspect target directory {target}: {exc}",
            fix_hint="Verify directory permissions and try again.",
            cause=exc,
        ) from exc


def _scaffold_from_template(
    template_root: Traversable,
    target: Path,
    project_name: str,
    today: str,
) -> list[Path]:
    """Walk ``template_root`` recursively; render + write files into ``target``.

    Returns the list of created files (relative to ``target``) for the
    success message. Translates filesystem failures to ``NucleusIOError``.
    """
    created: list[Path] = []
    try:
        target.mkdir(parents=True, exist_ok=True)
        _copy_traversable(template_root, target, project_name, today, created)
    except OSError as exc:
        raise NucleusIOError(
            user_message=f"Failed to scaffold project at {target}: {exc}",
            fix_hint="Verify the parent directory is writable and disk space is available.",
            cause=exc,
        ) from exc
    return created


def _copy_traversable(
    src: Traversable,
    dest: Path,
    project_name: str,
    today: str,
    created: list[Path],
) -> None:
    """Recursive helper for ``_scaffold_from_template``.

    Skips Python bytecode artefacts (``__pycache__/``, ``*.pyc``) that may
    leak into the installed ``templates/v01/`` tree if anyone runs
    ``compileall`` against the package — see the 2026-05-14 entry in
    ``docs/internal/research/ai_hallucinations.md`` for the original detection.
    Bytecode files would otherwise blow up the ``read_text(encoding="utf-8")``
    call below with a ``UnicodeDecodeError``.
    """
    for child in src.iterdir():
        if child.name == "__pycache__" or child.name.endswith((".pyc", ".pyo")):
            continue
        out_name = _TEMPLATE_NAME_RENAMES.get(child.name, child.name)
        out_path = dest / out_name
        if child.is_dir():
            out_path.mkdir(parents=True, exist_ok=True)
            _copy_traversable(child, out_path, project_name, today, created)
            continue
        content = child.read_text(encoding="utf-8")
        rendered = content.format(project_name=project_name, today=today)
        out_path.write_text(rendered, encoding="utf-8")
        created.append(out_path)


# ==============================================================================
# Data-plane helpers (run / ingest / query)
# ==============================================================================
# Per docs/specs/nucleus_cli_spec.md §3.4-§3.6 + §7. Every data-plane command needs to
# (a) locate the user's project, (b) read its YAML config, and (c) import
# the project's assets/ package so @nucleus.asset decorators register before
# materialize / query touches the registry. Helpers stay private so the
# CLI surface contract per ADR-005 §4 is unchanged.


def _locate_project_config(start: Path | None = None) -> Path:
    """Walk up to 3 levels from ``start`` looking for ``nucleus_project.yaml``.

    Raises ``NucleusInvalidAssetDefinition`` when no config is found — the
    fix_hint tells the user to run ``nucleus init`` or cd into a project.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents)[:4]:
        config = candidate / "nucleus_project.yaml"
        if config.is_file():
            return config
    raise NucleusInvalidAssetDefinition(
        user_message="No `nucleus_project.yaml` found in the current directory or its parents.",
        fix_hint=(
            "Run `nucleus init <name>` first or cd into a Nucleus project. "
            "The project root is the directory containing `nucleus_project.yaml`."
        ),
    )


def _load_project_config(config_path: Path) -> dict[str, Any]:
    """Parse the project YAML; return the top-level mapping.

    Translates filesystem / parse errors to ``NucleusIOError`` per v4.1 §6.4.
    """
    # Docs: https://pyyaml.org/wiki/PyYAMLDocumentation
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise NucleusIOError(
            user_message=f"Cannot read project config at {config_path}: {exc}",
            fix_hint="Verify the file exists and is readable by the current user.",
            cause=exc,
        ) from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise NucleusIOError(
            user_message=f"Project config at {config_path} is not valid YAML: {exc}",
            fix_hint="Re-generate the file with `nucleus init` or fix the syntax by hand.",
            cause=exc,
        ) from exc
    if not isinstance(data, dict):
        raise NucleusIOError(
            user_message=f"Project config at {config_path} must be a YAML mapping at the top level.",
            fix_hint="Re-generate the file with `nucleus init`.",
        )
    return data


def _resolve_warehouse_dir(config: dict[str, Any], project_root: Path) -> Path:
    """Extract ``storage.warehouse`` from the config; resolve relative to project root."""
    storage = config.get("storage")
    raw = storage.get("warehouse") if isinstance(storage, dict) else None
    if not isinstance(raw, str) or not raw:
        raise NucleusInvalidAssetDefinition(
            user_message="Project config is missing `storage.warehouse`.",
            fix_hint="Add `storage:\\n  warehouse: ./data/warehouse` to nucleus_project.yaml.",
        )
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else (project_root / candidate).resolve()


def _import_assets_package(project_root: Path) -> None:
    """Add ``project_root`` to ``sys.path`` and import its ``assets`` subpackage.

    Side-effect: every ``@nucleus.asset`` and ``@nucleus.check`` body inside
    the package registers in the in-process registry. No-op if the project
    has no ``assets/`` directory yet (decorator-less projects are valid).
    """
    assets_dir = project_root / "assets"
    if not assets_dir.is_dir():
        return
    project_str = str(project_root.resolve())
    added = project_str not in sys.path
    if added:
        sys.path.insert(0, project_str)
    try:
        importlib.invalidate_caches()
        package = importlib.import_module("assets")
        for child in sorted(assets_dir.iterdir()):
            if child.suffix == ".py" and child.name not in {"__init__.py"}:
                importlib.import_module(f"assets.{child.stem}")
        _ = package
    except NucleusError:
        raise
    except Exception as exc:
        raise NucleusInvalidAssetDefinition(
            user_message=f"Failed to load assets package at {assets_dir}: {exc}",
            fix_hint="Check assets/*.py for import errors. Run `python -c 'import assets'` from the project root.",
            cause=exc,
        ) from exc


def _open_iceberg_catalog(warehouse_dir: Path) -> Any:
    """Open the filesystem-backed Iceberg catalog rooted at ``warehouse_dir``.

    Mirrors the Windows-safe URI form used in ``nucleus.ctx.copy_from._open_catalog``
    so the CLI can re-open the same catalog the helper just wrote to.
    Docs: https://py.iceberg.apache.org/api/catalog/  (pyiceberg==0.11.1)
    """
    from pyiceberg.catalog import load_catalog

    from nucleus.coordination.error_translation import translate

    warehouse_dir.mkdir(parents=True, exist_ok=True)
    catalog_db = warehouse_dir / "catalog.db"
    try:
        return load_catalog(
            "default",
            type="sql",
            uri=f"sqlite:///{catalog_db.resolve().as_posix()}",
            warehouse=f"file://{warehouse_dir.resolve().as_posix()}",
        )
    except Exception as exc:
        raise translate(exc) from exc


def _scan_iceberg_preview(
    warehouse_dir: Path, namespace: str, table_name: str
) -> tuple[str, list[str], list[tuple[Any, ...]]]:
    """Re-open the catalog after ingest; return ``(snapshot_id, columns, rows[:10])``."""
    from nucleus.coordination.error_translation import translate

    catalog = _open_iceberg_catalog(warehouse_dir)
    try:
        ice_table = catalog.load_table((namespace, table_name))
        snapshot = ice_table.current_snapshot()
        snapshot_id = str(snapshot.snapshot_id) if snapshot is not None else ""
        arrow = ice_table.scan(limit=10).to_arrow()
    except Exception as exc:
        raise translate(exc) from exc
    columns = [str(name) for name in arrow.column_names]
    rows = [tuple(row[col] for col in columns) for row in arrow.to_pylist()]
    return snapshot_id, columns, rows


_LIMIT_RE = re.compile(r"\blimit\b", re.IGNORECASE)
_REF_RE = re.compile(r"\{\{\s*(?:ref|source)\s*\(", re.IGNORECASE)


def _register_catalog_in_duckdb(catalog: Any, conn: Any) -> dict[str, str]:
    """Register every catalog table as a DuckDB view; return ``{asset_key: view}`` map."""
    refs: dict[str, str] = {}
    for ns_tuple in catalog.list_namespaces():
        ns = ns_tuple[0] if ns_tuple else ""
        if not ns:
            continue
        conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{ns}"')
        for ident in catalog.list_tables(ns):
            tbl = ident[-1]
            ice_table = catalog.load_table(ident)
            arrow_t = ice_table.scan().to_arrow()
            arrow_view = f"_arrow_{ns}_{tbl}"
            conn.register(arrow_view, arrow_t)
            conn.execute(f'CREATE OR REPLACE VIEW "{ns}"."{tbl}" AS SELECT * FROM "{arrow_view}"')
            refs[f"{ns}.{tbl}"] = f'"{ns}"."{tbl}"'
    return refs


def _execute_sql(
    sql: str, warehouse_dir: Path, limit: int
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """Run ``sql`` against the warehouse; return ``(columns, rows)``."""
    # Docs: https://duckdb.org/docs/api/python/dbapi  (duckdb==1.1.3)
    import duckdb

    from nucleus.coordination.error_translation import translate
    from nucleus.coordination.sql_resolver import resolve_sql

    conn = duckdb.connect(":memory:")
    try:
        # Catalog open + DuckDB-view registration both call pyiceberg internals
        # (load_catalog / load_table) which can raise pydantic.ValidationError
        # on corrupt *.metadata.json — chaos J8 / CF-2.  Wrap in translate() so
        # those leaks become NucleusCatalogError (NE1007) per CF-3 handler.
        # Docs: https://py.iceberg.apache.org/api/  (pyiceberg==0.11.1)
        try:
            catalog = _open_iceberg_catalog(warehouse_dir)
            refs = _register_catalog_in_duckdb(catalog, conn)
        except NucleusError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary; translate() routes typed errors.
            raise translate(exc) from exc
        if _REF_RE.search(sql):

            def _resolver(name: str) -> str:
                if name in refs:
                    return refs[name]
                raise KeyError(name)

            sql, _ = resolve_sql(sql, _resolver, available=refs.keys())
        if not _LIMIT_RE.search(sql):
            sql = f"{sql.rstrip().rstrip(';').rstrip()} LIMIT {limit}"
        try:
            cursor = conn.execute(sql)
        except Exception as exc:
            raise translate(exc) from exc
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = [tuple(r) for r in cursor.fetchall()]
        return columns, rows
    finally:
        conn.close()


# ==============================================================================
# `nucleus up` / `nucleus down` helpers (docs/specs/nucleus_cli_spec.md §3.2 - §3.3)
# ==============================================================================
# Wrap ``docker compose`` / ``docker-compose`` via nucleus.cli._compose (stdlib
# subprocess — no docker-py). MinIO readiness uses pinned httpx (lazy import —
# docs: https://www.python-httpx.org/quickstart/).
# Compose reference: https://docs.docker.com/compose/reference/

_MINIO_READY_PATH = "/minio/health/ready"


def _wait_local_storage_ready(
    http_ready_url: str,
    *,
    deadline_s: float = 30.0,
    poll_interval_s: float = 0.5,
) -> None:
    """Poll GET ``http_ready_url`` until HTTP 2xx or ``deadline_s`` elapses."""

    import httpx  # pinned in pyproject.toml — https://www.python-httpx.org/quickstart/

    elapsed = 0.0
    while elapsed < deadline_s:
        try:
            response = httpx.get(http_ready_url, timeout=1.0)
            if 200 <= response.status_code < 300:
                return
        except httpx.TimeoutException:
            pass
        except httpx.RequestError:
            pass
        time.sleep(poll_interval_s)
        elapsed += poll_interval_s
    raise NucleusTimeoutError(
        user_message=(f"Local storage did not report ready within {int(deadline_s)} seconds."),
        fix_hint=(
            "Check `docker compose ps` from your project root, verify host ports "
            "in docker-compose.yaml are free, and inspect container logs before "
            "retrying `nucleus up`."
        ),
    )


def _rows_for_runtime_table(compose_file: Path) -> list[tuple[str, str]]:
    """Build service / endpoint tuples for Rich output after ``nucleus up``."""

    svc = compose_service_names(compose_file)
    rows: list[tuple[str, str]] = []
    if should_poll_minio_ready(compose_file, svc):
        base_api = minio_health_base_url(compose_file).rstrip("/")
        rows.append(("minio (S3 API)", base_api))
        rows.append(("minio (console)", minio_console_url(compose_file).rstrip("/")))
    for name in sorted(svc):
        if name.lower() == "minio":
            continue
        rows.append((name, "(see docker-compose.yaml)"))
    return rows


# ==============================================================================
# Root callback — global flags (docs/specs/nucleus_cli_spec.md §6)
# ==============================================================================


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Nucleus operator CLI. Run ``nucleus --help`` for available commands."""
    _ = version  # placate ruff ARG001; version flag is handled by its callback


# ==============================================================================
# v0.1 commands — docs/specs/nucleus_cli_spec.md §3
# ==============================================================================


@app.command()
def init(
    project_name: Annotated[
        str | None,
        typer.Argument(
            help="Name of the new project directory to create (1-64 chars; letters, digits, '-', '_').",
        ),
    ] = None,
    template: Annotated[
        str,
        typer.Option(
            "--template",
            help="Project template. v0.1 ships only [bold]default[/bold].",
        ),
    ] = "default",
    no_git: Annotated[
        bool,
        typer.Option(
            "--no-git",
            help="Skip the post-scaffold `git init` suggestion.",
        ),
    ] = False,
) -> None:
    """Scaffold a new Nucleus project.

    Creates ``nucleus_project.yaml``, ``assets/``, ``data/`` and a runnable
    example asset under ``<project_name>/``. Pure file-copy + ``str.format``
    interpolation — no engines, no shellouts, no network.

    Per [bold]docs/specs/nucleus_cli_spec.md §3.1[/bold]. Wraps stdlib
    ``importlib.resources`` for the template copy. ``--no-git`` suppresses
    the post-scaffold `git init` suggestion (the suggestion is print-only;
    Nucleus never shells out to git).

    [bold]Examples[/bold]

        nucleus init my-data-stack
        nucleus init demo --template default
        nucleus init demo --no-git
    """
    try:
        validated_name = _validate_project_name(project_name)
        template_root = _resolve_template_root(template)
        target = Path.cwd() / validated_name
        _ensure_target_writable(target)
        today = date.today().isoformat()
        created = _scaffold_from_template(template_root, target, validated_name, today)
    except NucleusError as err:
        _exit_nucleus_error(err)

    typer.echo(f"Created Nucleus project at {target} ({len(created)} files).")
    typer.echo("")
    typer.echo("Next steps:")
    typer.echo(f"  cd {validated_name}")
    typer.echo("  nucleus up")
    typer.echo("  nucleus run example.greeting")
    if not no_git:
        typer.echo("")
        typer.echo("Optional: initialize git via `git init` inside the new directory.")
    typer.echo("")
    typer.echo("Quickstart: https://nucleus.dev/quickstart")


@app.command()
def up(
    rebuild: Annotated[
        bool,
        typer.Option(
            "--rebuild",
            help="Tear down any running stack and rebuild from scratch.",
        ),
    ] = False,
    catalog: Annotated[
        str,
        typer.Option(
            "--catalog",
            envvar="NUCLEUS_CATALOG",
            help="Catalog backend type. Only [bold]filesystem[/bold] supported in v0.1.",
        ),
    ] = "filesystem",
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            "-p",
            envvar="NUCLEUS_PROFILE",
            help="Configuration profile to load from ``nucleus_project.yaml``.",
        ),
    ] = "default",
) -> None:
    """Boot the local Nucleus runtime (warehouse, catalog, and Compose stack).

    Creates the warehouse folder and SQLite catalog file under the project root,
    then runs ``docker compose up -d`` (or legacy ``docker-compose``) against
    ``docker-compose.yaml`` bundled by ``nucleus init``. When MinIO is declared,
    waits up to thirty seconds for the HTTP readiness probe to return success.

    Per [bold]docs/specs/nucleus_cli_spec.md §3.2[/bold]. References:
    https://docs.docker.com/compose/reference/ ·
    https://min.io/docs/minio/linux/operations/monitoring/healthcheck-probe.html

    [bold]Examples[/bold]

        nucleus up
        nucleus up --rebuild
    """
    try:
        if catalog != "filesystem":
            raise NucleusInvalidAssetDefinition(
                user_message=f"--catalog {catalog!r} is not supported in v0.1.",
                fix_hint=(
                    "v0.1 supports only `--catalog filesystem`. "
                    "REST catalogs (lakekeeper / polaris) land in v0.3+."
                ),
            )
        if profile != "default":
            raise NucleusInternalError(
                user_message=f"--profile {profile!r} is not supported in v0.1.",
                fix_hint="Profiles ship in v0.3+. v0.1 always uses the `default` profile.",
                docs_url="https://nucleus.dev/errors/not-implemented",
            )

        config_path = _locate_project_config()
        config = _load_project_config(config_path)
        project_root = config_path.parent
        warehouse_dir = _resolve_warehouse_dir(config, project_root)

        try:
            warehouse_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise NucleusIOError(
                user_message=f"Cannot create warehouse directory at {warehouse_dir}: {exc}",
                fix_hint="Verify the parent directory is writable by the current user.",
                cause=exc,
            ) from exc

        catalog_db = warehouse_dir / "catalog.db"
        try:
            catalog_db.touch(exist_ok=True)
        except OSError as exc:
            raise NucleusIOError(
                user_message=f"Cannot create catalog file at {catalog_db}: {exc}",
                fix_hint="Verify the warehouse directory is writable.",
                cause=exc,
            ) from exc

        compose_file = project_compose_file(project_root)
        if not compose_file.is_file():
            raise NucleusConfigError(
                user_message="No `docker-compose.yaml` next to nucleus_project.yaml.",
                fix_hint=(
                    "Create a fresh project via `nucleus init <name>` (recommended) "
                    "or restore `docker-compose.yaml` beside your config file."
                ),
            )

        runner = detect_compose_runner()

        if rebuild:
            down_res = run_compose(runner, project_root, compose_file, ["down", "-v"])
            if down_res.returncode != 0:
                raise translate_compose_process_failure(down_res)

        up_res = run_compose(runner, project_root, compose_file, ["up", "-d"])
        if up_res.returncode != 0:
            raise translate_compose_process_failure(up_res)

        names = compose_service_names(compose_file)
        if should_poll_minio_ready(compose_file, names):
            base = minio_health_base_url(compose_file).rstrip("/")
            _wait_local_storage_ready(base + _MINIO_READY_PATH)

        # Generate nucleus.db BI handshake (ADR-026) after storage is ready.
        # Non-fatal: if the catalog has no materialised assets yet (first boot)
        # the file is still created (empty metadata table); errors are warnings.
        try:
            catalog_instance = _open_iceberg_catalog(warehouse_dir)
            from nucleus.coordination.bi_handshake import generate_nucleus_db

            nucleus_db_path = generate_nucleus_db(project_root, catalog_instance)
        except Exception as _bi_exc:  # noqa: BLE001
            # BI handshake is best-effort at boot time — never block nucleus up.
            nucleus_db_path = project_root / "nucleus.db"
            import logging as _logging

            _logging.getLogger(__name__).warning("nucleus.db generation skipped: %s", _bi_exc)

        typer.echo(f"Warehouse: {warehouse_dir}")
        typer.echo(f"Catalog:   filesystem (SQLite at {catalog_db})")
        typer.echo(f"BI file:   {nucleus_db_path} (connect with DuckDB: open('{nucleus_db_path}'))")

        from nucleus.cli.rendering import render_runtime_endpoint_table

        rows = _rows_for_runtime_table(compose_file)
        if rows:
            render_runtime_endpoint_table(rows)

        typer.echo("")
        typer.echo("Nucleus up.")
    except NucleusError as err:
        _exit_nucleus_error(err)


@app.command()
def down(
    volumes: Annotated[
        bool,
        typer.Option(
            "--volumes",
            help=("Remove Compose-managed anonymous volumes (default preserves them)."),
        ),
    ] = False,
) -> None:
    """Stop the Compose stack shipped with this project.

    Runs ``docker compose down`` in the project root. Host paths such as your
    Iceberg warehouse under ``data/`` always remain untouched; `--volumes`
    deletes only anonymous volumes Compose created during ``up``.

    Per [bold]docs/specs/nucleus_cli_spec.md §3.3[/bold].

    [bold]Examples[/bold]

        nucleus down
        nucleus down --volumes
    """
    try:
        config_path = _locate_project_config()
        project_root = config_path.parent
        compose_file = project_compose_file(project_root)

        if not compose_file.is_file():
            raise NucleusConfigError(
                user_message="No docker-compose.yaml in this project — nothing to tear down.",
                fix_hint=(
                    "Copy `docker-compose.yaml` beside `nucleus_project.yaml` or run "
                    "`nucleus init <name>` in a fresh directory."
                ),
            )

        runner = detect_compose_runner()
        down_args = ["down"]
        if volumes:
            down_args.append("-v")

        proc = run_compose(runner, project_root, compose_file, down_args)
        if proc.returncode != 0:
            raise translate_compose_process_failure(proc)

        state = (
            "Docker volumes tied to this stack were removed."
            if volumes
            else "Docker volumes preserved (warehouse files on disk always remain)."
        )
        typer.echo(state)
        typer.echo("")
        typer.echo("Nucleus down.")
    except NucleusError as err:
        _exit_nucleus_error(err)


@app.command()
def run(
    asset_keys: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                "Asset key(s) to materialize, e.g. ``raw.users staging.users``. "
                "Use ``--all`` to materialize the full asset graph."
            ),
        ),
    ] = None,
    all_assets: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Materialize every asset in the project (full asset graph).",
        ),
    ] = False,
    changed_only: Annotated[
        bool,
        typer.Option(
            "--changed-only",
            help="Materialize only assets whose upstream changed since the last snapshot.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show which assets would materialize without executing them.",
        ),
    ] = False,
    param: Annotated[
        list[str] | None,
        typer.Option(
            "--param",
            help="Asset parameter override as KEY=VAL. Repeatable.",
        ),
    ] = None,
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
    """Materialize one or more assets and commit Iceberg snapshots.

    Executes each asset body, validates the schema contract, commits an Iceberg
    snapshot atomically, and emits an OpenLineage event. Equivalent to calling
    ``nucleus.materialize(...)`` from Python (per ADR-013).

    Per [bold]docs/specs/nucleus_cli_spec.md §3.4[/bold]. Wraps the Asset Materialization
    Adapter (v4.1 §6.2). All orchestrator internals are hidden from user output.

    [bold]Examples[/bold]

        nucleus run example.greeting
        nucleus run --dry-run raw.users
        nucleus run raw.users --format json
    """
    try:
        if all_assets or changed_only:
            flag = "--all" if all_assets else "--changed-only"
            raise NucleusInternalError(
                user_message=f"'nucleus run {flag}' is deferred to v0.2+.",
                fix_hint="Pass a single asset key, e.g. `nucleus run example.greeting`.",
                docs_url="https://nucleus.dev/errors/not-implemented",
            )
        if param:
            raise NucleusInternalError(
                user_message="'nucleus run --param' is deferred to v0.3+.",
                fix_hint="Hardcode parameters in the asset body for v0.1.",
                docs_url="https://nucleus.dev/errors/not-implemented",
            )
        keys = asset_keys or []
        if len(keys) != 1:
            raise NucleusInternalError(
                user_message=(
                    f"v0.1 supports a single asset per invocation; got {len(keys)} asset key(s)."
                ),
                fix_hint="Run one asset at a time, e.g. `nucleus run example.greeting`.",
                docs_url="https://nucleus.dev/errors/not-implemented",
            )
        # UX audit Rec #8 (2026-05-15): accept ``jsonl`` as a synonym of ``json``
        # — `nucleus run --format json` already emits NDJSON; ``jsonl`` matches
        # jq ecosystem convention so pipelines `nucleus run x --format jsonl | jq .`
        # signal NDJSON-ness up front. Normalised to ``"json"`` before being
        # passed to the renderer so render code stays single-branch.
        if format_ not in {"text", "json", "jsonl"}:
            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported for `nucleus run`.",
                fix_hint="Pass --format text (default), --format json (NDJSON), or --format jsonl (alias).",
            )
        if format_ == "jsonl":
            format_ = "json"
        asset_key = keys[0]
        config_path = _locate_project_config()
        config = _load_project_config(config_path)
        warehouse_dir = _resolve_warehouse_dir(config, config_path.parent)
        _import_assets_package(config_path.parent)
        # Route through the AMA to access dry_run; nucleus.materialize() does
        # not surface dry_run in v0.1 (no founder-approved SDK addition yet).
        # Layer rule: cli → coordination is downward and explicitly allowed
        # by scripts/check_layering.py per docs/conventions/engineering.md §3.1.
        # warehouse_dir is required for the real Iceberg commit path (v4.1 §6.2
        # step 3 — AMA owns the data-write, not Dagster's IO manager).
        from nucleus.coordination.asset_materialization import materialize_asset

        result = materialize_asset(asset_key, dry_run=dry_run, warehouse_dir=warehouse_dir)
        from nucleus.cli.rendering import render_materialization_result

        # mypy: format_ narrowed by the membership check above.
        fmt: Any = format_
        render_materialization_result(
            result,
            status="dry-run" if dry_run else "success",
            format_=fmt,
        )
    except NucleusError as err:
        _exit_nucleus_error(err)


@app.command()
def ingest(
    source_uri: Annotated[
        str,
        typer.Argument(
            help=(
                "Source URI: ``postgresql://``, ``mysql://``, ``sqlite://``, "
                "or a local path to CSV / Parquet / JSON."
            ),
        ),
    ],
    dest: Annotated[
        str,
        typer.Option(
            "--as",
            help=(
                "Destination asset key in ``<namespace>.<name>`` form "
                "(e.g. ``raw.users``). Required."
            ),
        ),
    ] = "",
    table: Annotated[
        str | None,
        typer.Option(
            "--table",
            help="Source table name within a database (required for DB sources).",
        ),
    ] = None,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            help="Write mode: [bold]append[/bold] (default) or [bold]replace[/bold].",
        ),
    ] = "append",
    merge_on: Annotated[
        list[str] | None,
        typer.Option(
            "--merge-on",
            help="Column(s) to match on for ``--mode merge``. Deferred to v0.3+.",
        ),
    ] = None,
) -> None:
    """Ingest a source into an Iceberg asset — the 30-minute beachhead one-liner.

    Auto-infers schema, auto-creates the destination asset, pulls rows from the
    source, commits atomically, and prints a 10-row preview.

    Per [bold]docs/specs/nucleus_cli_spec.md §3.5[/bold]. Dispatches by URL scheme:
    ``sqlite://`` wraps the built-in copy helper; ``postgresql://`` /
    ``postgres://`` wraps the Stage 1 SQL source (ADR-014, v4.1 §5.5).

    [bold]Supported sources (v0.1)[/bold]: ``sqlite://`` and ``postgresql://``.
    MySQL / CSV / Parquet / JSON land at v0.3+.

    [bold]Examples[/bold]

        nucleus ingest sqlite:///orders.db --table orders --as raw.orders
        nucleus ingest postgresql://user:pass@host/db --table public.orders --as raw.orders
        nucleus ingest postgresql://user:pass@host/db --table orders --as raw.orders --mode replace
    """
    try:
        if merge_on:
            raise NucleusInternalError(
                user_message="`--merge-on` requires `--mode merge`, deferred to v0.3+.",
                fix_hint="Drop --merge-on for v0.1.",
                docs_url="https://nucleus.dev/errors/not-implemented",
            )
        if not dest or "." not in dest or dest.count(".") != 1:
            raise NucleusInvalidAssetDefinition(
                user_message=f"--as must be in '<namespace>.<name>' form; got {dest!r}.",
                fix_hint="Pass `--as raw.users` (a 2-segment v0.1 asset key).",
            )

        parsed = urlparse(source_uri)
        scheme = parsed.scheme.lower()
        namespace, dest_table = dest.split(".", 1)

        # Validate scheme before --table / --mode so unsupported schemes get the right error.
        # Kept aligned with nucleus.ctx._dispatch._SUPPORTED_SCHEMES so the CLI
        # allow-list never lags the dispatcher (ADR-014 §"MySQL parity").
        if scheme not in ("sqlite", "postgresql", "postgres", "mysql", "mysql+pymysql"):
            raise NucleusConfigError(
                user_message=f"Source scheme {scheme!r} is not supported in v0.1.",
                fix_hint=(
                    "Supported sources: sqlite, postgresql, postgres, mysql. "
                    "CSV, Parquet, and JSON sources are deferred to v0.3+."
                ),
            )

        if not table:
            raise NucleusInvalidAssetDefinition(
                user_message="--table is required when ingesting from a database source.",
                fix_hint="Pass `--table <schema.table>` (the table inside the database).",
            )

        # CLI-level --mode validation. The unified ``nucleus.ctx.copy_from``
        # dispatcher also rejects unsupported write_disposition values, but the
        # CLI keeps this check so the user-facing wording ("Merge and upsert
        # modes are deferred to v0.3+") matches docs/specs/nucleus_cli_spec.md §3.5.
        if mode not in {"append", "replace"}:
            raise NucleusConfigError(
                user_message=f"--mode {mode!r} is not supported in v0.1.",
                fix_hint=(
                    "Pass --mode append (default) or --mode replace. "
                    "Merge and upsert modes are deferred to v0.3+."
                ),
            )

        # SQLite branch scope ceiling: ``--mode replace`` is deferred to v0.3+
        # for sqlite sources because the helper does not yet truncate-and-reload.
        # Postgres supports replace via dlt's write_disposition.
        if scheme == "sqlite" and mode == "replace":
            raise NucleusInternalError(
                user_message="--mode replace for sqlite sources is deferred to v0.3+.",
                fix_hint="Use --mode append (the default) for sqlite sources in v0.1.",
                docs_url="https://nucleus.dev/errors/not-implemented",
            )

        config_path = _locate_project_config()
        config = _load_project_config(config_path)
        warehouse_dir = _resolve_warehouse_dir(config, config_path.parent)

        # Delegate to the unified ctx.copy_from dispatcher per
        # docs/specs/nucleus_ctx_sdk_spec.md §0 (Principle 1 — ctx is the only thing users
        # import) + docs/specs/nucleus_architecture_v4.1.md §5.5.1. The dispatcher routes
        # sqlite / postgresql / postgres internally; the CLI no longer
        # re-implements scheme branching here.
        # Lazy import keeps boot-time cost off the hot path per PoC #4 +
        # docs/internal/research/dlt.md §6.
        from nucleus.ctx import copy_from as _copy_from

        rows_written = _copy_from(
            source_uri,
            table=table,
            target=dest,
            warehouse_dir=warehouse_dir,
            write_disposition=mode,
        )

        snapshot_id, preview_columns, preview_rows = _scan_iceberg_preview(
            warehouse_dir, namespace, dest_table
        )
        from nucleus.cli.rendering import render_ingest_summary

        render_ingest_summary(
            asset_key=dest,
            rows_written=rows_written,
            snapshot_id=snapshot_id,
            preview_columns=preview_columns,
            preview_rows=preview_rows,
        )
    except NucleusError as err:
        _exit_nucleus_error(err)


@app.command()
def query(
    sql: Annotated[
        str | None,
        typer.Argument(
            help="SQL string to execute, e.g. ``SELECT * FROM raw.users LIMIT 10``.",
        ),
    ] = None,
    file: Annotated[
        str | None,
        typer.Option(
            "--file",
            help="Path to a ``.sql`` file to execute (alternative to positional SQL).",
        ),
    ] = None,
    asset: Annotated[
        str | None,
        typer.Option(
            "--asset",
            help=("Asset key to query — shorthand for ``SELECT * FROM <key> LIMIT <limit>``."),
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            help="Row limit when using ``--asset`` mode (default: 100).",
        ),
    ] = 100,
    format_: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            envvar="NUCLEUS_FORMAT",
            help="Output format: [bold]text[/bold] | json | csv.",
        ),
    ] = "text",
) -> None:
    """Execute a SQL query against the warehouse via the embedded SQL engine.

    v0.1 input mode: positional SQL string only. ``--file`` and ``--asset``
    are deferred to v0.3+.

    Resolves Jinja ``{{ ref() }}`` references via the native ``ctx.sql``
    resolver (v4.1 §5.6). Results render as a Rich table on TTY; NDJSON with
    ``--format json``; CSV with ``--format csv``.

    Per [bold]docs/specs/nucleus_cli_spec.md §3.6[/bold]. Wraps DuckDB against the
    Iceberg catalog using PyIceberg's Arrow scan (v4.1 §5.6).

    [bold]Examples[/bold]

        nucleus query "SELECT * FROM raw.users LIMIT 10"
        nucleus query "SELECT * FROM raw.users" --format json
    """
    try:
        if file is not None:
            raise NucleusInternalError(
                user_message="`nucleus query --file` is deferred to v0.3+.",
                fix_hint='Pass the SQL as a positional argument: nucleus query "SELECT ...".',
                docs_url="https://nucleus.dev/errors/not-implemented",
            )
        if asset is not None:
            raise NucleusInternalError(
                user_message="`nucleus query --asset` is deferred to v0.3+.",
                fix_hint='Use a SQL string instead: nucleus query "SELECT * FROM <asset>".',
                docs_url="https://nucleus.dev/errors/not-implemented",
            )
        # UX audit Rec #8: ``jsonl`` accepted as alias for ``json`` (NDJSON).
        if format_ not in {"text", "json", "jsonl", "csv"}:
            raise NucleusInvalidAssetDefinition(
                user_message=f"--format {format_!r} is not supported.",
                fix_hint=(
                    "Pass --format text (default), --format json (NDJSON), "
                    "--format jsonl (alias), or --format csv."
                ),
            )
        if format_ == "jsonl":
            format_ = "json"
        if not sql or not sql.strip():
            raise NucleusInvalidAssetDefinition(
                user_message="A SQL string is required.",
                fix_hint='Pass the query as the positional argument: nucleus query "SELECT 1".',
            )
        config_path = _locate_project_config()
        config = _load_project_config(config_path)
        warehouse_dir = _resolve_warehouse_dir(config, config_path.parent)
        columns, rows = _execute_sql(sql, warehouse_dir, limit)
        from nucleus.cli.rendering import render_query_rows

        fmt: Any = format_
        render_query_rows(columns, rows, format_=fmt, limit=limit)
    except NucleusError as err:
        _exit_nucleus_error(err)


@app.command()
def version(
    check_updates: Annotated[
        bool,
        typer.Option(
            "--check-updates",
            help=(
                "Query PyPI for available updates — informational only, never "
                "auto-installs. Requires network access."
            ),
        ),
    ] = False,
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
    """Report installed Nucleus version and all pinned dependency versions.

    Lists at minimum: [bold]nucleus / duckdb / polars / pyarrow / pyiceberg /
    dagster[/bold]. Provides per-AGENTS.md Constraint #11 traceability.

    Pass ``--check-updates`` to query PyPI; network failure downgrades to a
    warning (exit 0 preserved).

    Per [bold]docs/specs/nucleus_cli_spec.md §3.7[/bold]. Wraps:
    ``nucleus.__version__`` + ``importlib.metadata.version()``;
    no network unless ``--check-updates``.
    Docs: https://docs.python.org/3/library/importlib.metadata.html
    """
    # Tier 1/2 wrapped dependencies per spec §3.7 + AGENTS.md Constraint #11.
    # Docs: https://docs.python.org/3/library/importlib.metadata.html
    packages: list[tuple[str, str]] = [("nucleus", __version__)]
    for pkg_name in ("duckdb", "polars", "pyarrow", "pyiceberg", "dagster"):
        try:
            pkg_ver = _pkg_version(pkg_name)
        except PackageNotFoundError:
            pkg_ver = "(not installed)"
        packages.append((pkg_name, pkg_ver))

    if format_ == "json":
        import json as _json

        payload = {p: v for p, v in packages}
        payload["_schema_version"] = 1  # type: ignore[assignment]
        typer.echo(_json.dumps(payload))
        return

    col_width = max(len(p) for p, _ in packages)
    header = f"{'package':<{col_width}}  version"
    typer.echo(header)
    typer.echo("-" * len(header))
    for pkg, ver in packages:
        typer.echo(f"{pkg:<{col_width}}  {ver}")

    if check_updates:
        # Deferred: PyPI query not yet implemented in v0.1 skeleton.
        typer.echo(
            "\nNote: --check-updates not yet implemented in v0.1. "
            "Check https://pypi.org/project/nucleus/ manually."
        )


# ==============================================================================
# v0.2 commands — docs/specs/nucleus_cli_spec.md §3.8 (Beta tier, ADR-015)
# ==============================================================================

from nucleus.cli.commands.chat import chat as _chat_cmd
from nucleus.cli.commands.dagit import dagit as _dagit_cmd
from nucleus.cli.commands.list import app as _list_app
from nucleus.cli.commands.runs import runs_app as _runs_app
from nucleus.cli.commands.schedule import schedule_app as _schedule_app
from nucleus.cli.commands.snapshot import snapshot_app as _snapshot_app
from nucleus.workbench.cli import app as _workbench_app

app.command(name="chat", help="Ask the AI Copilot a question about your project (Beta).")(_chat_cmd)

app.command(
    name="dagit",
    help=(
        "[yellow]Power-user mode[/yellow] — launch the embedded orchestrator's "
        "web UI (Dagit). Primary UX is [bold]nucleus workbench[/bold] (ADR-016)."
    ),
)(_dagit_cmd)

# Schedule command group (Beta, ADR-017). All five sub-commands registered;
# on/off/trigger raise NucleusFeatureDeferredError until v0.2 active-scheduling lands.
# Docs: https://typer.tiangolo.com/tutorial/subcommands/add-typer/
app.add_typer(
    _schedule_app,
    name="schedule",
    help=(
        "Inspect asset schedules declared with ``schedule=`` (Beta). "
        "Active scheduling ships in v0.2."
    ),
)

# Runs command group (Beta, ADR-025 §P0-2). Durable NDJSON run ledger.
app.add_typer(
    _runs_app,
    name="runs",
    help=(
        "Inspect asset run history from the durable ledger (Beta, ADR-025). "
        "History persists at ``.nucleus/runs/runs.ndjson``."
    ),
)

# Workbench command group (Beta, ADR-016 Fork B). FastAPI + React SPA / CDN-fallback.
app.add_typer(
    _workbench_app,
    name="workbench",
    help="Launch the Nucleus Workbench browser UI (FastAPI + React, ADR-016).",
)

# Snapshot command group (Beta, ADR-028). Iceberg branch + tag management.
app.add_typer(
    _snapshot_app,
    name="snapshot",
    help=(
        "Manage Iceberg snapshot references (branches + tags) on assets (Beta, ADR-028). "
        "Write-audit-publish branch writes require Lakekeeper — deferred to v0.3."
    ),
)

# `nucleus list` — registered-asset discoverability (PoC #5 Checkpoint 7).
# Mounted as a Typer sub-app so the richer surface in
# ``cli/commands/list.py`` (``--namespace``, ``--format jsonl`` alias,
# materialization status from the Iceberg catalog) replaces the earlier
# inline scaffold. The sub-app uses ``invoke_without_command=True`` so
# ``nucleus list`` runs the listing directly with no sub-command required.
# Docs: https://typer.tiangolo.com/tutorial/subcommands/add-typer/
app.add_typer(
    _list_app,
    name="list",
    help="List registered assets with materialization status (Beta).",
)


if __name__ == "__main__":
    # Enable ``python -m nucleus.cli.main`` for dev convenience.
    app()
