# 06 — Error Translation Guide

> **What you're doing**: Adding new `NucleusError` subclasses, writing translator handlers, or verifying that external exceptions are properly translated.
> **Why it matters**: The Error Translation Layer is the #1 release blocker discipline. A leaked Dagster classname or a raw `duckdb.CatalogException` in user output destroys the abstraction thesis. Per `docs/specs/nucleus_architecture_v4.1.md` §6.4.
> **Authority**: ADR-006 (error code numbering), `AGENTS.md §11.7`.
> **Time**: 1-2 hours per new translator handler

---

## The Core Discipline

**Every code path that catches an external exception MUST translate it to a `NucleusError` subclass.**

```
External exception (Dagster, DuckDB, Polars, pyiceberg, dlt, SQLAlchemy)
    ↓ translate()
NucleusError subclass {
    error_code: str           # "NE1001" etc.
    user_message: str         # plain English, no jargon
    fix_hint: str             # concrete action the user can take
    docs_url: str             # https://nucleus.dev/errors/<slug>
    cause: Exception          # original exception (preserved; shown with --verbose)
}
```

**What must NEVER appear in `user_message` or `fix_hint`**:
- External classnames: `DagsterUserCodeExecutionError`, `DuckDBPyConnection`, `OperationalError`
- Internal module paths: `nucleus.coordination.asset_materialization`, `pyiceberg.catalog`
- Stack traces (in user_message — they're fine in `--verbose` mode)

---

## NE-Code Numbering (ADR-006)

| Band | Prefix | Layer | Examples |
|---|---|---|---|
| Physics / Source errors | NE1xxx | L0 Physics | NE1001 = connection refused, NE1002 = commit conflict |
| Engine errors | NE2xxx | L1 Engines | NE2001 = SQL syntax, NE2002 = OOM |
| Coordination errors | NE3xxx | L2 Coordination | NE3001 = asset not materialized, NE3007 = schema mismatch |
| Intelligence errors | NE4xxx | L3 Intelligence | NE4001 = missing API key |
| Experience / CLI errors | NE5xxx | L4 Experience | NE5001 = environment error, NE5008 = deferred feature |

To find the next free code:
```bash
python scripts/check_error_codes.py   # shows all current codes + gaps
```

---

## Step 1: Add a New `NucleusError` Subclass

In `src/nucleus/errors.py`:

```python
from typing import ClassVar


class NucleusMyNewError(NucleusError):
    """
    <One-sentence description of when this error fires>.

    Per docs/specs/nucleus_architecture_v4.1.md §6.4.
    """
    error_code: ClassVar[str] = "NE1003"    # next free in the appropriate band
    docs_url: ClassVar[str] = "https://nucleus.dev/errors/<slug>"
    # Stability: Frozen  (error codes are permanent per ADR-006)
```

Rules:
- Inherit from the appropriate parent: `NucleusError` (generic) or a more specific parent.
- `error_code` must be unique — verify with `python scripts/check_error_codes.py`.
- `docs_url` uses the `https://nucleus.dev/errors/<slug>` pattern (even if the page doesn't exist yet).
- The `# Stability: Frozen` tag is required (error codes are permanent per ADR-006 §Decision r3).

---

## Step 2: Write a Translator Handler

In `src/nucleus/coordination/error_translation.py`:

```python
def _my_source_error_handler(exc: Exception) -> NucleusError | None:
    """
    Translate <source library> exceptions to NucleusError.

    Docs: <official library exception hierarchy URL>
    Pinned: <package>==<version>
    """
    # Use type name string to avoid importing the external module here
    # (avoids circular imports and keeps the handler decoupled)
    exc_type_name = type(exc).__name__
    exc_module = type(exc).__module__

    if exc_module.startswith("sqlalchemy") and exc_type_name == "OperationalError":
        # "could not connect to server"
        return NucleusSourceConnectionError(
            user_message=f"Cannot connect to the database: {_safe_message(exc)}",
            fix_hint=(
                "Check the connection URI is correct and the server is running. "
                "Example: postgres://user:pass@localhost:5432/mydb"
            ),
            docs_url="https://nucleus.dev/errors/source-connection",
            cause=exc,
        )

    if exc_module.startswith("sqlalchemy") and exc_type_name in (
        "ProgrammingError", "InternalError"
    ):
        msg = _safe_message(exc)
        if "authentication" in msg.lower() or "password" in msg.lower():
            return NucleusSourceAuthError(
                user_message="Database authentication failed.",
                fix_hint="Check the username and password in the connection URI.",
                docs_url="https://nucleus.dev/errors/source-connection",
                cause=exc,
            )

    return None   # this handler doesn't know about this exception; pass to next


def _safe_message(exc: Exception) -> str:
    """
    Extract a user-safe message from an exception.
    Strips class names and paths; preserves error content.
    """
    msg = str(exc)
    # Remove Python repr artifacts (class name: message)
    if ": " in msg:
        msg = msg.split(": ", 1)[-1]
    return msg[:200]   # truncate; don't flood the terminal
```

Register the handler in the handlers list:
```python
_HANDLERS: list[Callable[[Exception], NucleusError | None]] = [
    _dagster_step_handler,
    _duckdb_error_handler,
    _pyiceberg_error_handler,
    _sqlalchemy_error_handler,
    _my_source_error_handler,   # ← add here
    ...
]
```

---

## Step 3: The 8 Critical Translation Cases

Per `docs/specs/nucleus_architecture_v4.1.md` §6.4, all 8 must be handled at every external boundary:

| # | Error type | Expected `NucleusError` subclass |
|---|---|---|
| 1 | Asset materialization failure (Python exception in `@nucleus.asset` body) | `NucleusAssetMaterializationError` or `NucleusInternalError` |
| 2 | SQL execution error (DuckDB error during `ctx.sql`) | `NucleusSQLSyntaxError` or `NucleusSQLExecutionError` |
| 3 | Out-of-memory crash | `NucleusResourceExhaustedError` |
| 4 | Iceberg commit conflict | `NucleusCommitConflictError` |
| 5 | Dependency asset not yet materialized | `NucleusAssetNotMaterializedError` |
| 6 | Schema mismatch / contract violation | `NucleusSchemaEvolutionError` |
| 7 | Timeout / cancellation | `NucleusTimeoutError` |
| 8 | Concurrent write conflict | `NucleusCommitConflictError` |

---

## Step 4: Fix-Hint Discipline

Every `NucleusError` instance MUST have a concrete, actionable `fix_hint`. Bad and good examples:

```python
# BAD: vague, not actionable
fix_hint="An error occurred. Please check your configuration."

# BAD: exposes internal classname
fix_hint="Catch the DagsterUserCodeExecutionError in your Python code."

# GOOD: specific, actionable, vocabulary-clean
fix_hint=(
    "Check that your asset function does not raise an unhandled exception. "
    "Run `nucleus run <asset-key> --verbose` to see the full traceback. "
    "Common causes: missing import, division by zero, API call failure."
)
```

---

## Step 5: Verify with `dagster_leak_check.py`

```bash
python scripts/dagster_leak_check.py
```

This script AST-scans the codebase for:
1. External library classnames in user-facing strings.
2. `except` blocks that re-raise raw exceptions without translation.
3. Banned terms in `user_message` and `fix_hint`.

If it reports a violation, find the location and apply the translation pattern.

---

## Step 6: Test Pattern for Each Translation Case

```python
# tests/coordination/test_error_translation.py

def test_sqlalchemy_operational_error_translates_to_connection_error():
    """
    SQLAlchemy OperationalError → NucleusSourceConnectionError.
    No raw exception classnames in user output.
    """
    from sqlalchemy.exc import OperationalError
    from nucleus.coordination.error_translation import translate

    raw = OperationalError("could not connect", None, None)
    translated = translate(raw)

    assert isinstance(translated, NucleusSourceConnectionError)
    assert "NE1" in translated.error_code
    assert "OperationalError" not in translated.user_message
    assert "sqlalchemy" not in translated.user_message.lower()
    assert translated.fix_hint is not None
    assert len(translated.fix_hint) > 10
    assert translated.cause is raw   # original preserved


def test_unknown_exception_falls_through_to_internal_error():
    """
    An exception with no handler → NucleusInternalError (not raw re-raise).
    """
    class WeirdUnknownError(Exception):
        pass

    raw = WeirdUnknownError("something weird")
    translated = translate(raw)

    assert isinstance(translated, NucleusInternalError)
    assert translated.cause is raw
```

---

## Anti-Patterns (How to Spot Them)

### Anti-pattern 1: Broad `except Exception` without translation
```python
# BAD
try:
    result = some_external_call()
except Exception:
    pass  # swallowed — user never knows what happened

# GOOD
try:
    result = some_external_call()
except NucleusError:
    raise  # already translated; don't re-translate
except Exception as exc:
    raise translate(exc) from exc
```

### Anti-pattern 2: Re-raising without `from exc`
```python
# BAD — breaks the cause chain
raise NucleusSourceConnectionError(...) from None

# GOOD — preserves cause for --verbose
raise NucleusSourceConnectionError(...) from exc
```

### Anti-pattern 3: External classname in user_message
```python
# BAD
user_message=f"DuckDBPyConnection failed: {exc}"

# GOOD
user_message=f"SQL engine returned an error: {_safe_message(exc)}"
```

---

## Verification

```
[ ] New NucleusError subclass added to errors.py with error_code + docs_url + Stability tag
[ ] check_error_codes.py EXIT 0 (code is unique)
[ ] Translator handler added to _HANDLERS list
[ ] dagster_leak_check.py EXIT 0 (no classname leaks)
[ ] Tests cover: happy translation, cause preserved, no classnames in output
[ ] fix_hint is concrete and actionable (not "check configuration")
```

---

## Rollback

If a new error code causes CI failure (duplicate code, wrong band):
1. Run `python scripts/check_error_codes.py` to identify the conflict.
2. Reassign to a free code in the correct band.
3. Update the `ClassVar` in `errors.py` and all references.

---

## References

- `src/nucleus/errors.py` — all NucleusError subclasses
- `src/nucleus/coordination/error_translation.py` — translator + handlers
- ADR-006: `docs/decisions/ADR-006-nucleus-error-code-numbering.md`
- `docs/specs/nucleus_architecture_v4.1.md` §6.4 — Error Translation Layer
- `docs/errors/` — user-facing error docs (one page per error slug)
- `.cursor/skills/nucleus-error-translation/SKILL.md` — Cursor skill for this discipline
