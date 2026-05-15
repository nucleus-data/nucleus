# ruff: noqa: ARG002
"""Tests for ``nucleus list`` — PoC #5 Checkpoint 7 close.

Covers the discoverability surface promised by
``docs/poc/p5_beachhead/FEEDBACK_FORM.md`` Friction #5 / "What would make me a paying user" #3.

T01  Empty project (no assets) shows a helpful hint
T02  Bundled example asset (``example.greeting``) is listed by default
T03  Multiple assets across multiple namespaces all appear, sorted
T04  ``--namespace raw`` filter shows only ``raw.*`` entries
T05  ``--format json`` emits one valid NDJSON line per row
T06  ``--format jsonl`` is an alias for ``json``
T07  Unknown ``--format`` raises ``NucleusInvalidAssetDefinition`` (NE3004)
T08  No ``nucleus_project.yaml`` ⇒ NucleusError with ``nucleus init`` hint
T09  After ``nucleus run``, the asset row reports ``materialized=yes``
T10  Description column is truncated to ~60 characters
T11  Empty ``--namespace foo`` filter prints a "no assets in 'foo'" hint
T12  None of the rendered text contains Dagster / DuckDB / pyiceberg class names

The test fixture mirrors ``tests/cli/test_run.py:project`` — scaffold via
``nucleus init demo``, chdir, reset the in-process asset registry between
tests so the example asset is fresh each time.

Docs:
    - Typer testing:    https://typer.tiangolo.com/tutorial/testing/
    - CliRunner:        https://typer.tiangolo.com/tutorial/testing/#typer-testing-clirunner
"""

from __future__ import annotations

import json
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nucleus.cli.commands.list import app as list_app
from nucleus.cli.main import app as nucleus_app
from nucleus.sdk.decorators import _reset_registry_for_tests

