"""Nucleus — Modern composable data engineering platform.

This is the top-level package. End users typically interact with the SDK
through :mod:`nucleus.ctx` and the CLI through ``nucleus`` command.

Public surface (stable from v1.0):
    - :class:`nucleus.errors.NucleusError`         the base error type
    - :mod:`nucleus.ctx`                            the public SDK
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
# Single source of truth: this string.
# When bumping, also update CHANGELOG.md and pyproject.toml.
__version__: str = "0.0.0"

# Re-export the error base so users can do ``except nucleus.NucleusError``.
# All other surface lives under :mod:`nucleus.ctx`.
from nucleus.errors import NucleusError

__all__ = [
    "__version__",
    "NucleusError",
]
