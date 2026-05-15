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

Stable error codes (NEXxxx scheme per ADR-006)
----------------------------------------------
Every concrete subclass declares ``error_code: ClassVar[str] = "NEXxxx"``
matching ``^NE[1-5]\\d{3}$``. Codes are PERMANENT from first release —
renaming or recycling forbidden. Layer prefix maps to v4.1 §3.1 with a
+1 offset so ``NE0xxx`` is reserved (uninitialized / null in CLI output):

    NE1xxx  L0 Physics (Iceberg, Parquet, Arrow, S3, network IO)
    NE2xxx  L1 Engines (DuckDB, Polars; compute, parse/bind/plan)
    NE3xxx  L2 Coordination (asset graph, Dagster wrap, contracts, lineage)
    NE4xxx  L3 Intelligence (AI Copilot v0.2+, ``ctx.agent`` v0.5+)
    NE5xxx  L4 Experience (``ctx`` SDK, CLI, Workbench, Marimo)

Codes are unique per subclass. Multiple handlers MAY route to the same
subclass and therefore share the same code (e.g. ``pyiceberg.CommitFailedException``
+ ``duckdb.TransactionException`` both -> ``NucleusCommitConflictError`` ->
``NE1002``). Enforced by ``scripts/check_error_codes.py``. See
``docs/decisions/ADR-006-nucleus-error-code-numbering.md``.

