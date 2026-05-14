"""Tests for ``nucleus.coordination.schedules`` — ADR-017.

Validates:
    - :func:`list_schedules` returns ScheduleEntry records for scheduled assets.
    - :func:`preview_schedule` returns ISO-8601 UTC run times via croniter.
    - :func:`preview_schedule` raises NucleusScheduleNotFoundError for
      unregistered or unscheduled assets.
    - :func:`to_dagster_schedule` wraps Dagster ScheduleDefinition (v0.2 path).

Per ``nucleus_architecture_v4.1.md`` §6.3 (Coordination — Dagster wrap) and
ADR-017 §1.

No Dagster types must cross the outbound coordination boundary in
:func:`list_schedules` or :func:`preview_schedule` — enforced by assertions
and ``scripts/dagster_leak_check.py`` in CI.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

import nucleus
from nucleus.coordination.schedules import (
    ScheduleEntry,
    list_schedules,
    preview_schedule,
    to_dagster_schedule,
)
from nucleus.errors import NucleusScheduleNotFoundError
from nucleus.sdk.decorators import _reset_registry_for_tests, get_asset


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


# ---------------------------------------------------------------------------
# ScheduleEntry dataclass
# ---------------------------------------------------------------------------


class TestScheduleEntry:
    def test_is_frozen(self) -> None:
        entry = ScheduleEntry(asset_key="marts.rev", cron_expression="0 2 * * *")
        with pytest.raises((AttributeError, TypeError)):
            entry.asset_key = "other.key"  # type: ignore[misc]

    def test_default_description_is_empty(self) -> None:
        entry = ScheduleEntry(asset_key="marts.rev", cron_expression="0 2 * * *")
        assert entry.description == ""

    def test_no_dagster_types_in_entry(self) -> None:
        entry = ScheduleEntry(asset_key="marts.rev", cron_expression="0 2 * * *")
        # No Dagster classnames must appear in repr / str of the entry.
        entry_repr = repr(entry)
        assert "dagster" not in entry_repr.lower()


# ---------------------------------------------------------------------------
# list_schedules()
# ---------------------------------------------------------------------------


class TestListSchedules:
    def test_returns_empty_tuple_when_no_assets(self) -> None:
        assert list_schedules() == ()

    def test_returns_empty_when_assets_have_no_schedule(self) -> None:
        @nucleus.asset("staging.orders")
        def orders(_ctx: object) -> None:
            return None

        assert list_schedules() == ()

    def test_returns_entry_for_scheduled_asset(self) -> None:
        @nucleus.asset("marts.revenue", schedule="0 2 * * *")
        def revenue(_ctx: object) -> None:
            return None

        entries = list_schedules()
        assert len(entries) == 1
        entry = entries[0]
        assert isinstance(entry, ScheduleEntry)
        assert entry.asset_key == "marts.revenue"
        assert entry.cron_expression == "0 2 * * *"

    def test_alias_stored_normalised(self) -> None:
        @nucleus.asset("marts.daily_rev", schedule="@daily")
        def daily_rev(_ctx: object) -> None:
            return None

        entries = list_schedules()
        assert entries[0].cron_expression == "0 0 * * *"

    def test_excludes_unscheduled_assets(self) -> None:
        @nucleus.asset("staging.a", schedule="@hourly")
        def a(_ctx: object) -> None:
            return None

        @nucleus.asset("staging.b")
        def b(_ctx: object) -> None:
            return None

        entries = list_schedules()
        keys = [e.asset_key for e in entries]
        assert "staging.a" in keys
        assert "staging.b" not in keys

    def test_multiple_schedules_returned_sorted(self) -> None:
        @nucleus.asset("marts.zzz", schedule="@daily")
        def zzz(_ctx: object) -> None:
            return None

        @nucleus.asset("marts.aaa", schedule="@weekly")
        def aaa(_ctx: object) -> None:
            return None

        entries = list_schedules()
        assert entries[0].asset_key == "marts.aaa"
        assert entries[1].asset_key == "marts.zzz"

    def test_no_dagster_types_in_return(self) -> None:
        @nucleus.asset("marts.rev", schedule="0 2 * * *")
        def rev(_ctx: object) -> None:
            return None

        entries = list_schedules()
        for entry in entries:
            entry_str = str(type(entry))
            assert "dagster" not in entry_str.lower()


# ---------------------------------------------------------------------------
# preview_schedule()
# ---------------------------------------------------------------------------


class TestPreviewSchedule:
    """preview_schedule() returns ISO-8601 UTC strings via croniter."""

    _ISO8601_RE = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+\d{2}:\d{2}$"
    )

    def test_returns_three_run_times_by_default(self) -> None:
        @nucleus.asset("marts.revenue", schedule="0 2 * * *")
        def revenue(_ctx: object) -> None:
            return None

        runs = preview_schedule("marts.revenue")
        assert len(runs) == 3

    def test_run_times_are_iso8601_utc(self) -> None:
        @nucleus.asset("marts.rev", schedule="@daily")
        def rev(_ctx: object) -> None:
            return None

        runs = preview_schedule("marts.rev", n=2)
        for ts in runs:
            assert self._ISO8601_RE.match(ts), f"{ts!r} is not ISO-8601 UTC"

    def test_run_times_are_in_ascending_order(self) -> None:
        @nucleus.asset("marts.ordered", schedule="0 0 * * *")
        def ordered(_ctx: object) -> None:
            return None

        runs = preview_schedule("marts.ordered", n=3)
        datetimes = [datetime.fromisoformat(ts) for ts in runs]
        assert datetimes == sorted(datetimes)

    def test_run_times_are_in_future(self) -> None:
        @nucleus.asset("marts.future", schedule="@hourly")
        def future(_ctx: object) -> None:
            return None

        runs = preview_schedule("marts.future", n=1)
        run_dt = datetime.fromisoformat(runs[0])
        assert run_dt > datetime.now(UTC)

    def test_custom_n_count(self) -> None:
        @nucleus.asset("marts.custom_n", schedule="*/15 * * * *")
        def custom_n(_ctx: object) -> None:
            return None

        for n in (1, 5, 10):
            runs = preview_schedule("marts.custom_n", n=n)
            assert len(runs) == n

    def test_n_clamped_to_maximum(self) -> None:
        @nucleus.asset("marts.max_n", schedule="@hourly")
        def max_n(_ctx: object) -> None:
            return None

        runs = preview_schedule("marts.max_n", n=100)
        assert len(runs) == 20  # clamped to 20

    def test_n_clamped_to_minimum(self) -> None:
        @nucleus.asset("marts.min_n", schedule="@hourly")
        def min_n(_ctx: object) -> None:
            return None

        runs = preview_schedule("marts.min_n", n=0)
        assert len(runs) == 1  # clamped to 1

    def test_unregistered_key_raises_schedule_not_found(self) -> None:
        with pytest.raises(NucleusScheduleNotFoundError) as exc_info:
            preview_schedule("marts.nonexistent")

        err = exc_info.value
        assert err.error_code == "NE5006"
        assert err.asset == "marts.nonexistent"

    def test_registered_but_unscheduled_raises_not_found(self) -> None:
        @nucleus.asset("staging.no_schedule")
        def no_schedule(_ctx: object) -> None:
            return None

        with pytest.raises(NucleusScheduleNotFoundError) as exc_info:
            preview_schedule("staging.no_schedule")

        err = exc_info.value
        assert err.error_code == "NE5006"
        assert "schedule" in err.fix_hint.lower()


# ---------------------------------------------------------------------------
# to_dagster_schedule()
# ---------------------------------------------------------------------------


class TestToDagsterSchedule:
    """to_dagster_schedule() wraps a ScheduleDefinition — v0.2 path."""

    def test_returns_dagster_schedule_definition(self) -> None:
        @nucleus.asset("marts.rev", schedule="0 2 * * *")
        def rev(_ctx: object) -> None:
            return None

        defn = get_asset("marts.rev")
        assert defn is not None
        sched = to_dagster_schedule(defn)
        # We verify the type by checking its attribute rather than importing Dagster
        # types into test code (no Dagster classnames in test assertions per v4.1 §6.4).
        assert hasattr(sched, "cron_schedule")
        assert sched.cron_schedule == "0 2 * * *"

    def test_schedule_name_derived_from_asset_key(self) -> None:
        @nucleus.asset("marts.my_asset", schedule="@daily")
        def my_asset(_ctx: object) -> None:
            return None

        defn = get_asset("marts.my_asset")
        assert defn is not None
        sched = to_dagster_schedule(defn)
        assert hasattr(sched, "name")
        assert "marts" in sched.name
        assert "my_asset" in sched.name

    def test_no_schedule_raises_invalid_asset_definition(self) -> None:
        @nucleus.asset("staging.no_sched")
        def no_sched(_ctx: object) -> None:
            return None

        defn = get_asset("staging.no_sched")
        assert defn is not None

        from nucleus.errors import NucleusInvalidAssetDefinition

        with pytest.raises(NucleusInvalidAssetDefinition):
            to_dagster_schedule(defn)
