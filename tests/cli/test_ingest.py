# ruff: noqa: ARG002
"""Tests for ``nucleus ingest`` — docs/specs/nucleus_cli_spec.md §3.5.

Exercises the SQLite → Iceberg ingest CLI surface end-to-end:

- happy path: SQLite source + ``--as namespace.table`` → exit 0 + preview
- non-sqlite scheme (``postgresql://``) → dispatches to Postgres ingest (ADR-014, Stage 1)
- missing ``--as`` arg → Typer usage error (exit 2)
- invalid ``--as`` (no dot) → ``NucleusInvalidAssetDefinition`` (NE3004)
- ``--mode overwrite`` / ``--mode merge`` → deferred to v0.3+
- missing ``--table`` → ``NucleusInvalidAssetDefinition``
- no project → ``NucleusInvalidAssetDefinition`` ``nucleus init`` fix-hint
- output never leaks a Dagster / DuckDB / Polars / pyiceberg classname

The ``project`` fixture is taken as a method argument purely for its
chdir / registry-reset side effects; the file-level ARG002 noqa above
silences ruff's "unused argument" warning across every test method.

Docs:
- Typer testing: https://typer.tiangolo.com/tutorial/testing/
- sqlite3 (stdlib): https://docs.python.org/3/library/sqlite3.html
"""

from __future__ import annotations

import sqlite3
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nucleus.cli.main import app
from nucleus.sdk.decorators import _reset_registry_for_tests

_FORBIDDEN_CLASSNAMES = (
    "DagsterInstance",
    "OpExecutionContext",
    "DuckDBPyConnection",
    "Traceback (most recent call last)",
    "dagster._",
    "duckdb._",
    "polars._",
    "pyiceberg._",
)

runner = CliRunner(mix_stderr=False)


def _populate_sqlite(db_path: Path, rows: int = 3) -> None:
    """Create a tiny ``users`` table with ``rows`` rows for ingest tests."""
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE users (id INTEGER NOT NULL, name TEXT)")
        for i in range(1, rows + 1):
            conn.execute("INSERT INTO users VALUES (?, ?)", (i, f"user{i}"))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Scaffold a fresh project + chdir into it; tear down sys.path on exit."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "demo"])
    assert result.exit_code == 0, f"init failed: {result.stdout}"
    project_root = tmp_path / "demo"
    monkeypatch.chdir(project_root)
    _reset_registry_for_tests()
    project_str = str(project_root.resolve())
    sys.path.insert(0, project_str)
    sys.modules.pop("assets", None)
    sys.modules.pop("assets.example", None)
    try:
        yield project_root
    finally:
        if project_str in sys.path:
            sys.path.remove(project_str)
        sys.modules.pop("assets", None)
        sys.modules.pop("assets.example", None)
        _reset_registry_for_tests()


class TestHappyPath:
    """SQLite → Iceberg ingest with ``--mode append`` (the v0.1 default)."""

    def test_exit_code_zero(self, project: Path) -> None:
        _populate_sqlite(project / "source.db", rows=3)
        result = runner.invoke(
            app, ["ingest", "sqlite:///source.db", "--table", "users", "--as", "raw.users"]
        )
        assert result.exit_code == 0, f"unexpected: {result.stdout} | {result.stderr}"

    def test_summary_contains_row_count(self, project: Path) -> None:
        _populate_sqlite(project / "source.db", rows=3)
        result = runner.invoke(
            app, ["ingest", "sqlite:///source.db", "--table", "users", "--as", "raw.users"]
        )
        assert "3" in result.stdout
        assert "raw.users" in result.stdout

    def test_preview_contains_columns(self, project: Path) -> None:
        _populate_sqlite(project / "source.db", rows=3)
        result = runner.invoke(
            app, ["ingest", "sqlite:///source.db", "--table", "users", "--as", "raw.users"]
        )
        assert "id" in result.stdout
        assert "name" in result.stdout

    def test_no_forbidden_classnames(self, project: Path) -> None:
        _populate_sqlite(project / "source.db", rows=2)
        result = runner.invoke(
            app, ["ingest", "sqlite:///source.db", "--table", "users", "--as", "raw.users"]
        )
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in result.stdout, f"leaked {term!r}: {result.stdout}"