# Internal classnames that must never appear in user-facing output per v4.1 §6.4.
_FORBIDDEN_CLASSNAMES = (
    "DagsterInstance",
    "OpExecutionContext",
    "DuckDBPyConnection",
    "Traceback (most recent call last)",
    "dagster._",
    "duckdb._",
    "polars._",
    "pyiceberg._",
    "sqlalchemy.",
)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Scaffold a clean ``nucleus init demo`` project per test and chdir."""
    monkeypatch.chdir(tmp_path)
    init_runner = CliRunner()
    init_result = init_runner.invoke(nucleus_app, ["init", "demo"])
    assert init_result.exit_code == 0, f"init failed: {init_result.stdout}"
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
        for mod in ("assets", "assets.example", "assets.__init__", "assets.extras"):
            sys.modules.pop(mod, None)
        _reset_registry_for_tests()


def _write_asset_file(project_root: Path, filename: str, body: str) -> None:
    """Drop a Python file into ``<project>/assets/`` so it registers on import."""
    assets_dir = project_root / "assets"
    assets_dir.mkdir(exist_ok=True)
    (assets_dir / filename).write_text(textwrap.dedent(body), encoding="utf-8")


runner = CliRunner(mix_stderr=False)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestListHappyPath:
    def test_t02_example_asset_listed_by_default(self, project: Path) -> None:
        """T02: the bundled ``example.greeting`` asset shows up by default."""
        result = runner.invoke(list_app, [])
        assert result.exit_code == 0, f"stderr: {result.stderr}"
        assert "example.greeting" in result.stdout
        assert "asset" in result.stdout

    def test_t03_multiple_namespaces_all_listed(self, project: Path) -> None:
        """T03: assets in distinct namespaces all appear, sorted alphabetically."""
        _write_asset_file(
            project,
            "extras.py",
            """
            import polars as pl
            import nucleus

            @nucleus.asset("raw.orders")
            def raw_orders(ctx):
                return pl.DataFrame({"id": [1, 2, 3]})

            @nucleus.asset("staging.customers")
            def staging_customers(ctx):
                return pl.DataFrame({"id": [1]})
            """,
        )
        result = runner.invoke(list_app, [])
        assert result.exit_code == 0, result.stderr
        out = result.stdout
        assert "example.greeting" in out
        assert "raw.orders" in out
        assert "staging.customers" in out
        # Stable sort: raw.* < staging.* alphabetically — check ordering.
        assert out.index("raw.orders") < out.index("staging.customers")

    def test_t04_namespace_filter(self, project: Path) -> None:
        """T04: ``--namespace raw`` returns raw.* rows only."""
        _write_asset_file(
            project,
            "extras.py",
            """
            import polars as pl
            import nucleus

            @nucleus.asset("raw.orders")
            def raw_orders(ctx):
                return pl.DataFrame({"id": [1]})

            @nucleus.asset("mart.daily")
            def mart_daily(ctx):
                return pl.DataFrame({"id": [1]})
            """,
        )
        result = runner.invoke(list_app, ["--namespace", "raw"])
        assert result.exit_code == 0, result.stderr
        assert "raw.orders" in result.stdout
        assert "mart.daily" not in result.stdout
        assert "example.greeting" not in result.stdout


# ---------------------------------------------------------------------------
# Format tests
# ---------------------------------------------------------------------------


class TestListFormats:
    def test_t05_json_emits_ndjson(self, project: Path) -> None:
        """T05: ``--format json`` emits one JSON object per row, parseable."""
        result = runner.invoke(list_app, ["--format", "json"])
        assert result.exit_code == 0, result.stderr
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        assert len(lines) >= 1
        for line in lines:
            payload = json.loads(line)
            assert "key" in payload
            assert payload["_schema_version"] == 1
            assert payload["type"] in {"asset", "check"}

    def test_t06_jsonl_alias_for_json(self, project: Path) -> None:
        """T06: ``--format jsonl`` produces identical output to ``--format json``."""
        a = runner.invoke(list_app, ["--format", "json"])
        b = runner.invoke(list_app, ["--format", "jsonl"])
        assert a.exit_code == 0
        assert b.exit_code == 0
        assert a.stdout == b.stdout

    def test_t07_invalid_format_raises_ne3004(self, project: Path) -> None:
        """T07: an unknown ``--format`` value raises NE3004 with a fix hint."""
        result = runner.invoke(list_app, ["--format", "xml"])
        assert result.exit_code != 0
        combined = result.stderr + result.stdout
        assert "NE3004" in combined or "--format" in combined
        assert "xml" in combined or "not supported" in combined


# ---------------------------------------------------------------------------
# Empty-state + error tests
# ---------------------------------------------------------------------------


class TestListEmptyAndErrors:
    def test_t01_empty_project_helpful_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T01: project with zero registered assets shows the empty-state hint."""
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(nucleus_app, ["init", "empty"])
        project_root = tmp_path / "empty"
        # Replace the bundled example asset file with an empty registry so no
        # @nucleus.asset decorators fire on import.
        (project_root / "assets" / "example.py").write_text(
            "# intentionally empty for the empty-list test\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(project_root)
        _reset_registry_for_tests()
        sys.modules.pop("assets", None)
        sys.modules.pop("assets.example", None)
        try:
            result = runner.invoke(list_app, [])
            assert result.exit_code == 0
            assert "No assets" in result.stdout
            assert "nucleus init" in result.stdout or "@nucleus.asset" in result.stdout
        finally:
            sys.modules.pop("assets", None)
            sys.modules.pop("assets.example", None)
            _reset_registry_for_tests()

    def test_t08_no_project_emits_init_hint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T08: invoking outside a project surfaces the ``nucleus init`` fix hint."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(list_app, [])
        assert result.exit_code != 0
        combined = result.stderr + result.stdout
        assert "nucleus init" in combined
        assert "nucleus_project.yaml" in combined

    def test_t11_namespace_filter_no_match(self, project: Path) -> None:
        """T11: ``--namespace doesnotexist`` shows a helpful empty-namespace hint."""
        result = runner.invoke(list_app, ["--namespace", "doesnotexist"])
        assert result.exit_code == 0
        assert "doesnotexist" in result.stdout
        assert "no assets" in result.stdout.lower() or "no assets" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Materialization status
# ---------------------------------------------------------------------------


class TestListMaterializationStatus:
    def test_t09_materialized_status_after_run(self, project: Path) -> None:
        """T09: after ``nucleus run example.greeting``, the row is ``materialized=yes``."""
        run_result = CliRunner(mix_stderr=False).invoke(nucleus_app, ["run", "example.greeting"])
        assert run_result.exit_code == 0, run_result.stderr

        # Reset the registry first so re-importing assets/example.py inside
        # list_assets repopulates it — otherwise the `nucleus run` import has
        # already cached the module and the re-import is a no-op.
        _reset_registry_for_tests()
        sys.modules.pop("assets", None)
        sys.modules.pop("assets.example", None)

        result = runner.invoke(list_app, ["--format", "json"])
        assert result.exit_code == 0, result.stderr
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        greeting = next(r for r in rows if r["key"] == "example.greeting")
        assert greeting["materialized"] is True
        assert greeting["last_materialized_ms"] is not None


# ---------------------------------------------------------------------------
# Description truncation + leak guard
# ---------------------------------------------------------------------------


class TestListPolish:
    def test_t10_description_truncated_to_60_chars(self, project: Path) -> None:
        """T10: long docstrings render truncated (≤ 60 characters)."""
        long_desc = "x" * 200
        _write_asset_file(
            project,
            "extras.py",
            f"""
            import polars as pl
            import nucleus

            @nucleus.asset("raw.docs_long")
            def raw_docs_long(ctx):
                '''{long_desc}'''
                return pl.DataFrame({{"id": [1]}})
            """,
        )
        result = runner.invoke(list_app, ["--format", "json"])
        assert result.exit_code == 0, result.stderr
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        long_row = next(r for r in rows if r["key"] == "raw.docs_long")
        assert 0 < len(long_row["description"]) <= 60

    def test_t12_no_classname_leaks_in_any_output(self, project: Path) -> None:
        """T12: zero Dagster / DuckDB / pyiceberg class names in stdout or stderr."""
        cases = [[], ["--format", "json"], ["--namespace", "example"]]
        for argv in cases:
            result = runner.invoke(list_app, argv)
            combined = (result.stdout or "") + (result.stderr or "")
            for banned in _FORBIDDEN_CLASSNAMES:
                assert banned not in combined, (
                    f"banned classname {banned!r} leaked into output for argv={argv!r}"
                )
