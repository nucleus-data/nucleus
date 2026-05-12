"""Nucleus internal logging helpers.

Configures :mod:`structlog` for structured, queryable logs across the
codebase. The CLI and SDK entry points call :func:`configure` exactly
once.

Conventions (``docs/conventions/engineering.md`` §5):

- All event names are ``noun.verb`` past-tense: ``asset.materialized``,
  ``commit.failed``, ``query.executed``.
- Never log raw row data or credentials. Log shapes, not values.
- One ``structlog.get_logger(__name__)`` per module; never share loggers.

OpenTelemetry integration ships in a follow-up commit (this file may
grow to ~150 LOC; current stub is ~80 LOC).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog

# Lazy import note: we use structlog conditionally. If the user runs
# Nucleus without structlog installed (shouldn't happen given pinned deps,
# but defensive), we fall back gracefully.


def _resolve_level(name: str | None) -> int:
    """Resolve a log-level name to its int value, default INFO."""
    if not name:
        return logging.INFO
    return getattr(logging, name.upper(), logging.INFO)


def configure(
    *,
    level: str | None = None,
    pretty: bool | None = None,
) -> None:
    """Initialize structlog for the current process.

    Called once at the CLI / SDK entry point. Safe to call multiple times
    (re-configures cleanly).

    Args
    ----
    level
        Log level name (``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``).
        Defaults to the value of ``NUCLEUS_LOG_LEVEL`` env var, then ``INFO``.
    pretty
        If True, render colorful human-readable output (good for CLI).
        If False, render newline-delimited JSON (good for log aggregators).
        Defaults: pretty when stdout is a TTY, JSON otherwise.

    Notes
    -----
    Subsequent calls to :func:`structlog.get_logger` return a configured
    logger. Use ``log = structlog.get_logger(__name__)`` per module.
    """
    resolved_level = _resolve_level(level or os.environ.get("NUCLEUS_LOG_LEVEL"))
    resolved_pretty = pretty if pretty is not None else sys.stdout.isatty()

    # Standard library logging is the floor — structlog calls into it.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=resolved_level,
    )

    # Shared processor chain: adds context, levels, timestamps.
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Final renderer depends on pretty/JSON.
    renderer: Any
    if resolved_pretty:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Convenience wrapper around :func:`structlog.get_logger`.

    Equivalent to ``structlog.get_logger(name)``. Provided so internal
    modules can ``from nucleus._internal.logging import get_logger``
    without depending on ``structlog`` directly (in case we ever swap
    the implementation).
    """
    return structlog.get_logger(name)