class TestErrorPaths:
    """Validation + scope errors map to the right NucleusError subclass."""

    def test_postgres_connection_error_surfaced_cleanly(self, project: Path) -> None:
        """Unreachable Postgres server → NucleusError exit 1; no internal classnames.

        postgresql:// is now dispatched (ADR-014 Stage 1) — it is no longer
        deferred to v0.3+. An unreachable server should raise NucleusSourceConnectionError
        or NucleusInternalError with a clean user-facing message.
        """
        result = runner.invoke(
            app,
            [
                "ingest",
                "postgresql://u:p@badhost.invalid/db",
                "--table",
                "users",
                "--as",
                "raw.users",
            ],
        )
        assert result.exit_code == 1
        # Must not leak internal library classnames per AGENTS.md §11.7
        for forbidden in ("psycopg2", "PipelineStepFailed", "sqlalchemy.exc", "ModuleNotFound"):
            assert forbidden not in result.stderr, f"leaked {forbidden!r}: {result.stderr}"

    def test_csv_uri_deferred(self, project: Path) -> None:
        result = runner.invoke(app, ["ingest", "csv://orders.csv", "--as", "raw.orders"])
        assert result.exit_code == 1
        assert "deferred to v0.3+" in result.stderr

    def test_missing_as_flag(self, project: Path) -> None:
        # When --as defaults to "" + no other validation passes, the body
        # rejects the empty string with NucleusInvalidAssetDefinition.
        result = runner.invoke(app, ["ingest", "sqlite:///source.db", "--table", "users"])
        assert result.exit_code == 1
        assert "namespace" in result.stderr.lower()

    def test_invalid_dest_format_no_dot(self, project: Path) -> None:
        result = runner.invoke(
            app, ["ingest", "sqlite:///x.db", "--table", "users", "--as", "nodot"]
        )
        assert result.exit_code == 1
        assert "namespace" in result.stderr.lower()

    def test_invalid_dest_format_too_many_dots(self, project: Path) -> None:
        result = runner.invoke(
            app, ["ingest", "sqlite:///x.db", "--table", "users", "--as", "a.b.c"]
        )
        assert result.exit_code == 1
        assert "namespace" in result.stderr.lower()

    def test_mode_overwrite_deferred(self, project: Path) -> None:
        result = runner.invoke(
            app,
            [
                "ingest",
                "sqlite:///source.db",
                "--table",
                "users",
                "--as",
                "raw.users",
                "--mode",
                "overwrite",
            ],
        )
        assert result.exit_code == 1
        assert "deferred to v0.3+" in result.stderr

    def test_mode_merge_deferred(self, project: Path) -> None:
        result = runner.invoke(
            app,
            [
                "ingest",
                "sqlite:///source.db",
                "--table",
                "users",
                "--as",
                "raw.users",
                "--mode",
                "merge",
            ],
        )
        assert result.exit_code == 1
        assert "deferred to v0.3+" in result.stderr

    def test_missing_table_flag(self, project: Path) -> None:
        result = runner.invoke(app, ["ingest", "sqlite:///source.db", "--as", "raw.users"])
        assert result.exit_code == 1
        assert "--table" in result.stderr

    def test_no_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            app, ["ingest", "sqlite:///x.db", "--table", "users", "--as", "raw.users"]
        )
        assert result.exit_code == 1
        assert "nucleus init" in result.stderr

    def test_merge_on_without_merge_mode(self, project: Path) -> None:
        result = runner.invoke(
            app,
            [
                "ingest",
                "sqlite:///source.db",
                "--table",
                "users",
                "--as",
                "raw.users",
                "--merge-on",
                "id",
            ],
        )
        assert result.exit_code == 1
        assert "deferred to v0.3+" in result.stderr
