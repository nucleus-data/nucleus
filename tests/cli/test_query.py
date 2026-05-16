# ruff: noqa: ARG002
"""Tests for ``nucleus query`` — docs/specs/nucleus_cli_spec.md §3.6.

Exercises the SQL-against-warehouse CLI surface end-to-end:

- happy path: ingest first → query the materialized table → exit 0 + rows
- SQL syntax error → ``NucleusSQLSyntaxError`` (NE2002, no DuckDB classnames)
- ``--format json`` → NDJSON output (one row per line)
- ``--format csv`` → CSV with header row
- ``--limit N`` → emit at most N rows (truncation footer noted)
- ``--file`` → deferred to v0.3+
- ``--asset`` → deferred to v0.3+
- no project → ``NucleusInvalidAssetDefinition`` ``nucleus init`` fix-hint
- Jinja ``{{ ref('namespace.table') }}`` → resolved against catalog views

The ``project_with_data`` fixture is taken as a method argument purely
for its chdir / registry-reset / ingest-setup side effects; the file-level
ARG002 noqa above silences ruff's "unused argument" warning.

Docs:
- Typer testing: https://typer.tiangolo.com/tutorial/testing/
- DuckDB Python API: https://duckdb.org/docs/api/python/dbapi
- pyiceberg load_catalog: https://py.iceberg.apache.org/api/catalog/
"""

from __future__ import annotations

import csv as csv_mod
import io
import json
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
    """Create a tiny ``users`` SQLite source so ingest has something to read."""
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
def project_with_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Fresh project + ingested ``raw.users`` table; tear down sys.path on exit."""
    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["init", "demo"])
    assert init_result.exit_code == 0, f"init failed: {init_result.stdout}"
    project_root = tmp_path / "demo"
    monkeypatch.chdir(project_root)
    _reset_registry_for_tests()
    project_str = str(project_root.resolve())
    sys.path.insert(0, project_str)
    sys.modules.pop("assets", None)
    sys.modules.pop("assets.example", None)
    _populate_sqlite(project_root / "source.db", rows=3)
    ingest_result = runner.invoke(
        app,
        ["ingest", "sqlite:///source.db", "--table", "users", "--as", "raw.users"],
    )
    assert ingest_result.exit_code == 0, (
        f"ingest setup failed: {ingest_result.stdout} | {ingest_result.stderr}"
    )
    try:
        yield project_root
    finally:
        if project_str in sys.path:
            sys.path.remove(project_str)
        sys.modules.pop("assets", None)
        sys.modules.pop("assets.example", None)
        _reset_registry_for_tests()


class TestHappyPath:
    """Plain SELECT against an Iceberg-backed table renders a Rich table."""

    def test_exit_code_zero(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM raw.users"])
        assert result.exit_code == 0, f"unexpected: {result.stdout} | {result.stderr}"

    def test_output_contains_columns(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM raw.users"])
        assert "id" in result.stdout
        assert "name" in result.stdout

    def test_output_contains_rows(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM raw.users"])
        assert "user1" in result.stdout
        assert "user2" in result.stdout
        assert "user3" in result.stdout

    def test_no_forbidden_classnames(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM raw.users"])
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in result.stdout, f"leaked {term!r}: {result.stdout}"


class TestFormats:
    """``--format json`` / ``--format csv`` honour the NDJSON / CSV contract."""

    def test_json_outputs_ndjson(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM raw.users", "--format", "json"])
        assert result.exit_code == 0
        lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
        assert len(lines) == 3
        for line in lines:
            payload = json.loads(line)
            assert "_schema_version" in payload
            assert "id" in payload
            assert "name" in payload

    def test_csv_outputs_header_and_rows(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM raw.users", "--format", "csv"])
        assert result.exit_code == 0
        reader = csv_mod.reader(io.StringIO(result.stdout))
        rows = list(reader)
        assert rows[0] == ["id", "name"]
        assert len(rows) == 4  # header + 3 data rows


class TestLimit:
    """``--limit N`` controls how many rows are rendered."""

    def test_limit_truncates_text_output(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM raw.users", "--limit", "2"])
        assert result.exit_code == 0
        # "user3" should be excluded (3rd row)
        assert "user1" in result.stdout
        assert "user3" not in result.stdout

    def test_limit_truncates_json_output(self, project_with_data: Path) -> None:
        result = runner.invoke(
            app, ["query", "SELECT * FROM raw.users", "--format", "json", "--limit", "2"]
        )
        assert result.exit_code == 0
        lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
        assert len(lines) == 2


class TestJinja:
    """``{{ ref('schema.name') }}`` resolves against the registered catalog."""

    def test_jinja_ref_resolves(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM {{ ref('raw.users') }}"])
        assert result.exit_code == 0, f"unexpected: {result.stderr}"
        assert "user1" in result.stdout


class TestErrorPaths:
    """Validation + scope errors map to the right NucleusError subclass."""

    def test_sql_syntax_error(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELEC * FROM raw.users"])
        assert result.exit_code == 1
        assert "syntax" in result.stderr.lower()

    def test_sql_syntax_error_no_duckdb_leak(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELEC * FROM raw.users"])
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in result.stderr, f"leaked {term!r}: {result.stderr}"

    def test_file_flag_deferred(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "--file", "q.sql"])
        assert result.exit_code == 1
        assert "deferred to v0.3+" in result.stderr

    def test_asset_flag_deferred(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "--asset", "raw.users"])
        assert result.exit_code == 1
        assert "deferred to v0.3+" in result.stderr

    def test_no_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["query", "SELECT 1"])
        assert result.exit_code == 1
        assert "nucleus init" in result.stderr

    def test_invalid_format(self, project_with_data: Path) -> None:
        result = runner.invoke(app, ["query", "SELECT * FROM raw.users", "--format", "xml"])
        assert result.exit_code == 1
        assert "format" in result.stderr.lower()
