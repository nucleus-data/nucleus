"""Tests for ``nucleus snapshot`` CLI commands (ADR-028).

Architecture refs:
    nucleus_architecture_v4.1.md §6.3 (coordination layer)
    ADR-028 (Iceberg branch + tag CLI verbs)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from nucleus.cli.commands.snapshot import snapshot_app
from nucleus.errors import (
    NucleusBranchAlreadyExistsError,
    NucleusCatalogError,
    NucleusSnapshotNotFoundError,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_table(refs: dict | None = None, snapshot_id: int = 42) -> MagicMock:
    """Build a minimal mock pyiceberg Table for testing."""
    table = MagicMock()
    snap = MagicMock()
    snap.snapshot_id = snapshot_id
    table.current_snapshot.return_value = snap
    table.refs.return_value = refs or {}

    mgr = MagicMock()
    mgr.create_branch.return_value = mgr
    mgr.create_tag.return_value = mgr
    mgr.remove_branch.return_value = mgr
    mgr.remove_tag.return_value = mgr
    table.manage_snapshots.return_value = mgr
    return table


def _patch_open(table: MagicMock) -> patch:
    return patch(
        "nucleus.cli.commands.snapshot._open_ice_table",
        return_value=(Path("/fake"), table),
    )


# ---------------------------------------------------------------------------
# nucleus snapshot branch create — happy path
# ---------------------------------------------------------------------------


def test_branch_create_happy() -> None:
    """branch create calls manage_snapshots().create_branch().commit()."""
    table = _make_table()
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["branch", "create", "raw.users", "audit-2026"])
    assert result.exit_code == 0, result.output
    assert "audit-2026" in result.output
    table.manage_snapshots().create_branch.assert_called_once()


# ---------------------------------------------------------------------------
# nucleus snapshot branch create — branch already exists
# ---------------------------------------------------------------------------


def test_branch_create_already_exists() -> None:
    """branch create raises NucleusBranchAlreadyExistsError when ref already present."""
    from pyiceberg.table.refs import SnapshotRef, SnapshotRefType

    existing_ref = SnapshotRef(snapshot_id=42, snapshot_ref_type=SnapshotRefType.BRANCH)
    table = _make_table(refs={"audit-2026": existing_ref})
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["branch", "create", "raw.users", "audit-2026"])
    assert result.exit_code != 0 or "Error:" in result.output
    table.manage_snapshots().create_branch.assert_not_called()


# ---------------------------------------------------------------------------
# nucleus snapshot branch delete — happy path
# ---------------------------------------------------------------------------


def test_branch_delete_happy() -> None:
    """branch delete calls manage_snapshots().remove_branch().commit()."""
    from pyiceberg.table.refs import SnapshotRef, SnapshotRefType

    existing_ref = SnapshotRef(snapshot_id=42, snapshot_ref_type=SnapshotRefType.BRANCH)
    table = _make_table(refs={"audit-2026": existing_ref})
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["branch", "delete", "raw.users", "audit-2026"])
    assert result.exit_code == 0, result.output
    table.manage_snapshots().remove_branch.assert_called_once_with("audit-2026")


# ---------------------------------------------------------------------------
# nucleus snapshot branch delete — branch not found
# ---------------------------------------------------------------------------


def test_branch_delete_not_found() -> None:
    """branch delete raises NucleusSnapshotNotFoundError when branch is absent."""
    table = _make_table(refs={})
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["branch", "delete", "raw.users", "nonexistent"])
    assert result.exit_code != 0 or "Error:" in result.output
    table.manage_snapshots().remove_branch.assert_not_called()


# ---------------------------------------------------------------------------
# nucleus snapshot tag create — happy path
# ---------------------------------------------------------------------------


def test_tag_create_happy() -> None:
    """tag create calls manage_snapshots().create_tag().commit()."""
    table = _make_table()
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["tag", "create", "raw.users", "eom-2026-04"])
    assert result.exit_code == 0, result.output
    assert "eom-2026-04" in result.output
    table.manage_snapshots().create_tag.assert_called_once()


# ---------------------------------------------------------------------------
# nucleus snapshot tag delete — happy path
# ---------------------------------------------------------------------------


def test_tag_delete_happy() -> None:
    """tag delete calls manage_snapshots().remove_tag().commit()."""
    from pyiceberg.table.refs import SnapshotRef, SnapshotRefType

    existing_ref = SnapshotRef(snapshot_id=42, snapshot_ref_type=SnapshotRefType.TAG)
    table = _make_table(refs={"eom-2026-04": existing_ref})
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["tag", "delete", "raw.users", "eom-2026-04"])
    assert result.exit_code == 0, result.output
    table.manage_snapshots().remove_tag.assert_called_once_with("eom-2026-04")


# ---------------------------------------------------------------------------
# nucleus snapshot list — text output
# ---------------------------------------------------------------------------


def test_snapshot_list_text() -> None:
    """snapshot list shows branches and tags in text format."""
    from pyiceberg.table.refs import SnapshotRef, SnapshotRefType

    refs = {
        "audit": SnapshotRef(snapshot_id=42, snapshot_ref_type=SnapshotRefType.BRANCH),
        "eom-q1": SnapshotRef(snapshot_id=99, snapshot_ref_type=SnapshotRefType.TAG),
    }
    table = _make_table(refs=refs)
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["list", "raw.users"])
    assert result.exit_code == 0, result.output
    assert "audit" in result.output
    assert "eom-q1" in result.output
    assert "Branches" in result.output
    assert "Tags" in result.output


# ---------------------------------------------------------------------------
# nucleus snapshot list — json output
# ---------------------------------------------------------------------------


def test_snapshot_list_json() -> None:
    """snapshot list --format json emits valid JSON array."""
    import json

    from pyiceberg.table.refs import SnapshotRef, SnapshotRefType

    refs = {
        "main": SnapshotRef(snapshot_id=1, snapshot_ref_type=SnapshotRefType.BRANCH),
    }
    table = _make_table(refs=refs)
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["list", "raw.users", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload[0]["name"] == "main"
    assert payload[0]["type"] == "branch"


# ---------------------------------------------------------------------------
# Error translation: pyiceberg exception → NucleusError (no classname leaks)
# ---------------------------------------------------------------------------


def test_error_translation_no_classname_leak() -> None:
    """pyiceberg exceptions must not surface in user-facing output."""
    with patch(
        "nucleus.cli.commands.snapshot._open_ice_table",
        side_effect=NucleusCatalogError(
            user_message="Could not load asset catalog.",
            fix_hint="Run nucleus up first.",
        ),
    ):
        result = runner.invoke(snapshot_app, ["list", "raw.broken"])
    assert "pyiceberg" not in result.output.lower()
    assert "Could not load asset" in result.output


# ---------------------------------------------------------------------------
# snapshot list — no refs (empty output is valid)
# ---------------------------------------------------------------------------


def test_snapshot_list_empty() -> None:
    """snapshot list with no refs shows (none) for both groups."""
    table = _make_table(refs={})
    with _patch_open(table):
        result = runner.invoke(snapshot_app, ["list", "raw.users"])
    assert result.exit_code == 0, result.output
    assert "(none)" in result.output
