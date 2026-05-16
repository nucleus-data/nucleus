# ruff: noqa: ARG002
"""Tests for ``nucleus run`` — docs/specs/nucleus_cli_spec.md §3.4 + ADR-013.

Exercises the materialize-asset CLI surface end-to-end:

- happy path: scaffolded project + registered asset → exit 0 with status row
- asset not found → ``NucleusAssetNotFound`` (NE3002)
- no project → ``NucleusInvalidAssetDefinition`` with ``nucleus init`` fix-hint
- ``--all`` / ``--changed-only`` → deferred to v0.2+
- ``--param`` → deferred to v0.3+
- ``--dry-run`` → ``status="dry-run"``; exit 0
- ``--format json`` → single NDJSON line on stdout
- multiple positional asset keys → ``NucleusInternalError`` (single-asset constraint)
- output never leaks a Dagster / DuckDB / Polars / pyiceberg classname

The ``project`` fixture is taken as a method argument purely for its
chdir / registry-reset side effects; the file-level ARG002 noqa above
silences ruff's "unused argument" warning across every test method.

Docs:
- Typer testing: https://typer.tiangolo.com/tutorial/testing/
- pytest tmp_path + monkeypatch.chdir: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
"""

from __future__ import annotations

import json
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


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Scaffold a fresh ``nucleus init demo`` project per test, chdir into it.

    Resets the in-process asset registry before and after so the example
    asset registered by `assets.example` is fresh for each test, not reused
    from a previous test's `sys.modules` cache.
    """
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(app, ["init", "demo"])
    assert result.exit_code == 0, f"init failed: {result.stdout}"
    project_root = tmp_path / "demo"
    monkeypatch.chdir(project_root)
    _reset_registry_for_tests()
    project_str = str(project_root.resolve())
    sys.path.insert(0, project_str)
    sys.modules.pop("assets", None)
    sys.modules.pop("assets.example", None)
    sys.modules.pop("assets.__init__", None)
    try:
        yield project_root
    finally:
        if project_str in sys.path:
            sys.path.remove(project_str)
        sys.modules.pop("assets", None)
        sys.modules.pop("assets.example", None)
        sys.modules.pop("assets.__init__", None)
        _reset_registry_for_tests()


# CliRunner with mix_stderr=False so we can read stdout (rendered table /
# NDJSON / CSV) and stderr (NucleusError messages, Dagster log noise)
# separately. The default mix_stderr=True mode garbles JSON parsing because
# Dagster's debug logger goes to stderr.
runner = CliRunner(mix_stderr=False)


class TestHappyPath:
    """Materialize the bundled example asset and inspect rendered output."""

    def test_exit_code_zero(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting"])
        assert result.exit_code == 0, f"unexpected: {result.stdout} | {result.stderr}"

    def test_output_contains_asset_key(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting"])
        assert "example.greeting" in result.stdout

    def test_output_indicates_success(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting"])
        assert "success" in result.stdout

    def test_no_forbidden_classnames(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting"])
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in result.stdout, f"leaked {term!r}: {result.stdout}"


class TestDryRun:
    """``--dry-run`` invokes the AMA without committing and labels output."""

    def test_dry_run_exit_zero(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting", "--dry-run"])
        assert result.exit_code == 0, result.stdout

    def test_dry_run_status_label(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting", "--dry-run"])
        assert "dry-run" in result.stdout


class TestJsonFormat:
    """``--format json`` emits one NDJSON line on stdout (dagster logs go to stderr)."""

    def test_json_exit_zero(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting", "--format", "json"])
        assert result.exit_code == 0, result.stderr

    def test_json_output_parses(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting", "--format", "json"])
        line = result.stdout.strip().splitlines()[-1]
        payload = json.loads(line)
        assert payload["asset_key"] == "example.greeting"
        assert payload["status"] == "success"
        assert payload["_schema_version"] == 1


class TestErrorPaths:
    """Validation + scope errors map to the right NucleusError subclass."""

    def test_asset_not_found(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "nonexistent.asset"])
        assert result.exit_code == 1
        assert "Asset 'nonexistent.asset' is not defined." in result.stderr

    def test_asset_not_found_no_dagster_leak(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "nonexistent.asset"])
        for term in _FORBIDDEN_CLASSNAMES:
            assert term not in result.stderr, f"leaked {term!r}: {result.stderr}"

    def test_no_project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["run", "any.asset"])
        assert result.exit_code == 1
        assert "nucleus init" in result.stderr
        assert "nucleus_project.yaml" in result.stderr

    def test_all_flag_deferred(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "--all"])
        assert result.exit_code == 1
        assert "deferred to v0.2+" in result.stderr

    def test_changed_only_flag_deferred(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting", "--changed-only"])
        assert result.exit_code == 1
        assert "deferred to v0.2+" in result.stderr

    def test_param_flag_deferred(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting", "--param", "env=prod"])
        assert result.exit_code == 1
        assert "deferred to v0.3+" in result.stderr

    def test_multi_asset_rejected(self, project: Path) -> None:
        result = runner.invoke(app, ["run", "example.greeting", "second.asset"])
        assert result.exit_code == 1
        assert "single asset" in result.stderr
