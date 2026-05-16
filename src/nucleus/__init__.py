"""Nucleus — Ship data products from a laptop.

A local-first Python SDK + CLI for building Iceberg-native pipelines and
analytics stacks. Built on open Apache foundations, AI-ready by design.
Graduates cleanly to any Iceberg catalog (Polaris, Lakekeeper, Unity, R2)
when users outgrow their laptop.

This is the top-level package. End users typically interact with the SDK
through :mod:`nucleus.sdk` (decorators + ``materialize``) +
:mod:`nucleus.ctx` (per-asset runtime), and with the CLI through the
``nucleus`` command.

Public surface (stable from v1.0):
    - :class:`nucleus.errors.NucleusError`         the base error type
    - :func:`nucleus.asset`                         the asset decorator
    - :func:`nucleus.check`                         the quality-check decorator
    - :func:`nucleus.materialize`                   ADR-013 entry point
    - :class:`nucleus.MaterializationResult`        ADR-013 §2 return type
    - :class:`nucleus.AssetRef`                     ctx SDK §3.1 reference type
    - :class:`nucleus.CheckResult`                  asset model spec §10 record
    - :mod:`nucleus.ctx`                            the per-asset runtime
    - :mod:`nucleus.cli`                            the operator CLI

Internal (subject to change without notice):
    - :mod:`nucleus._internal`                      shared toolbox
    - :mod:`nucleus.physics`                        format adapters (Iceberg, Arrow, Parquet)
    - :mod:`nucleus.engines`                        engine adapters (DuckDB, Polars, ...)
    - :mod:`nucleus.coordination`                   Dagster wrappers + error translation
    - :mod:`nucleus.intelligence`                   AI Layer (post v0.2)

See:
    - ``AGENTS.md``                                 universal contributor rules (11 constraints)
    - ``docs/architecture/C4_container.md``         the layer breakdown
    - ``docs/conventions/engineering.md``           the engineering conventions

Version policy:
    - ``0.0.x``    pre-Heartbeat / Heartbeat (this state)
    - ``0.1.x``    Tier 1 Foundation (beachhead-ready)
    - ``1.0.x``    GA — ctx SDK signatures stable per semver
"""

from __future__ import annotations

# Version exposed for ``nucleus --version`` and ``nucleus.__version__``.
# Single source of truth: this string. When bumping, also update CHANGELOG.md
# and pyproject.toml.
#
# Stability: Frozen — version reporting is part of the v1.0 stable contract
# (PEP 396 / standard module attribute). This tier is documentation-only
# because ``scripts/check_api_stability.py`` (per ADR-005 §Verification plan)
# does not yet support tier extraction from module-level ``AnnAssign`` nodes
# — the regex only reads docstrings on ``ClassDef`` / ``FunctionDef`` /
# ``Module`` (see ``scripts/check_api_stability.py`` ``_extract_tier``).
# Consequently ``__version__`` is accessed solely as a module attribute
# (``nucleus.__version__``) and is intentionally NOT listed in ``__all__``
# — also the standard Python idiom (numpy, pandas, etc. all omit
# ``__version__`` from ``__all__`` so ``from nucleus import *`` does not
# clobber an importer's own ``__version__``). Tracked as a founder review
# item alongside ADR-005 acceptance.
__version__: str = "0.2.0"

# Stability: Frozen — re-export of the error base for the idiomatic
# ``except nucleus.NucleusError`` pattern. The class itself carries
# ``# Stability: Frozen`` in its docstring; that is the locus the script
# reads. This comment is documentation-only.
from nucleus.errors import NucleusError

# Re-export the v0.1 SDK surface per docs/specs/nucleus_ctx_sdk_spec.md §12 frozen
# surface and ADR-013 §1+§2. Each underlying definition carries its own
# ``# Stability: Beta`` marker (per ADR-005 §2) which
# ``scripts/check_api_stability.py`` reads when validating the public
# surface — it walks one hop via ``ast.ImportFrom``, so the imports below
# point at the leaf modules where each symbol is defined (importing via
# the intermediate ``nucleus.sdk`` package would resolve to the package
# ``__init__`` whose body only re-imports, leaving the script unable to
# find the actual definition node).
from nucleus.sdk.decorators import asset, check
from nucleus.sdk.materialize import materialize
from nucleus.sdk.results import AssetRef, CheckResult, MaterializationResult

__all__ = [
    "AssetRef",
    "CheckResult",
    "MaterializationResult",
    "NucleusError",
    "asset",
    "check",
    "materialize",
]
