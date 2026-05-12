"""Nucleus error system — the user-facing exception types.

All errors that reach Nucleus end-users are subclasses of
:class:`NucleusError`. Internal exceptions (Dagster, DuckDB, PyIceberg,
Polars, psycopg, ...) are translated at the ``coordination/`` boundary
by the Error Translation Layer — see
``docs/architecture/sequence_error_translation.md``.

The three-field contract
------------------------
Every NucleusError instance carries:

    user_message    What went wrong, in *user* language. No internal types,
                    no Python tracebacks, no file paths from our codebase.
    fix_hint        A concrete suggestion: "Run X first", "Add Y", etc.
                    If we cannot suggest a fix, this field is empty string.
    docs_url        URL on https://nucleus.dev/errors/ that explains the error.

These three fields are how we turn errors into UX (per the architecture
v4.1 §6.4). Without all three, the error is a riddle. The optional
``asset`` and ``cause`` fields complete the 5-field shape.

NUC-XXX codes deferred
----------------------
Numeric stable error codes (the ``NUC-XXX`` scheme mentioned in some older
notes) are **explicitly deferred to post-v0.5** — v0.1 uses the class name
+ docs slug as the stable identifier (e.g. ``NucleusCommitConflictError``
with slug ``/errors/commit-conflict``). See v4.1 §6.4.

Adding a new error type
-----------------------
1. Subclass :class:`NucleusError`.
2. Override ``DEFAULT_DOCS_URL`` with the appropriate slug.
3. Document the trigger in the docstring.
4. Update ``docs/architecture/sequence_error_translation.md`` translation table.
5. Add a test in ``tests/test_errors.py``.

Public surface
--------------
Everything in :data:`__all__` is part of the **stable** public surface
(``nucleus_architecture_v4.1.md`` §13.1). Renaming / removing requires an ADR.
"""

from __future__ import annotations

import textwrap
from typing import Final

# Default docs base. Subclasses use specific slugs.
# When we publish nucleus.dev, this is the live URL prefix.
_DOCS_BASE: Final[str] = "https://nucleus.dev/errors"


