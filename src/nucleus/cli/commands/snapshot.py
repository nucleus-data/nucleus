"""``nucleus snapshot`` CLI — Iceberg branch + tag management (ADR-028).

Exposes pyiceberg's ``table.manage_snapshots()`` API via three subcommand groups:

    nucleus snapshot branch create <asset> <branch-name> [options]
    nucleus snapshot branch delete <asset> <branch-name>
    nucleus snapshot tag    create <asset> <tag-name>    [options]
    nucleus snapshot tag    delete <asset> <tag-name>
    nucleus snapshot list   <asset>

Architecture refs:
    nucleus_architecture_v4.1.md §6.3 (coordination layer)
    nucleus_architecture_v4.1.md §13 (CLI surface)
    ADR-028 (Iceberg branch + tag CLI verbs)

Docs (AGENTS.md §11.12):
    pyiceberg manage_snapshots: https://py.iceberg.apache.org/api/#snapshot-management
    pyiceberg Table.refs: https://py.iceberg.apache.org/api/#pyiceberg.table.Table.refs

Important limitation (ADR-028 §Context):
    ``table.append(branch=...)`` is NOT supported in PyIceberg 0.11.1.
    Branch-targeted writes require Spark/Flink or Lakekeeper catalog.
    Full WAP (write-audit-publish) deferred to v0.3. These commands manage
    snapshot references only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from nucleus.errors import (
    NucleusAssetNotMaterialized,
    NucleusBranchAlreadyExistsError,
    NucleusCatalogError,
    NucleusError,
    NucleusSnapshotNotFoundError,
)

snapshot_app = typer.Typer(
    name="snapshot",
    help=(
        "Manage Iceberg snapshot references (branches + tags) on your assets. "
        "[bold]Note[/bold]: write-audit-publish (branch-targeted writes) requires "
        "Lakekeeper catalog — available at v0.3. These commands manage snapshot "
        "references only."
    ),
    no_args_is_help=True,
)

branch_app = typer.Typer(
    name="branch",
    help="Create or delete snapshot branches on an asset.",
    no_args_is_help=True,
)

tag_app = typer.Typer(
    name="tag",
    help="Create or delete snapshot tags on an asset.",
    no_args_is_help=True,
)

snapshot_app.add_typer(branch_app, name="branch")
snapshot_app.add_typer(tag_app, name="tag")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _exit_err(err: NucleusError, code: int = 1) -> None:
    typer.echo(f"Error: {err.user_message}", err=True)
    if err.fix_hint:
        typer.echo(f"Fix:   {err.fix_hint}", err=True)
    typer.echo(f"Docs:  {err.docs_url}", err=True)
    raise typer.Exit(code=code)


def _open_ice_table(asset_key: str, project_root: Path | None = None) -> tuple[Path, object]:
    """Locate the project, open the catalog, load the Iceberg table for *asset_key*.

    Returns ``(project_root, ice_table)`` on success.
    Raises a ``NucleusError`` subclass on failure (no pyiceberg classnames exposed).

    Docs: https://py.iceberg.apache.org/api/catalog/  (pyiceberg==0.11.1)
    """
    from pyiceberg.catalog import load_catalog

    from nucleus.coordination.error_translation import translate

    if project_root is None:
        from nucleus.cli.main import _locate_project_config, _load_project_config, _resolve_warehouse_dir

        config_path = _locate_project_config()
        config = _load_project_config(config_path)
        project_root = config_path.parent
        warehouse_dir = _resolve_warehouse_dir(config, project_root)
    else:
        warehouse_dir = project_root / "data" / "warehouse"

    catalog_db = warehouse_dir / "catalog.db"
    try:
        catalog = load_catalog(
            "default",
            type="sql",
            uri=f"sqlite:///{catalog_db.resolve().as_posix()}",
            warehouse=f"file://{warehouse_dir.resolve().as_posix()}",
        )
    except Exception as exc:
        raise translate(exc) from exc

    if "." not in asset_key or asset_key.count(".") != 1:
        raise NucleusCatalogError(
            user_message=f"Asset key {asset_key!r} must be in '<namespace>.<name>' form.",
            fix_hint="Pass a two-part key, e.g. `raw.users`.",
        )
    namespace, name = asset_key.split(".", 1)
    try:
        ice_table = catalog.load_table((namespace, name))
    except Exception as exc:
        translated = translate(exc)
        raise translated from exc

    return project_root, ice_table


def _resolve_snapshot_id(ice_table: object, snapshot_id: int | None) -> int:
    """Return *snapshot_id* or the current snapshot id; raise if table has no snapshot."""
    if snapshot_id is not None:
        return snapshot_id
    snap = ice_table.current_snapshot()  # type: ignore[union-attr]
    if snap is None:
        raise NucleusAssetNotMaterialized(
            user_message="This asset has no materialized snapshot to create a branch/tag from.",
            fix_hint="Run `nucleus run <asset-key>` first to produce a snapshot.",
        )
    return int(snap.snapshot_id)


# ---------------------------------------------------------------------------
# nucleus snapshot branch create
# ---------------------------------------------------------------------------


@branch_app.command(name="create")
def branch_create(
    asset: Annotated[str, typer.Argument(help="Asset key, e.g. ``raw.users``.")],
    branch_name: Annotated[str, typer.Argument(help="Name for the new branch.")],
    snapshot_id: Annotated[
        int | None,
        typer.Option("--snapshot-id", help="Snapshot ID to anchor the branch. Defaults to current snapshot."),
    ] = None,
    max_ref_age_ms: Annotated[
        int | None,
        typer.Option("--max-ref-age-ms", help="Maximum reference age in milliseconds before expiry."),
    ] = None,
    min_snapshots_to_keep: Annotated[
        int | None,
        typer.Option("--min-snapshots-to-keep", help="Minimum number of snapshots to retain on this branch."),
    ] = None,
) -> None:
    """Create a snapshot branch on an Iceberg asset.

    Per [bold]ADR-028[/bold]. Wraps ``table.manage_snapshots().create_branch(...).commit()``.
    Docs: https://py.iceberg.apache.org/api/#snapshot-management

    [bold]Note[/bold]: write-audit-publish (branch-targeted writes) requires Lakekeeper
    catalog — deferred to v0.3. This command creates the branch reference only.

    [bold]Examples[/bold]

        nucleus snapshot branch create raw.users audit-2026-05
        nucleus snapshot branch create raw.users dev --snapshot-id 8823671234
        nucleus snapshot branch create raw.users compliance --max-ref-age-ms 604800000
    """
    try:
        _, ice_table = _open_ice_table(asset)
        snap_id = _resolve_snapshot_id(ice_table, snapshot_id)

        # Check for pre-existing branch to surface NucleusBranchAlreadyExistsError.
        refs = ice_table.refs()  # type: ignore[union-attr]
        if branch_name in refs:
            raise NucleusBranchAlreadyExistsError(
                user_message=f"A branch or tag named '{branch_name}' already exists on asset '{asset}'.",
                fix_hint=(
                    f"Delete it first with `nucleus snapshot branch delete {asset} {branch_name}` "
                    "or choose a different name."
                ),
            )

        from nucleus.coordination.error_translation import translate

        try:
            mgr = ice_table.manage_snapshots()  # type: ignore[union-attr]
            mgr = mgr.create_branch(
                snap_id,
                branch_name,
                max_ref_age_ms=max_ref_age_ms,
                min_snapshots_to_keep=min_snapshots_to_keep,
            )
            mgr.commit()
        except NucleusError:
            raise
        except Exception as exc:
            raise translate(exc) from exc

        typer.echo(f"Branch '{branch_name}' created on asset '{asset}' (snapshot {snap_id}).")
    except NucleusError as err:
        _exit_err(err)


# ---------------------------------------------------------------------------
# nucleus snapshot branch delete
# ---------------------------------------------------------------------------


@branch_app.command(name="delete")
def branch_delete(
    asset: Annotated[str, typer.Argument(help="Asset key, e.g. ``raw.users``.")],
    branch_name: Annotated[str, typer.Argument(help="Name of the branch to delete.")],
) -> None:
    """Delete a snapshot branch from an Iceberg asset.

    Per [bold]ADR-028[/bold]. Wraps ``table.manage_snapshots().remove_branch(...).commit()``.
    Docs: https://py.iceberg.apache.org/api/#snapshot-management

    [bold]Examples[/bold]

        nucleus snapshot branch delete raw.users audit-2026-05
    """
    try:
        _, ice_table = _open_ice_table(asset)

        from pyiceberg.table.refs import SnapshotRefType

        from nucleus.coordination.error_translation import translate

        refs = ice_table.refs()  # type: ignore[union-attr]
        ref = refs.get(branch_name)
        if ref is None or ref.snapshot_ref_type != SnapshotRefType.BRANCH:
            raise NucleusSnapshotNotFoundError(
                user_message=f"Branch '{branch_name}' does not exist on asset '{asset}'.",
                fix_hint=f"Use `nucleus snapshot list {asset}` to see available branches.",
            )

        try:
            ice_table.manage_snapshots().remove_branch(branch_name).commit()  # type: ignore[union-attr]
        except NucleusError:
            raise
        except Exception as exc:
            raise translate(exc) from exc

        typer.echo(f"Branch '{branch_name}' deleted from asset '{asset}'.")
    except NucleusError as err:
        _exit_err(err)


# ---------------------------------------------------------------------------
# nucleus snapshot tag create
# ---------------------------------------------------------------------------


@tag_app.command(name="create")
def tag_create(
    asset: Annotated[str, typer.Argument(help="Asset key, e.g. ``raw.users``.")],
    tag_name: Annotated[str, typer.Argument(help="Name for the new tag.")],
    snapshot_id: Annotated[
        int | None,
        typer.Option("--snapshot-id", help="Snapshot ID to tag. Defaults to current snapshot."),
    ] = None,
    max_ref_age_ms: Annotated[
        int | None,
        typer.Option("--max-ref-age-ms", help="Maximum reference age in milliseconds before expiry."),
    ] = None,
) -> None:
    """Create a snapshot tag on an Iceberg asset.

    Tags are immutable named pointers to a specific snapshot — useful for
    compliance archiving (EOW/EOM snapshots) and reproducible analysis.

    Per [bold]ADR-028[/bold]. Wraps ``table.manage_snapshots().create_tag(...).commit()``.
    Docs: https://py.iceberg.apache.org/api/#snapshot-management

    [bold]Examples[/bold]

        nucleus snapshot tag create raw.users eom-2026-04
        nucleus snapshot tag create raw.users baseline --snapshot-id 8823671234
        nucleus snapshot tag create raw.users quarterly --max-ref-age-ms 7776000000
    """
    try:
        _, ice_table = _open_ice_table(asset)
        snap_id = _resolve_snapshot_id(ice_table, snapshot_id)

        refs = ice_table.refs()  # type: ignore[union-attr]
        if tag_name in refs:
            raise NucleusBranchAlreadyExistsError(
                user_message=f"A branch or tag named '{tag_name}' already exists on asset '{asset}'.",
                fix_hint=(
                    f"Delete it first with `nucleus snapshot tag delete {asset} {tag_name}` "
                    "or choose a different name."
                ),
            )

        from nucleus.coordination.error_translation import translate

        try:
            ice_table.manage_snapshots().create_tag(snap_id, tag_name, max_ref_age_ms=max_ref_age_ms).commit()  # type: ignore[union-attr]
        except NucleusError:
            raise
        except Exception as exc:
            raise translate(exc) from exc

        typer.echo(f"Tag '{tag_name}' created on asset '{asset}' (snapshot {snap_id}).")
    except NucleusError as err:
        _exit_err(err)


# ---------------------------------------------------------------------------
# nucleus snapshot tag delete
# ---------------------------------------------------------------------------


@tag_app.command(name="delete")
def tag_delete(
    asset: Annotated[str, typer.Argument(help="Asset key, e.g. ``raw.users``.")],
    tag_name: Annotated[str, typer.Argument(help="Name of the tag to delete.")],
) -> None:
    """Delete a snapshot tag from an Iceberg asset.

    Per [bold]ADR-028[/bold]. Wraps ``table.manage_snapshots().remove_tag(...).commit()``.
    Docs: https://py.iceberg.apache.org/api/#snapshot-management

    [bold]Examples[/bold]

        nucleus snapshot tag delete raw.users eom-2026-04
    """
    try:
        _, ice_table = _open_ice_table(asset)

        from pyiceberg.table.refs import SnapshotRefType

        from nucleus.coordination.error_translation import translate

        refs = ice_table.refs()  # type: ignore[union-attr]
        ref = refs.get(tag_name)
        if ref is None or ref.snapshot_ref_type != SnapshotRefType.TAG:
            raise NucleusSnapshotNotFoundError(
                user_message=f"Tag '{tag_name}' does not exist on asset '{asset}'.",
                fix_hint=f"Use `nucleus snapshot list {asset}` to see available tags.",
            )

        try:
            ice_table.manage_snapshots().remove_tag(tag_name).commit()  # type: ignore[union-attr]
        except NucleusError:
            raise
        except Exception as exc:
            raise translate(exc) from exc

        typer.echo(f"Tag '{tag_name}' deleted from asset '{asset}'.")
    except NucleusError as err:
        _exit_err(err)


# ---------------------------------------------------------------------------
# nucleus snapshot list
# ---------------------------------------------------------------------------


@snapshot_app.command(name="list")
def snapshot_list(
    asset: Annotated[str, typer.Argument(help="Asset key, e.g. ``raw.users``.")],
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
    """List all branches and tags for an Iceberg asset.

    Per [bold]ADR-028[/bold]. Reads ``table.refs()`` to enumerate all
    snapshot references.
    Docs: https://py.iceberg.apache.org/api/#pyiceberg.table.Table.refs

    [bold]Examples[/bold]

        nucleus snapshot list raw.users
        nucleus snapshot list raw.users --format json
    """
    try:
        from pyiceberg.table.refs import SnapshotRefType

        _, ice_table = _open_ice_table(asset)
        refs = ice_table.refs()  # type: ignore[union-attr]

        if format_ == "json":
            import json as _json

            payload = [
                {
                    "name": name,
                    "type": ref.snapshot_ref_type.value,
                    "snapshot_id": ref.snapshot_id,
                    "max_ref_age_ms": ref.max_ref_age_ms,
                    "min_snapshots_to_keep": ref.min_snapshots_to_keep,
                }
                for name, ref in sorted(refs.items())
            ]
            typer.echo(_json.dumps(payload, indent=2))
            return

        branches = [(name, ref) for name, ref in sorted(refs.items()) if ref.snapshot_ref_type == SnapshotRefType.BRANCH]
        tags = [(name, ref) for name, ref in sorted(refs.items()) if ref.snapshot_ref_type == SnapshotRefType.TAG]

        typer.echo(f"Asset: {asset}")
        typer.echo("")

        typer.echo(f"Branches ({len(branches)}):")
        if branches:
            for name, ref in branches:
                typer.echo(f"  {name}  (snapshot {ref.snapshot_id})")
        else:
            typer.echo("  (none)")

        typer.echo("")
        typer.echo(f"Tags ({len(tags)}):")
        if tags:
            for name, ref in tags:
                typer.echo(f"  {name}  (snapshot {ref.snapshot_id})")
        else:
            typer.echo("  (none)")

    except NucleusError as err:
        _exit_err(err)
