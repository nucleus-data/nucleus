"""Bundled project templates for ``nucleus init`` (L4 — operator surface).

This package ships the on-disk skeleton(s) that ``nucleus init`` copies
into a new project directory. Per ``docs/specs/nucleus_cli_spec.md`` §3.1, v0.1
ships a single template family:

    nucleus.templates.v01    canonical "default" template (alias: ``default``)

Files under ``v01/`` are read at scaffolding time via
``importlib.resources.files(...)`` and rendered with Python's
``str.format()`` — the only template variables are ``{project_name}``
and ``{today}`` (per the per-feature workflow note from the founder
2026-05-13: keep it simpler than Jinja for v0.1).

To add a v0.3+ template (deferred — see ``docs/specs/nucleus_cli_spec.md`` §3.1
``--template`` flag), add a sibling subpackage and wire its key in
``nucleus.cli.main:_TEMPLATE_KEYS``.
"""

from __future__ import annotations