Adding a new error type
-----------------------
1. Subclass :class:`NucleusError`.
2. Assign a unique ``error_code: ClassVar[str]`` from the correct layer band.
3. Override ``DEFAULT_DOCS_URL`` with the appropriate slug.
4. Tag the docstring with a stability tier (``# Stability: Stable`` by default).
5. Document the trigger in the docstring.
6. Update ``docs/architecture/sequence_error_translation.md`` translation table.
7. Add a test in ``tests/test_errors.py``.

Public surface
--------------
Everything in :data:`__all__` is part of the **stable** public surface
(``nucleus_architecture_v4.1.md`` §13.1). Renaming / removing requires an ADR.
Stability tiers per ADR-005 are encoded in each class docstring.
"""

from __future__ import annotations

import textwrap
from typing import ClassVar, Final

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

    # Stability: Frozen
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

    Layer (ADR-006 §1): L2 Coordination — asset graph concern even when
    the underlying ``duckdb.CatalogException`` is raised at L1 (semantic
    over source per ADR-006 §Decision).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE3002"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/asset-not-found"


class NucleusAssetNotMaterialized(NucleusError):
    """An asset is defined but has never been materialized.

    Typically surfaced when downstream code tries to read an asset that
    was never run. Fix is usually ``nucleus run <upstream-asset>``.

    Layer (ADR-006 §1): L2 Coordination — asset-graph state. Source
    exception is typically ``pyiceberg.NoSuchTableError`` (L0).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE3003"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/not-materialized"


class NucleusInvalidAssetDefinition(NucleusError):
    """``@nucleus.asset`` was used with invalid configuration.

    Examples: wrong name pattern, schema/return-type mismatch, missing deps.

    Layer (ADR-006 §1): L2 Coordination — asset-graph definition.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE3004"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/invalid-asset"


class NucleusCatalogError(NucleusError):
    """A problem with the Iceberg catalog (filesystem / SQL / REST).

    Examples: catalog path not writable, namespace missing, catalog backend
    unreachable.

    Layer (ADR-006 §1): L0 Physics — Iceberg catalog is the durable-truth
    substrate.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1007"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/catalog"


# ============================================================================
# Schema / type errors
# ============================================================================


class NucleusSchemaError(NucleusError):
    """The data did not match the declared schema.

    Examples: column missing, type mismatch, declared NOT NULL but got NULL.

    Layer (ADR-006 §1): L1 Engines — discovered during engine bind/plan
    (DuckDB ``BinderException``, Polars ``SchemaError``/``ColumnNotFoundError``,
    Dagster inner ``TypeError``/``ValueError`` mentioning schema).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE2001"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/schema"


class NucleusSchemaEvolutionError(NucleusError):
    """A schema change is not a valid Iceberg evolution.

    Examples: type narrowing, nullable -> not-nullable, removing partition key.

    Layer (ADR-006 §1): L0 Physics — Iceberg schema-evolution rule
    (``pyiceberg.ValidationError``).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1004"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/schema-evolution"


class NucleusUnsupportedTypeError(NucleusError):
    """A column type is not yet supported by Nucleus.

    See ``docs/patterns/type_mapping.md`` for the supported set.

    Layer (ADR-006 §1): L1 Engines — discovered during engine type-mapping.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE2004"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/unsupported-type"


# ============================================================================
# Materialization / commit errors
# ============================================================================


class NucleusCommitConflictError(NucleusError):
    """Concurrent commit attempted to write to the same asset.

    The fix is usually to retry (the AMA does this automatically up to 3
    times). If user-facing, it means retries were exhausted.

    Layer (ADR-006 §1): L0 Physics — Iceberg commit conflict
    (``pyiceberg.CommitFailedException``). Per H10 founder ratification
    (Option a), engine-transaction conflicts (``duckdb.TransactionException``)
    route to the SAME class and code; user-facing semantics ("concurrent
    write conflicted with yours") are identical even though the source
    layer differs.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1002"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/commit-conflict"


class NucleusCommitUnknownError(NucleusError):
    """A commit failed mid-write and we cannot determine its status.

    Network failure during the metadata pointer swap is the typical
    cause. Manual recovery via ``nucleus catalog inspect`` is required.

    Layer (ADR-006 §1): L0 Physics —
    ``pyiceberg.CommitStateUnknownException``.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1003"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/commit-unknown"


class NucleusEmptyAssetError(NucleusError):
    """An asset produced no rows (sometimes intentional, sometimes a bug).

    Lifted to an error only when the asset's contract says
    ``allow_empty=False`` (the default for assets with explicit schemas).

    Layer (ADR-006 §1): L2 Coordination — contract enforcement.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE3006"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/empty-asset"


class NucleusLineageEmissionError(NucleusError):
    """OpenLineage event emission failed for an asset materialization.

    Surfaced when writing a START/COMPLETE/FAIL RunEvent to the NDJSON
    lineage log raises (e.g. filesystem permission denied, disk full,
    malformed event payload). Per the AMA's lineage hook boundary
    (:mod:`nucleus.coordination.lineage`) this error is **never**
    propagated to the user - it is constructed, logged at WARN, and
    swallowed so a lineage failure cannot fail the underlying
    materialization. Per ``docs/research/openlineage.md`` section 5.1
    OL emission lives at v4.1 section 6.2 step 4 (post-write).

    Layer (ADR-006 section 1): L2 Coordination - Nucleus owns the
    OpenLineage emit step (Tier 0 immortal substrate; no swap target).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE3010"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/lineage-emission"


# ============================================================================
# Engine / execution errors
# ============================================================================


class NucleusSQLSyntaxError(NucleusError):
    """A SQL string failed to parse.

    Includes line/column position when available.

    Layer (ADR-006 §1): L1 Engines — parser/binder
    (``duckdb.ParserException``).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE2002"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/sql-syntax"


class NucleusEngineError(NucleusError):
    """An engine (DuckDB / Polars / DataFusion) failed during execution.

    Generic bucket; more specific subclasses preferred when the cause is known.

    Layer (ADR-006 §1): L1 Engines — execution-time engine failure.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE2005"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/engine"


class NucleusCheckExecutionError(NucleusError):
    """A registered ``@nucleus.check`` body raised during materialization.

    Layer (ADR-006 §1): **L2 Coordination** — per ADR-006 §1 the
    "contracts" capability is explicitly enumerated under the NE3xxx
    range (alongside asset graph, Dagster wrap, lineage, and the
    translator itself). The check body is registered by the SDK, but
    its *execution* is owned by the coordination-layer contracts
    runtime (:mod:`nucleus.sdk.contracts`) which decides when to invoke
    it, captures the raise, and folds the outcome into the
    materialization result. The "semantic over source" carve-out
    (raising at the engine boundary) does not apply because the source
    in v0.1 is plain Python — there is no wrapped-library exception
    being translated.

    Per ``nucleus_architecture_v4.1.md`` §15 +
    ``nucleus_asset_model_spec.md`` §10, check failures attach to the
    materialization result rather than abort it — the contracts runtime
    wraps the raise as a failing :class:`nucleus.CheckResult` so the
    user sees the full set of check outcomes for one materialization.
    Direct ``raise`` (e.g. unit-test style) is the public surface for
    callers who want fail-fast semantics.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE3007"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/check-execution"


class NucleusRunNotFoundError(NucleusError):
    """A run ID was looked up but is not present in the run ledger.

    Fired by ``nucleus runs show <id>`` and ``nucleus runs cancel <id>``
    when the requested run ID does not appear in the NDJSON ledger at
    ``<project_root>/.nucleus/runs/runs.ndjson``.

    fix_hint: "Use ``nucleus runs list`` to see available run IDs."

    Layer (ADR-006 §1): L2 Coordination — run ledger ownership.
    See ADR-025 §P0-2 (run monitoring + persistence).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE3011"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/run-not-found"


# ============================================================================
# Source / IO errors
# ============================================================================


class NucleusSourceConnectionError(NucleusError):
    """Could not connect to a data source (Postgres, MySQL, ...).

    Typical causes: wrong host/port, network blocked, credentials wrong.

    Layer (ADR-006 §1): L0 Physics — source IO. Dagster inner
    ``ConnectionError`` (H1) routes here.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1001"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/source-connection"


class NucleusSourceNotFound(NucleusError):
    """A source dataset / view / file was referenced but does not exist.

    Layer (ADR-006 §1): L0 Physics — IO / object-store lookup.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1008"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/source-not-found"


class NucleusSourceAuthError(NucleusError):
    """The source rejected our credentials or denied access to the object.

    Layer (ADR-006 §1): L0 Physics — source-side auth failure during IO.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1009"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/source-auth"


class NucleusIOError(NucleusError):
    """A read/write to local FS or object storage failed.

    Layer (ADR-006 §1): L0 Physics — file-system / object-store IO
    (builtin ``FileNotFoundError`` routes here).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1005"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/io"


class NucleusPermissionError(NucleusError):
    """A filesystem or storage operation was denied due to permissions.

    Layer (ADR-006 §1): L0 Physics — OS / object-store permission boundary
    (builtin ``PermissionError`` routes here).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1006"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/permission"


# ============================================================================
# Config & runtime errors
# ============================================================================


class NucleusConfigError(NucleusError):
    """A configuration value is missing, malformed, or contradictory.

    Layer (ADR-006 §1): L4 Experience — ``ctx`` SDK / CLI configuration
    parsing surfaces this to the user.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE5001"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/config"


class NucleusAuthError(NucleusError):
    """Authentication failed (cloud credentials expired, OIDC token invalid, ...).

    Layer (ADR-006 §1): L4 Experience — surfaced through ``ctx`` / CLI when
    the OIDC delegation flow rejects the user (per AGENTS.md Constraint #6,
    we never own identity).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE5002"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/auth"


class NucleusResourceError(NucleusError):
    """An operation exceeded a resource limit (memory, disk, file descriptors).

    Layer (ADR-006 §1): L1 Engines — in-engine resource limit
    (``duckdb.OutOfMemoryException`` routes here).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE2003"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/resource"


class NucleusTimeoutError(NucleusError):
    """An operation exceeded its time budget.

    Layer (ADR-006 §1): L2 Coordination — Nucleus run-budget enforcement.
    Per H17 founder ratification (Option b), builtin ``TimeoutError`` from
    non-source paths routes here (NOT to ``NucleusSourceConnectionError``).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE3005"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/timeout"


class NucleusNetworkError(NucleusError):
    """A network operation failed (DNS, TCP, TLS, HTTP).

    Layer (ADR-006 §1): L0 Physics — wire-level transport.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE1010"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/network"


class NucleusRunCancelled(NucleusError):
    """A run was cancelled by the user (Ctrl+C / SIGTERM).

    Clean exit; not a true error but useful as a typed signal.

    Layer (ADR-006 §1): L4 Experience — user-initiated cancellation
    surfaces through the CLI / SDK.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE5003"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/cancelled"


class NucleusEnvironmentError(NucleusError):
    """The local development environment is missing or misconfigured.

    Surfaced when a required local-only dependency (container runtime,
    development-mode object-store container, port reservation) is
    unavailable, unreachable, or fails to come up healthy. Distinct from
    :class:`NucleusConfigError` (declarative config problems) and
    :class:`NucleusIOError` (filesystem read/write on a known-good
    environment); a ``NucleusEnvironmentError`` always points the user at
    something to install or start, not something to fix in a file.

    Typical triggers (v0.1): the local container runtime is not on PATH,
    ``docker compose`` exits non-zero, or the storage container fails to
    answer its readiness probe inside the timeout budget set by
    ``nucleus up``.

    Layer (ADR-006 §1): L4 Experience — the CLI and Workbench own
    bringing the local runtime online. First L4 NE5xxx allocation per
    ``nucleus_cli_spec.md`` §10 NV #4 (NE5001-3 ratified earlier alongside
    ``NucleusConfigError`` / ``NucleusAuthError`` / ``NucleusRunCancelled``;
    this is the next monotonic value per ADR-006 §Decision).

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE5004"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/environment"


# ============================================================================
# Scheduling errors (NE5005-NE5008 per ADR-017 + ADR-006 §NE5xxx L4 Experience)
# Accepted alongside ADR-017 PROPOSED status; founder ratifies the allocation.
# ============================================================================


class NucleusScheduleParseError(NucleusError):
    """A ``schedule=`` expression passed to ``@nucleus.asset`` could not be parsed.

    Fires at decoration time (import time) when the cron expression is not a
    valid 5-field cron string and does not match any supported shorthand alias
    (``@daily``, ``@hourly``, ``@weekly``, ``@monthly``, ``@yearly``).

    Typical triggers: typo in the cron string, 6-field cron (seconds not
    supported in v0.1), unsupported alias.

    Layer (ADR-006 §1): L4 Experience — ``ctx`` SDK boundary; validated at
    decoration time by ``nucleus.sdk.decorators._validate_schedule``.
    Source: ``croniter.is_valid()`` (Docs: https://pypi.org/project/croniter/).
    See ADR-017 §4 for the NE5xxx allocation rationale.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5005"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/schedule-parse"


class NucleusScheduleNotFoundError(NucleusError):
    """An asset key was referenced in a schedule command but no schedule is declared.

    Fires when ``nucleus schedule preview <key>`` is called for an asset that
    has no ``schedule=`` on its ``@nucleus.asset`` decorator (or when the asset
    key is not in the registry at all).

    Layer (ADR-006 §1): L4 Experience — CLI surface; resolved by the
    coordination layer's ``list_schedules`` + ``preview_schedule`` helpers.
    See ADR-017 §4.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5006"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/schedule-not-found"


class NucleusScheduleAlreadyActiveError(NucleusError):
    """A ``nucleus schedule on`` was attempted for a schedule already active.

    Reserved for v0.2 ``nucleus schedule on/off`` commands — not raised in v0.1.
    Declared here so the error code is locked per ADR-006 before v0.2 ships
    (codes are permanent from first release).

    Layer (ADR-006 §1): L4 Experience — CLI + coordination boundary.
    See ADR-017 §4 + ADR-006 §Decision (permanent from first ship).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5007"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/schedule-already-active"


class NucleusFeatureDeferredError(NucleusError):
    """A feature exists in the CLI surface but its implementation is deferred.

    Raised by ``nucleus schedule on``, ``nucleus schedule off``, and
    ``nucleus schedule trigger`` in v0.1.1 — the commands are visible in
    ``--help`` with a clear "coming in v0.2" message so users know the
    roadmap rather than seeing a confusing "command not found" error.

    Distinct from :class:`NucleusInternalError` (Nucleus bug) — this class
    signals an intentional, documented deferral, not an invariant violation.

    Layer (ADR-006 §1): L4 Experience — CLI feature-flag boundary.
    See ADR-017 §6 (v0.2 deferred items).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5008"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/feature-deferred"


# ============================================================================
# Layer 5 / Intelligence (AI Copilot v0.2+, ctx.agent v0.5+)
# NE4xxx range accepted 2026-05-13 via ADR-015 ratification; co-amendment per
# docs/FOUNDER_ACTION_QUEUE.md §0 + ADR-006 §Decision.
# ============================================================================


class NucleusCopilotAuthError(NucleusError):
    """The Copilot provider rejected the API key or token.

    Fires when the provider returns an auth failure (HTTP 401 / 403).
    The original ``litellm.AuthenticationError`` is preserved as ``cause``.

    Layer (ADR-006 §1): L3 Intelligence — AI Copilot boundary.
    Source: ``litellm.AuthenticationError``.
    See ``docs/errors/copilot.md`` for fix steps and provider key env vars.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE4001"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/copilot-auth"


class NucleusCopilotRateLimitError(NucleusError):
    """The Copilot provider rate-limited this request.

    Fires when the provider returns HTTP 429. Retry with back-off or
    switch to the Ollama offline path for zero-rate-limit usage.
    The original ``litellm.RateLimitError`` is preserved as ``cause``.

    Layer (ADR-006 §1): L3 Intelligence — AI Copilot boundary.
    See ``docs/errors/copilot.md`` and the provider status page links.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE4002"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/copilot-rate-limit"


class NucleusCopilotProviderError(NucleusError):
    """The Copilot provider returned a server-side error (5xx or unmapped).

    Fires for ``litellm.APIError``, ``APIConnectionError``,
    ``BadRequestError`` (non-content-filter), or
    ``ServiceUnavailableError``. The full cause chain is preserved.

    Layer (ADR-006 §1): L3 Intelligence — AI Copilot boundary.
    See ``docs/errors/copilot.md`` for the Ollama offline fallback.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE4003"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/copilot-provider"


class NucleusCopilotContentFilterError(NucleusError):
    """The provider's content policy rejected the Copilot request.

    Fires when the provider returns a content policy violation
    (``litellm.ContentPolicyViolationError``). Rephrase the question
    or remove context items that may trigger content filters.

    Layer (ADR-006 §1): L3 Intelligence — AI Copilot boundary.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE4004"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/copilot-content-filter"


class NucleusBudgetExceededError(NucleusError):
    """Pre-flight cost estimate exceeds the configured ceiling.

    Raised BEFORE any HTTP call. The estimated cost (USD) is in the
    ``user_message``. Raise ``chat.cost_ceiling_usd`` in
    ``nucleus_project.yaml`` or shorten the question / context.

    This is a Nucleus-side pre-flight guard distinct from
    ``litellm.BudgetExceededError`` (proxy-side budget enforcement —
    not used in v0.2 per ADR-015 §2 out-of-scope items).

    Layer (ADR-006 §1): L3 Intelligence — AI Copilot boundary.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE4005"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/copilot-budget"


# ============================================================================
# Catch-all
# ============================================================================


class NucleusInternalError(NucleusError):
    """An internal Nucleus invariant was violated — this is a bug in Nucleus.

    Surfaced when the Error Translation Layer has no specific translator
    for an underlying exception type. Includes instructions for filing a
    bug report.

    Layer (ADR-006 §1): L2 Coordination — the translator itself owns
    this fallback.

    # Stability: Stable
    """

    error_code: ClassVar[str] = "NE3001"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/internal"


# ============================================================================
# Reliability hardening (NE2007 + NE3008 + NE3009 per ADR-024 + ADR-006)
# Appended 2026-05-15 by reliability-hardening builder (Wave 2 P0-3).
# ============================================================================


class NucleusMemoryLimitExceeded(NucleusError):
    """DuckDB exhausted the configured memory budget during a query.

    Fires when DuckDB raises ``OutOfMemoryException`` (or a similar
    memory-pressure signal) after Nucleus has already applied the
    ``SET memory_limit`` guard at AMA init.  Increase the project-level
    ``memory_limit`` key in ``nucleus_project.yaml``, or split the
    asset into smaller partitions.

    The original ``duckdb.OutOfMemoryException`` is preserved as
    ``cause`` for debug-mode inspection.

    Layer (ADR-006 §1): L1 Engines — DuckDB memory-pressure boundary.
    Per ADR-024 P0-1: triggered at ``coordination/asset_materialization.py``
    after ``SET memory_limit`` is applied.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE2007"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/memory-limit"


class NucleusConcurrentRunError(NucleusError):
    """A second ``nucleus run`` attempted to materialise the same asset concurrently.

    Fires when the advisory filesystem lock (``coordination/locks.py``)
    is already held by another process for this asset.  The conflicting
    ``pid`` and start timestamp are included in ``user_message``.  Wait
    for the first run to finish or kill the stale lock file at
    ``<warehouse>/.nucleus/locks/<asset_key>.lock``.

    Layer (ADR-006 §1): L2 Coordination — advisory-lock boundary.
    Per ADR-024 P0-2.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE3008"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/concurrent-run"


class NucleusMaintenanceError(NucleusError):
    """A post-commit maintenance operation (e.g. snapshot expiry) failed.

    Fires when ``coordination/snapshot_maintenance.py``'s
    ``expire_old_snapshots`` call raises an unexpected exception from
    pyiceberg.  The materialisation itself succeeded; this error is
    recorded but does NOT roll back the committed snapshot.

    The original exception is preserved as ``cause``.

    Layer (ADR-006 §1): L2 Coordination — post-commit maintenance boundary.
    Per ADR-024 P0-3.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE3009"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/maintenance"


# ============================================================================
# Dagit escape-hatch errors (NE5009-NE5011 per ADR-018 + ADR-006 §NE5xxx L4)
# Appended 2026-05-15 by mass-audit builder — WAVE-AUDIT-MARKER
# Wave 1B must NOT allocate NE5009/5010/5011; these are reserved here.
# ============================================================================


class NucleusDagitLaunchError(NucleusError):
    """The ``dagster-webserver`` binary is not installed or could not be found.

    Fired by ``nucleus dagit`` when ``subprocess.Popen`` raises
    ``FileNotFoundError`` for the ``dagster-webserver`` binary.
    Fix: ``pip install dagster-webserver==<pinned-dagster-version>``.

    Layer (ADR-006 §1): L4 Experience — CLI escape-hatch boundary.
    See ADR-018 §2 (escape-hatch vocabulary carve-out).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5009"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/dagit-launch"


class NucleusPortUnavailableError(NucleusError):
    """All ports in the auto-scan range are already bound.

    Fired by ``nucleus dagit`` when every port in the scan window
    (default 3000-3010) is already in use and the user did not pass
    an explicit ``--port``.

    Layer (ADR-006 §1): L4 Experience — CLI escape-hatch boundary.
    See ADR-018 §3 (port-scan range).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5010"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/port-unavailable"


class NucleusDagitSubprocessError(NucleusError):
    """The ``dagster-webserver`` subprocess failed during execution.

    Fired by ``nucleus dagit`` on any ``subprocess.SubprocessError``
    that is not a ``FileNotFoundError`` (which maps to
    :class:`NucleusDagitLaunchError` instead).

    Layer (ADR-006 §1): L4 Experience — CLI escape-hatch boundary.
    See ADR-018 §2.

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5011"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/dagit-subprocess"


# ============================================================================
# Scheduler daemon errors (NE5012-NE5014 — ADR-017 v0.2.1 mini-scheduler)
# Appended 2026-05-15 by Wave 2 P0-1 daemon builder.
# ============================================================================


class NucleusDaemonStartError(NucleusError):
    """The Nucleus scheduler daemon could not be started.

    Fired when :func:`nucleus.coordination.daemon.start_daemon` fails to
    spawn the daemon subprocess or encounters a startup error. Check that
    the project root is a valid Nucleus project and that no stale pidfile
    is blocking the start path.

    Layer (ADR-006 §1): L4 Experience — CLI + coordination boundary.
    See ADR-017 §v0.2.1 (mini-scheduler fallback).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5012"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/daemon-start"


class NucleusDaemonNotRunningError(NucleusError):
    """No Nucleus scheduler daemon is currently running.

    Fired by :func:`nucleus.coordination.daemon.stop_daemon` when the
    daemon is expected to be running but no live process is found.
    Run ``nucleus schedule on`` to start the daemon.

    Layer (ADR-006 §1): L4 Experience — CLI + coordination boundary.
    See ADR-017 §v0.2.1 (mini-scheduler fallback).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5013"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/daemon-not-running"


class NucleusDaemonAlreadyRunningError(NucleusError):
    """The Nucleus scheduler daemon is already running.

    Fired by :func:`nucleus.coordination.daemon.start_daemon` when a
    live daemon process is detected via the pidfile. Use
    ``nucleus schedule off`` to stop it first, or
    ``nucleus schedule status`` to inspect its current state.

    Layer (ADR-006 §1): L4 Experience — CLI + coordination boundary.
    See ADR-017 §v0.2.1 (mini-scheduler fallback).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5014"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/daemon-already-running"


# ============================================================================
# Iceberg snapshot management errors (NE5015-NE5016 per ADR-028 + ADR-006)
# Appended 2026-05-15 by snapshot-cli builder.
# ============================================================================


class NucleusSnapshotNotFoundError(NucleusError):
    """A snapshot ID or branch/tag name was not found in the Iceberg table.

    Fired by ``nucleus snapshot branch/tag create`` when the supplied
    ``--snapshot-id`` does not exist in the table's snapshot log, or by
    ``nucleus snapshot branch/tag delete`` when the named ref does not exist.

    Layer (ADR-006 §1): L0 Physics — Iceberg snapshot ref lookup.
    See ADR-028 §2 (Iceberg branch + tag CLI verbs).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5015"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/snapshot-not-found"


class NucleusBranchAlreadyExistsError(NucleusError):
    """A branch or tag with the given name already exists on the asset.

    Fired by ``nucleus snapshot branch/tag create`` when a ref with the
    same name is already registered in the Iceberg table metadata.
    Use ``nucleus snapshot branch/tag delete`` first, or choose a
    different name.

    Layer (ADR-006 §1): L0 Physics — Iceberg snapshot ref creation.
    See ADR-028 §2 (Iceberg branch + tag CLI verbs).

    # Stability: Beta
    """

    error_code: ClassVar[str] = "NE5016"
    DEFAULT_DOCS_URL = f"{_DOCS_BASE}/branch-already-exists"


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
    "NucleusLineageEmissionError",
    "NucleusCheckExecutionError",
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
    # Run ledger (NE3011 — ADR-025 §P0-2)
    "NucleusRunNotFoundError",
    # Intelligence / AI Copilot (NE4xxx — ADR-015 + ADR-006)
    "NucleusCopilotAuthError",
    "NucleusCopilotRateLimitError",
    "NucleusCopilotProviderError",
    "NucleusCopilotContentFilterError",
    "NucleusBudgetExceededError",
    # Scheduling (NE5005-NE5008 — ADR-017 + ADR-006)
    "NucleusScheduleParseError",
    "NucleusScheduleNotFoundError",
    "NucleusScheduleAlreadyActiveError",
    "NucleusFeatureDeferredError",
    # Dagit escape-hatch (NE5009-NE5011 — ADR-018 + ADR-006)
    "NucleusDagitLaunchError",
    "NucleusPortUnavailableError",
    "NucleusDagitSubprocessError",
    # Scheduler daemon (NE5012-NE5014 — ADR-017 v0.2.1 mini-scheduler)
    "NucleusDaemonStartError",
    "NucleusDaemonNotRunningError",
    "NucleusDaemonAlreadyRunningError",
    # Iceberg snapshot management (NE5015-NE5016 — ADR-028)
    "NucleusSnapshotNotFoundError",
    "NucleusBranchAlreadyExistsError",
    # Reliability hardening (NE2007 + NE3008 + NE3009 — ADR-024)
    "NucleusMemoryLimitExceeded",
    "NucleusConcurrentRunError",
    "NucleusMaintenanceError",
    # Catch-all
    "NucleusInternalError",
]
