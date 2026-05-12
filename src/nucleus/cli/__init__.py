"""The nucleus CLI — operator surface (L4).

The CLI is built on Typer (which itself wraps Click). Each command is
a thin wrapper that constructs the appropriate ``ctx`` call and renders
output via ``rich``.

Entry point (declared in ``pyproject.toml``):
    nucleus = "nucleus.cli.main:app"

Per ``nucleus_architecture_v4.1.md`` §13.1, the CLI surface is part of the
stable public API. Adding / changing commands follows the same semver
discipline as the ``ctx`` SDK.

See:
    - ``nucleus_cli_spec.md``                        full CLI specification
    - ``docs/architecture/C4_container.md`` §3.2     command list

This package's content arrives progressively:
    - Tier 0:   ``--version``, ``--help`` only
    - Tier 1:   ``up`` / ``down`` / ``init`` / ``run`` / ``inspect`` / ``lineage``
    - Tier 2:   ``workbench`` (launch web IDE)
    - Tier 3+:  ``upgrade``, additional inspection tools
"""

from __future__ import annotations
