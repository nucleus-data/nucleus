"""Tests for ``@nucleus.asset(schedule=...)`` kwarg — ADR-017 §3.

Validates the v0.1.1 schedule kwarg surface per:
    - ``docs/specs/nucleus_ctx_sdk_spec.md`` §5 (decorator surface, schedule field)
    - ADR-017 §3 (cron normalisation + shorthand aliases)
    - ADR-006 §NE5005 (NucleusScheduleParseError allocation)

All errors must surface at decoration time (import time) so users see them
immediately rather than at materialisation.

The registry is module-level state; the ``_clean_registry`` fixture clears
both registries before and after every test for cross-test isolation.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

import nucleus
from nucleus.errors import NucleusScheduleParseError
from nucleus.sdk.decorators import (
    _reset_registry_for_tests,
    get_asset,
    get_scheduled_assets,
)


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


# ---------------------------------------------------------------------------
# Happy paths — valid schedule= values
# ---------------------------------------------------------------------------


class TestScheduleKwargHappyPaths:
    """schedule= accepted and normalised correctly."""

    def test_no_schedule_defaults_to_none(self) -> None:
        @nucleus.asset("staging.orders")
        def orders(_ctx: object) -> None:
            return None

        record = get_asset("staging.orders")
        assert record is not None
        assert record.schedule is None

    def test_explicit_none_schedule(self) -> None:
        @nucleus.asset("staging.users", schedule=None)
        def users(_ctx: object) -> None:
            return None

        record = get_asset("staging.users")
        assert record is not None
        assert record.schedule is None

    def test_five_field_cron_accepted(self) -> None:
        @nucleus.asset("marts.revenue", schedule="0 2 * * *")
        def revenue(_ctx: object) -> None:
            return None

        record = get_asset("marts.revenue")
        assert record is not None
        assert record.schedule == "0 2 * * *"

    def test_daily_alias_normalised(self) -> None:
        @nucleus.asset("marts.daily", schedule="@daily")
        def daily(_ctx: object) -> None:
            return None

        record = get_asset("marts.daily")
        assert record is not None
        assert record.schedule == "0 0 * * *"

    def test_midnight_alias_same_as_daily(self) -> None:
        @nucleus.asset("marts.midnight", schedule="@midnight")
        def midnight(_ctx: object) -> None:
            return None

        record = get_asset("marts.midnight")
        assert record is not None
        assert record.schedule == "0 0 * * *"

    def test_hourly_alias_normalised(self) -> None:
        @nucleus.asset("staging.hourly", schedule="@hourly")
        def hourly(_ctx: object) -> None:
            return None

        record = get_asset("staging.hourly")
        assert record is not None
        assert record.schedule == "0 * * * *"

    def test_weekly_alias_normalised(self) -> None:
        @nucleus.asset("staging.weekly", schedule="@weekly")
        def weekly(_ctx: object) -> None:
            return None

        record = get_asset("staging.weekly")
        assert record is not None
        assert record.schedule == "0 0 * * 0"

    def test_monthly_alias_normalised(self) -> None:
        @nucleus.asset("staging.monthly", schedule="@monthly")
        def monthly(_ctx: object) -> None:
            return None

        record = get_asset("staging.monthly")
        assert record is not None
        assert record.schedule == "0 0 1 * *"

    def test_yearly_alias_normalised(self) -> None:
        @nucleus.asset("staging.yearly", schedule="@yearly")
        def yearly(_ctx: object) -> None:
            return None

        record = get_asset("staging.yearly")
        assert record is not None
        assert record.schedule == "0 0 1 1 *"

    def test_annually_alias_same_as_yearly(self) -> None:
        @nucleus.asset("staging.annually", schedule="@annually")
        def annually(_ctx: object) -> None:
            return None

        record = get_asset("staging.annually")
        assert record is not None
        assert record.schedule == "0 0 1 1 *"

    def test_every_five_minutes(self) -> None:
        @nucleus.asset("staging.fivemin", schedule="*/5 * * * *")
        def fivemin(_ctx: object) -> None:
            return None

        record = get_asset("staging.fivemin")
        assert record is not None
        assert record.schedule == "*/5 * * * *"

    def test_schedule_coexists_with_deps(self) -> None:
        @nucleus.asset("marts.scheduled_with_deps", deps=["raw.events"], schedule="0 3 * * *")
        def scheduled_with_deps(_ctx: object) -> None:
            return None

        record = get_asset("marts.scheduled_with_deps")
        assert record is not None
        assert record.schedule == "0 3 * * *"
        assert record.deps == ("raw.events",)


# ---------------------------------------------------------------------------
# Error paths — invalid schedule= values
# ---------------------------------------------------------------------------


class TestScheduleKwargErrorPaths:
    """Invalid schedule= raises NucleusScheduleParseError at decoration time."""

    def test_invalid_cron_string_raises(self) -> None:
        with pytest.raises(NucleusScheduleParseError) as exc_info:

            @nucleus.asset("marts.bad", schedule="not-a-cron")
            def bad(_ctx: object) -> None:
                return None

        err = exc_info.value
        assert err.error_code == "NE5005"
        assert "not-a-cron" in err.user_message
        assert "fix_hint" not in err.user_message  # user_message doesn't contain fix_hint
        assert err.fix_hint != ""
        assert "@daily" in err.fix_hint

    def test_non_string_schedule_raises(self) -> None:
        with pytest.raises(NucleusScheduleParseError) as exc_info:

            @nucleus.asset("marts.badtype", schedule=42)  # type: ignore[arg-type]
            def badtype(_ctx: object) -> None:
                return None

        err = exc_info.value
        assert err.error_code == "NE5005"
        assert "int" in err.user_message

    def test_empty_string_schedule_raises(self) -> None:
        with pytest.raises(NucleusScheduleParseError) as exc_info:

            @nucleus.asset("marts.empty_sched", schedule="")
            def empty_sched(_ctx: object) -> None:
                return None

        assert exc_info.value.error_code == "NE5005"

    def test_six_field_cron_raises(self) -> None:
        """6-field cron (includes seconds) is not supported in v0.1."""
        with pytest.raises(NucleusScheduleParseError):

            @nucleus.asset("marts.sixfield", schedule="0 0 2 * * *")
            def sixfield(_ctx: object) -> None:
                return None

    def test_error_carries_asset_key(self) -> None:
        with pytest.raises(NucleusScheduleParseError) as exc_info:

            @nucleus.asset("marts.err_key", schedule="INVALID")
            def err_key(_ctx: object) -> None:
                return None

        assert exc_info.value.asset == "marts.err_key"

    def test_unknown_shorthand_raises(self) -> None:
        """@yearly and @annually are supported, but @quarterly is not."""
        with pytest.raises(NucleusScheduleParseError):

            @nucleus.asset("marts.quarterly", schedule="@quarterly")
            def quarterly(_ctx: object) -> None:
                return None


# ---------------------------------------------------------------------------
# Registry accessor — get_scheduled_assets()
# ---------------------------------------------------------------------------


class TestGetScheduledAssets:
    """get_scheduled_assets() returns only assets with a declared schedule."""

    def test_returns_empty_when_no_schedules(self) -> None:
        @nucleus.asset("staging.no_schedule")
        def no_schedule(_ctx: object) -> None:
            return None

        assert get_scheduled_assets() == ()

    def test_returns_single_scheduled_asset(self) -> None:
        @nucleus.asset("marts.with_schedule", schedule="@daily")
        def with_schedule(_ctx: object) -> None:
            return None

        result = get_scheduled_assets()
        assert len(result) == 1
        assert result[0].key == "marts.with_schedule"
        assert result[0].schedule == "0 0 * * *"

    def test_excludes_unscheduled_sibling(self) -> None:
        @nucleus.asset("staging.a", schedule="@hourly")
        def a(_ctx: object) -> None:
            return None

        @nucleus.asset("staging.b")
        def b(_ctx: object) -> None:
            return None

        result = get_scheduled_assets()
        keys = [r.key for r in result]
        assert "staging.a" in keys
        assert "staging.b" not in keys

    def test_result_sorted_by_key(self) -> None:
        @nucleus.asset("marts.zzz", schedule="@daily")
        def zzz(_ctx: object) -> None:
            return None

        @nucleus.asset("marts.aaa", schedule="@weekly")
        def aaa(_ctx: object) -> None:
            return None

        result = get_scheduled_assets()
        assert result[0].key == "marts.aaa"
        assert result[1].key == "marts.zzz"

    def test_multiple_scheduled_assets(self) -> None:
        for i in range(3):
            # Use a closure-capture variable to avoid name conflicts
            cron = f"0 {i} * * *"

            def make_fn(n: int):
                @nucleus.asset(f"staging.asset{n}", schedule=f"0 {n} * * *")
                def fn(_ctx: object) -> None:
                    return None

                return fn

            make_fn(i)
            _ = cron  # suppress unused warning

        result = get_scheduled_assets()
        assert len(result) == 3
