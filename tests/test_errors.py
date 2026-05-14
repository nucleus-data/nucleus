"""Tests for :mod:`nucleus.errors`.

These tests verify the three-field contract (``user_message`` /
``fix_hint`` / ``docs_url``) and the rendering behavior that the CLI
relies on.

These are also the FIRST tests in the repo — they prove the toolchain
(pyproject, pytest, src/ layout) is wired correctly.
"""

from __future__ import annotations

import pytest

import nucleus.errors as nucleus_errors
from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusAssetNotMaterialized,
    NucleusError,
    NucleusInternalError,
    NucleusSchemaError,
    NucleusSourceConnectionError,
)

ERRORS_ALL = nucleus_errors.__all__

# ============================================================================
# Three-field contract
# ============================================================================


class TestThreeFieldContract:
    """Every error must carry user_message + fix_hint + docs_url."""

    def test_minimal_construction(self) -> None:
        err = NucleusError("something broke", fix_hint="restart it")
        assert err.user_message == "something broke"
        assert err.fix_hint == "restart it"
        assert err.docs_url.startswith("https://nucleus.dev/errors/")

    def test_explicit_docs_url_wins_over_default(self) -> None:
        err = NucleusError(
            "x",
            fix_hint="y",
            docs_url="https://example.com/custom",
        )
        assert err.docs_url == "https://example.com/custom"

    def test_subclass_picks_up_default_docs_url(self) -> None:
        err = NucleusAssetNotFound(
            "asset 'foo' not found",
            fix_hint="define it",
        )
        assert err.docs_url == "https://nucleus.dev/errors/asset-not-found"

    def test_whitespace_is_trimmed(self) -> None:
        err = NucleusError(
            "  msg with padding  \n",
            fix_hint="\t  hint  \n",
            asset="  raw.orders  ",
        )
        assert err.user_message == "msg with padding"
        assert err.fix_hint == "hint"
        assert err.asset == "raw.orders"

    def test_fix_hint_can_be_empty(self) -> None:
        # Allowed because not every error has an actionable fix.
        err = NucleusInternalError("internal invariant violated")
        assert err.fix_hint == ""

    def test_asset_is_optional(self) -> None:
        err = NucleusError("x", fix_hint="y")
        assert err.asset is None


# ============================================================================
# Category & rendering
# ============================================================================


class TestCategory:
    """The ``category`` attribute drives CLI output headers."""

    def test_category_strips_nucleus_prefix(self) -> None:
        err = NucleusAssetNotFound("x", fix_hint="y")
        assert err.category == "AssetNotFound"

    def test_category_for_base_class(self) -> None:
        # Base class is special-cased: category = "Error"
        err = NucleusError("x", fix_hint="y")
        assert err.category == "Error"


class TestRendering:
    """The ``rendered()`` output is the user-facing message."""

    def test_render_basic(self) -> None:
        err = NucleusAssetNotFound(
            "asset 'staging.foo' is not defined",
            fix_hint="add @nucleus.asset to its definition",
            asset="marts.daily_revenue",
        )
        out = err.rendered()
        assert "AssetNotFound" in out
        assert "marts.daily_revenue" in out
        assert "asset 'staging.foo' is not defined" in out
        assert "add @nucleus.asset to its definition" in out
        assert "https://nucleus.dev/errors/asset-not-found" in out

    def test_render_no_fix_hint(self) -> None:
        err = NucleusInternalError("invariant violated")
        out = err.rendered()
        assert "invariant violated" in out
        # No "How to fix:" header when fix_hint is empty.
        assert "How to fix" not in out

    def test_render_no_dagster_leak(self) -> None:
        """Sanity check: nothing in rendered() exposes Dagster types.

        This is a smoke test for v4.1 §6.4. Real check is
        scripts/dagster_leak_check.py running on CI artifacts.
        """
        err = NucleusAssetNotFound("missing", fix_hint="add it")
        assert "dagster" not in err.rendered().lower()

    def test_render_debug_includes_cause(self) -> None:
        inner = ValueError("inner detail")
        err = NucleusInternalError("outer message", cause=inner)
        debug_out = err.rendered(debug=True)
        assert "outer message" in debug_out
        assert "ValueError" in debug_out
        assert "inner detail" in debug_out

    def test_render_default_excludes_cause(self) -> None:
        inner = ValueError("inner detail")
        err = NucleusInternalError("outer message", cause=inner)
        out = err.rendered()
        assert "inner detail" not in out


# ============================================================================
# Exception chaining
# ============================================================================


class TestExceptionChaining:
    """We use ``__cause__`` so tracebacks show the original exception."""

    def test_cause_chains_via___cause__(self) -> None:
        inner = ValueError("original")
        err = NucleusSchemaError("schema mismatch", fix_hint="fix it", cause=inner)
        assert err.__cause__ is inner

    def test_no_cause_means_no_chain(self) -> None:
        err = NucleusSchemaError("x", fix_hint="y")
        assert err.__cause__ is None

    def test_caught_as_nucleus_error_base(self) -> None:
        """Any specific NucleusError is catchable as NucleusError."""
        with pytest.raises(NucleusError):
            raise NucleusSourceConnectionError(
                "cannot reach postgres",
                fix_hint="check host/port",
            )

    def test_distinct_subclasses_are_independent(self) -> None:
        with pytest.raises(NucleusAssetNotFound):
            raise NucleusAssetNotFound("x", fix_hint="y")

        with pytest.raises(NucleusAssetNotMaterialized):
            raise NucleusAssetNotMaterialized("x", fix_hint="y")


# ============================================================================
# Public surface
# ============================================================================


class TestPublicSurface:
    """The error module's ``__all__`` is part of the stable public API."""

    def test_base_class_in_all(self) -> None:
        assert "NucleusError" in ERRORS_ALL

    def test_every_exported_name_resolves(self) -> None:
        import nucleus.errors as mod

        for name in ERRORS_ALL:
            assert hasattr(mod, name), f"{name} is in __all__ but not defined"
            obj = getattr(mod, name)
            assert isinstance(obj, type), f"{name} should be a class"
            assert issubclass(obj, Exception), f"{name} should be an Exception"

    def test_every_subclass_overrides_docs_url(self) -> None:
        import nucleus.errors as mod

        base_default = NucleusError.DEFAULT_DOCS_URL
        for name in ERRORS_ALL:
            if name == "NucleusError":
                continue
            cls = getattr(mod, name)
            assert base_default != cls.DEFAULT_DOCS_URL, (
                f"{name} should override DEFAULT_DOCS_URL with a specific slug"
            )

    def test_renderable_for_every_subclass(self) -> None:
        """Every error type can be constructed + rendered without crashing."""
        import nucleus.errors as mod

        for name in ERRORS_ALL:
            cls = getattr(mod, name)
            err = cls("test message", fix_hint="test hint")
            out = err.rendered()
            assert "test message" in out
            assert err.docs_url in out


# ============================================================================
# Top-level export
# ============================================================================


def test_top_level_nucleus_exports_nucleus_error() -> None:
    """``import nucleus`` should expose NucleusError directly."""
    import nucleus

    assert nucleus.NucleusError is NucleusError
    assert nucleus.__version__  # truthy string
