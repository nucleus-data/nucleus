"""Tests for :mod:`nucleus.coordination.asset_materialization` (the AMA).

Validates the Asset Materialization Adapter end-to-end per
``nucleus_architecture_v4.1.md`` §6.2 + ``docs/decisions/ADR-013-ctx-materialize-api.md`` §1+§2.
The SDK-boundary contract (eager validation, AssetRef unwrapping,
upstream deferred-mode rejection) is exercised in
``tests/sdk/test_materialize.py``; this file covers the parts the SDK
delegates downward:

    * Happy-path materialize (direct asset-body invocation, no Dagster IO manager)
    * Iceberg commit path (DataFrame → real snapshot_id + row_count)
    * dry_run routing (body executes but no Iceberg commit occurs)
    * registry miss → NucleusAssetNotFound with no external classname leak
    * asset body raising → NucleusError via error_translation.translate()
    * partition propagation into MaterializationResult
    * upstream != "skip" defensive rejection at the AMA layer
    * Result-shape invariants (MaterializationResult per ADR-013 §2,
      field-additive per ADR-005 §1 + ADR-013 §3)

The translation guarantees overlap with
``tests/coordination/test_error_translation.py``; the cases below verify
the AMA actually drives translate() at the asset-body boundary, not just
that translate() works in isolation.

AMA v0.1 data path (2026-05-14 beachhead E2E fix):
    Asset body is called directly (no Dagster IO manager). Polars DataFrame
    or PyArrow Table return values are committed to Iceberg via pyiceberg.
    Non-committable return types (None, int, etc.) return sentinel values.
    ``warehouse_dir=None`` also returns sentinels (deferred commit).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

import nucleus
from nucleus.coordination.asset_materialization import materialize_asset
from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusError,
    NucleusInternalError,
    NucleusSchemaError,
    NucleusSourceConnectionError,
)
from nucleus.sdk.decorators import _reset_registry_for_tests
from nucleus.sdk.results import MaterializationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registry() -> Iterator[None]:
    _reset_registry_for_tests()
    try:
        yield
    finally:
        _reset_registry_for_tests()


@pytest.fixture()
def trivial_asset_key() -> str:
    """Register a no-arg asset that simply returns None.

    Mirrors the v0.1 idiom for assets whose body is a pure side effect
    once Iceberg/ctx wiring lands; the AMA must still produce a clean
    MaterializationResult for them.
    """
    @nucleus.asset("staging.orders")
    def staging_orders() -> None:
        return None

    return "staging.orders"


@pytest.fixture()
def value_returning_asset_key() -> str:
    """Register an asset whose body returns a concrete value."""
    @nucleus.asset("marts.row_count")
    def marts_row_count() -> int:
        return 42

    return "marts.row_count"


# ---------------------------------------------------------------------------
# Happy path — MaterializationResult populated correctly
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_returns_materialization_result(self, trivial_asset_key: str) -> None:
        result = materialize_asset(trivial_asset_key)
        assert isinstance(result, MaterializationResult)

    def test_result_has_all_fields(self, trivial_asset_key: str) -> None:
        # ADR-013 §2 + ADR-005 §1 + ADR-013 §3 (field-additive): verifies the shape did
        # not drift. ``checks`` landed 2026-05-13 with the contracts runtime
        # (v4.1 §15); v0.1 emits the empty-tuple default for assets with
        # no @nucleus.check bodies registered.
        result = materialize_asset(trivial_asset_key)
        for field in (
            "asset_key",
            "snapshot_id",
            "partition",
            "row_count",
            "duration_ms",
            "lineage_event_id",
            "materialized_at",
            "checks",
        ):
            assert hasattr(result, field), f"missing field: {field}"

    def test_asset_key_matches_registered_key(self, trivial_asset_key: str) -> None:
        result = materialize_asset(trivial_asset_key)
        assert result.asset_key == trivial_asset_key

    def test_duration_ms_is_non_negative(self, trivial_asset_key: str) -> None:
        # perf_counter delta cast to int can be 0 on a sub-millisecond body;
        # the contract is "non-negative", not "strictly positive."
        result = materialize_asset(trivial_asset_key)
        assert isinstance(result.duration_ms, int)
        assert result.duration_ms >= 0

    def test_materialized_at_is_recent_utc(self, trivial_asset_key: str) -> None:
        before = datetime.now(UTC) - timedelta(seconds=5)
        result = materialize_asset(trivial_asset_key)
        after = datetime.now(UTC) + timedelta(seconds=5)
        assert isinstance(result.materialized_at, datetime)
        assert result.materialized_at.tzinfo is not None
        assert before <= result.materialized_at <= after

    def test_v01_sentinels_when_no_warehouse_dir(self, trivial_asset_key: str) -> None:
        # When warehouse_dir is omitted the AMA skips the Iceberg commit step
        # and returns sentinel values per the deferred-commit design.
        # ADR-013 §2: snapshot_id and lineage_event_id are real values only
        # when the commit path is active; sentinels are the honest signal
        # that the downstream step has not been invoked.
        result = materialize_asset(trivial_asset_key)
        assert result.snapshot_id == ""
        assert result.lineage_event_id == ""
        assert result.row_count == 0

    def test_partition_propagated_to_result(self, trivial_asset_key: str) -> None:
        # ADR-013 §1 + AGENTS.md §7 vocabulary: the partition argument is
        # propagated into MaterializationResult.partition. The user prompt
        # asks for the asset body to see ``ctx.partition``, but v0.1 has no
        # real ctx wired yet (Phase C work); the result-level contract is
        # the testable surface today.
        result = materialize_asset(trivial_asset_key, partition="2026-05-13")
        assert result.partition == "2026-05-13"

    def test_none_partition_default(self, trivial_asset_key: str) -> None:
        result = materialize_asset(trivial_asset_key)
        assert result.partition is None

    def test_value_returning_asset_succeeds(self, value_returning_asset_key: str) -> None:
        # An asset body that returns a non-DataFrame value (e.g. int) should
        # not break the AMA. The value is not committable to Iceberg, so
        # sentinels are returned. No Dagster IO manager involved.
        result = materialize_asset(value_returning_asset_key)
        assert result.asset_key == value_returning_asset_key


# ---------------------------------------------------------------------------
# dry_run routing
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_true_succeeds(self, trivial_asset_key: str) -> None:
        # dry_run=True must not raise; the asset body still runs (side
        # effects are preserved) but no Iceberg commit occurs.
        result = materialize_asset(trivial_asset_key, dry_run=True)
        assert isinstance(result, MaterializationResult)
        assert result.asset_key == trivial_asset_key

    def test_dry_run_does_not_write_to_iceberg(
        self, trivial_asset_key: str, tmp_path: Path,
    ) -> None:
        # Even when warehouse_dir is provided, dry_run=True must not produce
        # an Iceberg snapshot.
        warehouse_dir = tmp_path / "warehouse"
        result = materialize_asset(trivial_asset_key, dry_run=True, warehouse_dir=warehouse_dir)
        assert result.snapshot_id == ""
        assert result.row_count == 0
        assert not (warehouse_dir / "catalog.db").exists(), (
            "dry_run must not touch the warehouse"
        )

    def test_real_run_without_warehouse_dir_uses_sentinels(
        self, trivial_asset_key: str,
    ) -> None:
        # When warehouse_dir is None the AMA skips the Iceberg commit step
        # and returns sentinel values (v0.1 deferred-commit behaviour).
        result = materialize_asset(trivial_asset_key, dry_run=False)
        assert result.snapshot_id == ""
        assert result.row_count == 0


# ---------------------------------------------------------------------------
# Registry miss
# ---------------------------------------------------------------------------


class TestRegistryMiss:
    def test_unknown_asset_raises_asset_not_found(self) -> None:
        with pytest.raises(NucleusAssetNotFound) as exc_info:
            materialize_asset("nope.missing")
        assert exc_info.value.asset == "nope.missing"
        assert "nope.missing" in exc_info.value.user_message

    def test_asset_not_found_message_does_not_leak_external_classnames(self) -> None:
        # v4.1 §6.4: even on the failure path the rendered string must not
        # contain external classnames.
        try:
            materialize_asset("nope.missing")
        except NucleusError as exc:
            rendered = exc.rendered().lower()
            assert "dagster" not in rendered
            assert "duckdb" not in rendered
            assert "polars" not in rendered
            assert "pyiceberg" not in rendered


# ---------------------------------------------------------------------------
# Asset body errors → translated NucleusError (no Dagster leak)
# ---------------------------------------------------------------------------


class TestAssetBodyErrorTranslation:
    def test_value_error_schema_translates_to_schema_error(self) -> None:
        @nucleus.asset("staging.bad_value")
        def staging_bad_value() -> None:
            raise ValueError("schema mismatch on column 'amount'")

        with pytest.raises(NucleusSchemaError) as exc_info:
            materialize_asset("staging.bad_value")
        # error_translation handler wraps the message; the key signal is
        # type-not-Dagster + the original message reaches the user.
        assert "schema mismatch" in exc_info.value.user_message.lower()

    def test_connection_error_translates_to_source_connection(self) -> None:
        @nucleus.asset("staging.bad_conn")
        def staging_bad_conn() -> None:
            raise ConnectionError("host db.local unreachable")

        with pytest.raises(NucleusSourceConnectionError) as exc_info:
            materialize_asset("staging.bad_conn")
        assert "unreachable" in exc_info.value.user_message.lower()

    def test_unknown_exception_falls_back_to_internal_error(self) -> None:
        @nucleus.asset("staging.zero_div")
        def staging_zero_div() -> None:
            raise ZeroDivisionError("divide by zero in body")

        with pytest.raises(NucleusInternalError) as exc_info:
            materialize_asset("staging.zero_div")
        # ZeroDivisionError has no specific registration in the translator;
        # translate() falls back to NucleusInternalError with the original
        # message preserved. No Dagster wrapper involved.
        assert "zero" in exc_info.value.user_message.lower()

    def test_error_rendered_does_not_leak_dagster_classnames(self) -> None:
        # v4.1 §6.4 + scripts/dagster_leak_check.py: the rendered user-facing
        # error must not carry any "dagster.X" substring (case-insensitive).
        @nucleus.asset("staging.fail_one")
        def staging_fail_one() -> None:
            raise RuntimeError("intentional failure for leak-check test")

        with pytest.raises(NucleusError) as exc_info:
            materialize_asset("staging.fail_one")
        rendered = exc_info.value.rendered().lower()
        assert "dagster" not in rendered
        assert "duckdb" not in rendered
        assert "polars" not in rendered
        assert "pyiceberg" not in rendered

    def test_translated_error_preserves_cause(self) -> None:
        @nucleus.asset("staging.fail_cause")
        def staging_fail_cause() -> None:
            raise ValueError("schema column missing")

        try:
            materialize_asset("staging.fail_cause")
        except NucleusError as exc:
            # The original exception is preserved via ``raise translated from exc``
            # in _invoke_asset_body so debug-mode --debug traces show the full chain.
            assert exc.__cause__ is not None


# ---------------------------------------------------------------------------
# Upstream deferred-mode defensive check
# ---------------------------------------------------------------------------


class TestUpstreamDefensive:
    def test_upstream_materialize_rejected_at_ama(self, trivial_asset_key: str) -> None:
        # SDK boundary rejects this eagerly; the AMA layer also rejects it
        # so direct callers (CLI, future ctx.agent.*) cannot bypass the
        # ADR-013 §NV #6 v0.1 limit.
        with pytest.raises(NucleusInternalError) as exc_info:
            materialize_asset(trivial_asset_key, upstream="materialize")
        assert "v0.3" in exc_info.value.user_message
        assert exc_info.value.asset == trivial_asset_key

    def test_upstream_validate_rejected_at_ama(self, trivial_asset_key: str) -> None:
        with pytest.raises(NucleusInternalError) as exc_info:
            materialize_asset(trivial_asset_key, upstream="validate")
        assert "v0.3" in exc_info.value.user_message


# ---------------------------------------------------------------------------
# Result shape invariants
# ---------------------------------------------------------------------------


class TestResultShapeInvariants:
    def test_result_is_frozen(self, trivial_asset_key: str) -> None:
        # ADR-013 §2 promises frozen=True so user code cannot mutate it.
        result = materialize_asset(trivial_asset_key)
        with pytest.raises(FrozenInstanceError):
            result.asset_key = "should.fail"

    def test_repr_contains_no_external_classnames(self, trivial_asset_key: str) -> None:
        result = materialize_asset(trivial_asset_key)
        rendered = repr(result).lower()
        assert "dagster" not in rendered
        assert "duckdb" not in rendered
        assert "polars" not in rendered
        assert "pyiceberg" not in rendered


# ---------------------------------------------------------------------------
# Iceberg commit path — real E2E (2026-05-14 beachhead E2E fix)
# ---------------------------------------------------------------------------


class TestIcebergCommit:
    """Verify the AMA writes a real Iceberg snapshot when warehouse_dir is given.

    These tests are the regression gate for the beachhead blocker where
    ``nucleus run example_asset`` was returning snapshot_id="-" and rows=0
    because Dagster's PickledObjectFilesystemIOManager was receiving the
    DataFrame instead of pyiceberg committing it. Option A fix: AMA owns
    the data-write path directly.
    """

    @pytest.fixture()
    def df_asset_key(self) -> str:
        """Register an asset that returns a small Polars DataFrame."""

        @nucleus.asset("test.tiny")
        def tiny_asset() -> pl.DataFrame:
            return pl.DataFrame({"id": [1, 2, 3], "label": ["a", "b", "c"]})

        return "test.tiny"

    def test_polars_df_commits_real_snapshot(
        self, df_asset_key: str, tmp_path: Path
    ) -> None:
        """Non-dry_run + warehouse_dir → real Iceberg snapshot_id + row_count."""
        warehouse_dir = tmp_path / "warehouse"
        result = materialize_asset(df_asset_key, warehouse_dir=warehouse_dir)

        assert result.snapshot_id != "", "snapshot_id must be non-empty after Iceberg commit"
        assert result.row_count == 3, "row_count must equal the DataFrame length"
        assert result.snapshot_id.isdigit() or len(result.snapshot_id) > 0

    def test_iceberg_table_written_to_warehouse(
        self, df_asset_key: str, tmp_path: Path
    ) -> None:
        """After commit the Iceberg metadata.json must exist under warehouse."""
        warehouse_dir = tmp_path / "warehouse"
        materialize_asset(df_asset_key, warehouse_dir=warehouse_dir)

        # pyiceberg SQL catalog stores metadata under <namespace>/<table>/
        metadata_dir = warehouse_dir / "test" / "tiny" / "metadata"
        assert metadata_dir.is_dir(), f"Expected Iceberg metadata dir at {metadata_dir}"
        json_files = list(metadata_dir.glob("*.json"))
        assert json_files, "At least one metadata.json must be written"

    def test_catalog_db_created(self, df_asset_key: str, tmp_path: Path) -> None:
        """The SQLite catalog file must be created by the commit."""
        warehouse_dir = tmp_path / "warehouse"
        materialize_asset(df_asset_key, warehouse_dir=warehouse_dir)
        assert (warehouse_dir / "catalog.db").is_file()

    def test_dry_run_with_df_asset_does_not_commit(
        self, df_asset_key: str, tmp_path: Path
    ) -> None:
        """dry_run=True must not write to Iceberg even for DataFrame assets."""
        warehouse_dir = tmp_path / "warehouse"
        result = materialize_asset(df_asset_key, dry_run=True, warehouse_dir=warehouse_dir)
        assert result.snapshot_id == ""
        assert result.row_count == 0
        assert not (warehouse_dir / "catalog.db").exists()

    def test_no_dagster_classnames_in_result(
        self, df_asset_key: str, tmp_path: Path
    ) -> None:
        """v4.1 §6.4 regression: MaterializationResult must contain no Dagster strings."""
        warehouse_dir = tmp_path / "warehouse"
        result = materialize_asset(df_asset_key, warehouse_dir=warehouse_dir)
        rendered = repr(result).lower()
        forbidden = [
            "dagster",
            "pickledobjectfilesystemiomanager",
            "__ephemeral_asset_job__",
            "opexecutioncontext",
            "dagsterinstance",
        ]
        for term in forbidden:
            assert term not in rendered, f"Forbidden term {term!r} leaked into result repr"