class NucleusError(Exception):
    """Base class for all user-facing Nucleus errors.

    Carries a user-helpful triplet (user_message + fix_hint + docs_url),
    plus optional ``asset`` (the asset name involved, if any) and
    ``cause`` (the original exception that was translated, if any).

    The ``str()`` representation is the fully rendered user-facing message
    — what shows up in CLI output by default. The original exception is
    available via the standard Python ``__cause__`` mechanism for debug
    inspection but is not surfaced in the formatted output unless
    ``rendered(debug=True)`` is called explicitly.
    """

    # Subclasses MUST override this with a stable slug like "/asset-not-found".
    DEFAULT_DOCS_URL: str = f"{_DOCS_BASE}/generic"

    # Used in CLI rendering as a short tag (e.g. "AssetNotFound").
    # Defaults to the class name stripped of the "Nucleus" prefix.
    CATEGORY: str = ""

    def __init__(
        self,
        user_message: str,
        *,
        fix_hint: str = "",
        docs_url: str | None = None,
        asset: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        # Strip whitespace defensively — many sources of these strings.
        self.user_message: Final[str] = user_message.strip()
        self.fix_hint: Final[str] = fix_hint.strip()
        self.docs_url: Final[str] = (docs_url or self.DEFAULT_DOCS_URL).strip()
        self.asset: Final[str | None] = asset.strip() if asset else None

        # Chain to the original cause so debuggers can walk the chain.
        # Using __cause__ (not __context__) so it shows the "The above
        # exception was the direct cause of the following exception"
        # message in tracebacks.
        super().__init__(self.user_message)
        if cause is not None:
            self.__cause__ = cause

    @property
    def category(self) -> str:
        """Short tag used in CLI output (e.g. ``"AssetNotFound"``)."""
        if self.CATEGORY:
            return self.CATEGORY
        name = type(self).__name__
        return name[len("Nucleus") :] if name.startswith("Nucleus") else name

    def rendered(self, *, debug: bool = False) -> str:
        """Format the full user-facing error message.

        The CLI calls this. The default output is clean for end users:
        no Python tracebacks, no Nucleus internal file paths. When
        ``debug=True``, the original cause's representation is appended.
        """
        parts: list[str] = []

        # Header line: category + asset (if known)
        header = self.category
        if self.asset:
            header = f"{header} in asset '{self.asset}'"
        parts.append(header)
        parts.append("")  # blank line

        # User message — indented for readability.
        parts.append(textwrap.indent(self.user_message, "  "))

        # Fix hint — present when non-empty.
        if self.fix_hint:
            parts.append("")
            parts.append("  How to fix:")
            parts.append(textwrap.indent(self.fix_hint, "    "))

        # Docs URL.
        parts.append("")
        parts.append(f"  Docs: {self.docs_url}")

        # Debug info — only when requested.
        if debug and self.__cause__ is not None:
            parts.append("")
            parts.append("  Original cause (debug):")
            parts.append(
                textwrap.indent(
                    f"{type(self.__cause__).__name__}: {self.__cause__}",
                    "    ",
                )
            )

        return "\n".join(parts)

    def __repr__(self) -> str:
        # Useful for tests + interactive REPL.
        return (
            f"{type(self).__name__}("
            f"user_message={self.user_message!r}, "
            f"fix_hint={self.fix_hint!r}, "
            f"docs_url={self.docs_url!r}, "
            f"asset={self.asset!r})"
        )


# ============================================================================
# Asset / catalog errors
# ============================================================================


class NucleusAssetNotFound(NucleusError):
    """An asset name was referenced but is not defined in the project.

    Distinguish from :class:`NucleusAssetNotMaterialized`: an asset can
    be DEFINED (decorated with ``@nucleus.asset``) but not yet MATERIALIZED
    (computed and stored).
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/asset-not-found"


class NucleusAssetNotMaterialized(NucleusError):
    """An asset is defined but has never been materialized.

    Typically surfaced when downstream code tries to read an asset that
    was never run. Fix is usually ``nucleus run <upstream-asset>``.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/not-materialized"


class NucleusInvalidAssetDefinition(NucleusError):
    """``@nucleus.asset`` was used with invalid configuration.

    Examples: wrong name pattern, schema/return-type mismatch, missing deps.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/invalid-asset"


class NucleusCatalogError(NucleusError):
    """A problem with the Iceberg catalog (filesystem / SQL / REST).

    Examples: catalog path not writable, namespace missing, catalog backend
    unreachable.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/catalog"


# ============================================================================
# Schema / type errors
# ============================================================================


class NucleusSchemaError(NucleusError):
    """The data did not match the declared schema.

    Examples: column missing, type mismatch, declared NOT NULL but got NULL.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/schema"


class NucleusSchemaEvolutionError(NucleusError):
    """A schema change is not a valid Iceberg evolution.

    Examples: type narrowing, nullable → not-nullable, removing partition key.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/schema-evolution"


class NucleusUnsupportedTypeError(NucleusError):
    """A column type is not yet supported by Nucleus.

    See ``docs/patterns/type_mapping.md`` for the supported set.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/unsupported-type"


# ============================================================================
# Materialization / commit errors
# ============================================================================


class NucleusCommitConflictError(NucleusError):
    """Concurrent commit attempted to write to the same table.

    The fix is usually to retry (the AMA does this automatically up to 3
    times). If user-facing, it means retries were exhausted.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/commit-conflict"


class NucleusCommitUnknownError(NucleusError):
    """A commit failed mid-write and we cannot determine its status.

    Network failure during the metadata pointer swap is the typical
    cause. Manual recovery via ``nucleus catalog inspect`` is required.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/commit-unknown"


class NucleusEmptyAssetError(NucleusError):
    """An asset produced no rows (sometimes intentional, sometimes a bug).

    Lifted to an error only when the asset's contract says
    ``allow_empty=False`` (the default for assets with explicit schemas).
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/empty-asset"


# ============================================================================
# Engine / execution errors
# ============================================================================


class NucleusSQLSyntaxError(NucleusError):
    """A SQL string failed to parse.

    Includes line/column position when available.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/sql-syntax"


class NucleusEngineError(NucleusError):
    """An engine (DuckDB / Polars / DataFusion) failed during execution.

    Generic bucket; more specific subclasses preferred when the cause is known.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/engine"


# ============================================================================
# Source / IO errors
# ============================================================================


class NucleusSourceConnectionError(NucleusError):
    """Could not connect to a data source (Postgres, MySQL, ...).

    Typical causes: wrong host/port, network blocked, credentials wrong.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/source-connection"


class NucleusSourceNotFound(NucleusError):
    """A source table / view / file was referenced but does not exist."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/source-not-found"


class NucleusSourceAuthError(NucleusError):
    """The source rejected our credentials or denied access to the object."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/source-auth"


class NucleusIOError(NucleusError):
    """A read/write to local FS or object storage failed."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/io"


class NucleusPermissionError(NucleusError):
    """A filesystem or storage operation was denied due to permissions."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/permission"


# ============================================================================
# Config & runtime errors
# ============================================================================


class NucleusConfigError(NucleusError):
    """A configuration value is missing, malformed, or contradictory."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/config"


class NucleusAuthError(NucleusError):
    """Authentication failed (cloud credentials expired, OIDC token invalid, ...)."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/auth"


class NucleusResourceError(NucleusError):
    """An operation exceeded a resource limit (memory, disk, file descriptors)."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/resource"


class NucleusTimeoutError(NucleusError):
    """An operation exceeded its time budget."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/timeout"


class NucleusNetworkError(NucleusError):
    """A network operation failed (DNS, TCP, TLS, HTTP)."""

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/network"


class NucleusRunCancelled(NucleusError):
    """A run was cancelled by the user (Ctrl+C / SIGTERM).

    Clean exit; not a true error but useful as a typed signal.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/cancelled"


# ============================================================================
# Catch-all
# ============================================================================


class NucleusInternalError(NucleusError):
    """An internal Nucleus invariant was violated — this is a bug in Nucleus.

    Surfaced when the Error Translation Layer has no specific translator
    for an underlying exception type. Includes instructions for filing a
    bug report.
    """

    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/internal"


__all__ = [
    "NucleusError",
    # Asset / catalog
    "NucleusAssetNotFound",
    "NucleusAssetNotMaterialized",
    "NucleusInvalidAssetDefinition",
    "NucleusCatalogError",
    # Schema / type
    "NucleusSchemaError",
    "NucleusSchemaEvolutionError",
    "NucleusUnsupportedTypeError",
    # Materialization / commit
    "NucleusCommitConflictError",
    "NucleusCommitUnknownError",
    "NucleusEmptyAssetError",
    # Engine / execution
    "NucleusSQLSyntaxError",
    "NucleusEngineError",
    # Source / IO
    "NucleusSourceConnectionError",
    "NucleusSourceNotFound",
    "NucleusSourceAuthError",
    "NucleusIOError",
    "NucleusPermissionError",
    # Config & runtime
    "NucleusConfigError",
    "NucleusAuthError",
    "NucleusResourceError",
    "NucleusTimeoutError",
    "NucleusNetworkError",
    "NucleusRunCancelled",
    # Catch-all
    "NucleusInternalError",
]
