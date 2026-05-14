"""Tests for ``nucleus schedule`` command group — ADR-017.

Validates:
    - ``nucleus schedule list`` shows scheduled assets; empty message when none.
    - ``nucleus schedule list --format json`` emits valid JSON.
    - ``nucleus schedule preview <key>`` shows next 3 run times.
    - ``nucleus schedule preview <key> --count 5`` shows 5 run times.
    - ``nucleus schedule on/off/trigger <key>`` raise NucleusFeatureDeferredError
      with a clear "v0.2" message and NE5008.
    - ``--help`` exits 0 and lists all sub-commands.
    - No Dagster classnames in any user-facing output.

The ``_import_project_assets`` helper in ``schedule.py`` is patched to a no-op
so tests don't need a ``nucleus_project.yaml`` on disk.

Docs:
    - Typer testing: https://typer.tiangolo.com/tutorial/testing/
    - unittest.mock.patch: https://docs.python.org/3/library/unittest.mock.html
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nucleus.cli.main import app
from nucleus.sdk.decorators import _reset_registry_for_tests


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


# Patch _import_project_assets so tests don't require a project on disk.
_PATCH_IMPORT_ASSETS = patch(
    "nucleus.cli.commands.schedule._import_project_assets",
    return_value=None,
)


# ---------------------------------------------------------------------------
# nucleus schedule --help
# ---------------------------------------------------------------------------


class TestScheduleHelp:
    def test_help_exits_zero(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["schedule", "--help"])
        assert result.exit_code == 0

    def test_help_lists_list_subcommand(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["schedule", "--help"])
        assert "list" in result.output

    def test_help_lists_preview_subcommand(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["schedule", "--help"])
        assert "preview" in result.output

    def test_help_lists_on_off_trigger_subcommands(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["schedule", "--help"])
        assert "on" in result.output
        assert "off" in result.output
        assert "trigger" in result.output


# ---------------------------------------------------------------------------
# nucleus schedule list
# ---------------------------------------------------------------------------


class TestScheduleList:
    def test_empty_message_when_no_schedules(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("staging.orders")
        def orders(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "list"])

        assert result.exit_code == 0
        assert "No scheduled assets" in result.output

    def test_shows_scheduled_asset(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("marts.revenue", schedule="0 2 * * *")
        def revenue(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "list"])

        assert result.exit_code == 0
        assert "marts.revenue" in result.output
        assert "0 2 * * *" in result.output

    def test_json_format_emits_valid_json(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("marts.rev", schedule="@daily")
        def rev(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "list", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["asset_key"] == "marts.rev"
        assert data[0]["cron_expression"] == "0 0 * * *"  # normalised from @daily

    def test_json_format_includes_next_run(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("marts.weekly", schedule="@weekly")
        def weekly(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "list", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data[0]["next_run"] is not None
        # next_run should be an ISO-8601 string
        assert "T" in data[0]["next_run"]

    def test_invalid_format_exits_nonzero(self, runner: CliRunner) -> None:
        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "list", "--format", "csv"])

        assert result.exit_code != 0
        # Error rendered to stderr; combine both streams for the assertion.
        combined = (result.output or "") + (result.stderr or "")
        assert "Error:" in combined or "csv" in combined

    def test_no_dagster_classnames_in_output(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("marts.rev", schedule="0 2 * * *")
        def rev(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "list"])

        combined = (result.output or "") + (result.stderr or "")
        assert "dagster" not in combined.lower()
        assert "ScheduleDefinition" not in combined
        assert "DagsterError" not in combined


# ---------------------------------------------------------------------------
# nucleus schedule preview
# ---------------------------------------------------------------------------


class TestSchedulePreview:
    def test_shows_default_three_run_times(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("marts.revenue", schedule="0 2 * * *")
        def revenue(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "preview", "marts.revenue"])

        assert result.exit_code == 0
        # Expect 3 numbered lines
        assert "1." in result.output
        assert "2." in result.output
        assert "3." in result.output

    def test_count_flag_changes_output_count(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("marts.hourly", schedule="@hourly")
        def hourly(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(
                app, ["schedule", "preview", "marts.hourly", "--count", "5"]
            )

        assert result.exit_code == 0
        assert "5." in result.output

    def test_json_format_returns_structured_output(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("marts.rev", schedule="@daily")
        def rev(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(
                app,
                ["schedule", "preview", "marts.rev", "--format", "json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["asset_key"] == "marts.rev"
        assert isinstance(data["next_runs"], list)
        assert len(data["next_runs"]) == 3

    def test_unknown_asset_exits_nonzero(self, runner: CliRunner) -> None:
        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "preview", "marts.nonexistent"])

        assert result.exit_code != 0
        assert "Error:" in result.output or "Error:" in result.stderr

    def test_no_dagster_classnames_in_preview_output(self, runner: CliRunner) -> None:
        import nucleus

        @nucleus.asset("marts.nodags", schedule="@monthly")
        def nodags(_ctx: object) -> None:
            return None

        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", "preview", "marts.nodags"])

        combined = (result.output or "") + (result.stderr or "")
        assert "dagster" not in combined.lower()


# ---------------------------------------------------------------------------
# Deferred stubs: nucleus schedule on / off / trigger
# ---------------------------------------------------------------------------


class TestScheduleDeferredCommands:
    """on/off/trigger raise NucleusFeatureDeferredError with NE5008."""

    @pytest.mark.parametrize("sub", ["on", "off", "trigger"])
    def test_exits_nonzero(self, runner: CliRunner, sub: str) -> None:
        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", sub, "marts.revenue"])

        assert result.exit_code != 0

    @pytest.mark.parametrize("sub", ["on", "off", "trigger"])
    def test_v02_message_in_output(self, runner: CliRunner, sub: str) -> None:
        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", sub, "marts.revenue"])

        combined = (result.output or "") + (result.stderr or "")
        assert "v0.2" in combined or "deferred" in combined.lower()

    @pytest.mark.parametrize("sub", ["on", "off", "trigger"])
    def test_no_dagster_classnames_in_deferred_output(
        self, runner: CliRunner, sub: str
    ) -> None:
        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", sub, "marts.revenue"])

        combined = (result.output or "") + (result.stderr or "")
        assert "dagster" not in combined.lower()
        assert "ScheduleDefinition" not in combined

    @pytest.mark.parametrize("sub", ["on", "off", "trigger"])
    def test_docs_url_in_output(self, runner: CliRunner, sub: str) -> None:
        with _PATCH_IMPORT_ASSETS:
            result = runner.invoke(app, ["schedule", sub, "marts.revenue"])

        combined = (result.output or "") + (result.stderr or "")
        assert "Docs:" in combined or "nucleus.dev" in combined
