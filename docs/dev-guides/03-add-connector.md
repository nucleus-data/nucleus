# 03 — Add a New Data Source Connector

> **What you're doing**: Adding `nucleus ingest <source>://...` support for a new data source.
> **Why it matters**: Connectors are the most-requested features from beachhead teams. Getting the pattern right ensures each connector is testable, error-translated, and swappable.
> **Template**: The Postgres connector (`src/nucleus/ctx/copy_from_postgres.py`) is the gold standard — read it before starting.
> **Time**: 2-4 hours for a standard connector

---

## Before You Start

Apply the wrap-vs-build check:
1. Does dlt have a verified source for this? Check: https://dlthub.com/docs/dlt-ecosystem/verified-sources
2. If yes: wrap dlt. If no: consider SQLAlchemy (for SQL databases) or a purpose-built library.
3. Does the source library have permissive license (Apache 2.0, MIT, BSD)? Check ADR-007.
4. Read the official docs of the source system before touching any code (per Constraint #10).

---

## Step 1: Wrap-vs-Build Decision

Apply the algorithm from [`02-wrap-not-build-decisions.md`](02-wrap-not-build-decisions.md). For most SQL databases: wrap dlt. For file formats (Parquet, CSV): wrap `pyarrow` directly.

Document the decision in a new ADR (copy the Postgres ADR-014 pattern):
```bash
# Next free ADR number:
ls docs/decisions/ADR-*.md | sort | tail -1
# Create the new ADR:
cp docs/decisions/ADR-014-dlt-postgres-source.md docs/decisions/ADR-0NN-<source>-source.md
```

---

## Step 2: Read Official Docs of the Source System

**Do not skip this step.** Per Constraint #10 (`AGENTS.md §11.12`):

- Find the official documentation URL for the source system.
- Find the official dlt verified-source URL (if wrapping dlt).
- Note the exact method names and parameters you will call.
- Save the URL in the code as a comment.

Example:
```python
# Docs (source system): https://www.postgresql.org/docs/current/libpq-connect.html
# Docs (dlt verified source): https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database
```

---

## Step 3: Add Optional Dependencies to `pyproject.toml`

If the connector requires new packages:

```toml
# pyproject.toml
[project.optional-dependencies]
<source> = [
    "some-driver==X.Y.Z",  # exact pin required (Constraint #11)
]
```

Then run:
```bash
pip install -e ".[<source>,dev]"
```

Update `docs/internal/compatibility.md` with a new row for each new package. Update `docs/decisions/ADR-012-runtime-dependency-pin-matrix-v01.md` if the pin is mandatory (core, not optional).

---

## Step 4: Create `src/nucleus/ctx/copy_from_<source>.py`

Follow the Postgres pattern exactly:

```python
"""
ctx.copy_from_<source> — <Source Name> → Iceberg ingestion.

Per docs/specs/nucleus_architecture_v4.1.md §5.6.1 (copy_from helpers) and §6.4 (error translation).
Wrap target: <OSS library name>
Docs: <official docs URL>
Pinned: <package>==<version> (pyproject.toml extras.<source>)
"""
# Stability: Beta  (per ADR-005; change to Frozen when E2E-tested at v0.3+)

from __future__ import annotations

import logging

from nucleus.errors import (
    NucleusSourceConnectionError,
    NucleusSourceAuthError,
    NucleusIOError,
    NucleusSchemaEvolutionError,
)
from nucleus.coordination.error_translation import translate

_logger = logging.getLogger(__name__)


def copy_from_<source>(
    uri: str,
    table: str,
    *,
    destination_table: str | None = None,
    write_disposition: str = "replace",
    schema: str | None = None,
) -> None:
    """
    Ingest a table from <source> into the local Iceberg warehouse.

    Args:
        uri: Connection URI (e.g., '<source>://user:pass@host:port/db')
        table: Source table name to ingest.
        destination_table: Iceberg table name. Defaults to source table name.
        write_disposition: 'replace' (default) or 'append'.
        schema: Schema/database to use. Defaults to the one in the URI.

    Raises:
        NucleusSourceConnectionError: Host unreachable or connection refused.
        NucleusSourceAuthError: Bad credentials.
        NucleusSchemaEvolutionError: Schema mismatch with existing Iceberg table.
        NucleusIOError: Iceberg write failure.

    Docs: <official docs URL>
    """
    try:
        # Step 1: establish connection
        # Step 2: read source data
        # Step 3: write to Iceberg via ctx.copy_from's downstream path
        ...
    except SomeSourceError as exc:
        raise translate(exc) from exc
    except Exception as exc:
        raise translate(exc) from exc
```

---

## Step 5: Add `<source>://` Branch in `_dispatch.py`

```python
# src/nucleus/ctx/_dispatch.py

def copy_from(uri: str, **kwargs):
    scheme = uri.split("://")[0].lower()
    ...
    elif scheme in ("<source>", "<source>+<driver>"):
        from nucleus.ctx.copy_from_<source> import copy_from_<source>
        return copy_from_<source>(uri, **kwargs)
    ...
```

Also add to the CLI's scheme allow-list in `src/nucleus/cli/main.py` (search for `_INGEST_SCHEMES` or similar).

---

## Step 6: Public Re-export in `ctx/__init__.py`

```python
# src/nucleus/ctx/__init__.py
from nucleus.ctx.copy_from_<source> import copy_from_<source> as ingest_<source>_to_iceberg

__all__ = [
    ...,
    "ingest_<source>_to_iceberg",
]
```

---

## Step 7: Add NE2xxx Error Codes

Per ADR-006, connector-specific errors belong to the NE1xxx (Physics/Source) band. Add to `src/nucleus/errors.py`:

```python
class Nucleus<Source>ConnectionError(NucleusSourceConnectionError):
    """Connection to <Source> failed."""
    error_code: ClassVar[str] = "NE1xxx"  # next free NE1xxx code
    docs_url: ClassVar[str] = "https://nucleus.dev/errors/source-connection"
```

Run `python scripts/check_error_codes.py` to verify uniqueness.

---

## Step 8: Wire Translator Hook

Add a handler in `src/nucleus/coordination/error_translation.py`:

```python
def _<source>_error_handler(exc: Exception) -> NucleusError | None:
    """
    Translate <Source> library exceptions to NucleusError.
    Docs: <source library exception hierarchy URL>
    """
    exc_type = type(exc).__name__
    if exc_type in ("OperationalError", "ConnectionRefusedError"):
        return NucleusSourceConnectionError(
            user_message=f"Cannot connect to <Source>: {exc}",
            fix_hint="Check the <source>:// URI, verify the server is running, ...",
            docs_url="https://nucleus.dev/errors/source-connection",
        )
    if exc_type in ("AuthenticationError", "LoginFailedError"):
        return NucleusSourceAuthError(
            user_message=f"<Source> authentication failed: {exc}",
            fix_hint="Check credentials in the URI. ...",
            docs_url="https://nucleus.dev/errors/source-connection",
        )
    return None

# Register in the handlers list:
_HANDLERS = [
    ...,
    _<source>_error_handler,
    ...,
]
```

---

## Step 9: Write Tests (Minimum 5)

Create `tests/ctx/test_copy_from_<source>.py`:

```python
# tests/ctx/test_copy_from_<source>.py
"""
Tests for copy_from_<source>.

Mocked to not require a live <Source> instance.
Upgrade smoke at: tests/upgrade_smoke/test_<source>_connector.py
"""
import pytest
from unittest.mock import patch, MagicMock
from nucleus.ctx.copy_from_<source> import copy_from_<source>
from nucleus.errors import NucleusSourceConnectionError, NucleusSourceAuthError

def test_happy_path_replaces_table(tmp_path):
    """Step N: Happy path — replace disposition ingests successfully."""
    ...

def test_bad_credentials_raises_auth_error():
    """Step N: Bad credentials → NucleusSourceAuthError (NE1009), not raw exception."""
    with patch("<source_module>.<ConnectFunction>") as mock_connect:
        mock_connect.side_effect = <SourceAuthException>("bad password")
        with pytest.raises(NucleusSourceAuthError) as exc_info:
            copy_from_<source>("<source>://bad:pw@localhost/db", table="t")
        assert "NE1" in exc_info.value.error_code
        assert "authentication" in exc_info.value.fix_hint.lower()

def test_host_unreachable_raises_connection_error():
    """Step N: Host unreachable → NucleusSourceConnectionError."""
    ...

def test_schema_mismatch_raises_schema_evolution_error():
    """Step N: Incompatible schema → NucleusSchemaEvolutionError."""
    ...

def test_no_external_classnames_in_error_message():
    """Step N: Error messages contain no source library classnames (NE-code discipline)."""
    # Verify dagster_leak_check pattern: check user_message and fix_hint
    ...
```

---

## Step 10: Author ADR

Fill the ADR template (see `docs/dev-guides/08-author-adr.md`):
- Status: PROPOSED (becomes ACCEPTED after founder review)
- Context: why this connector is needed (beachhead metric link)
- OSS Options Considered: dlt vs SQLAlchemy vs custom
- Decision: which approach
- Consequences: LOC budget, new pins, upgrade smoke test

---

## Step 11: Update CHANGELOG

Add to `CHANGELOG.md` under `[Unreleased] > Added`:
```
- `nucleus ingest <source>://...` — <Source> source via wrapped <library> (ADR-0NN).
  New `src/nucleus/ctx/copy_from_<source>.py` plus `_translate_<source>_exception` in
  `coordination/error_translation.py`; `_dispatch.py` adds `<source>://` scheme;
  full mocked-unit + upgrade-smoke test coverage.
```

---

## Step 12: Run Governance + pytest + Beachhead E2E

```powershell
python scripts/check_vocabulary.py
python scripts/check_pinning.py
python scripts/loc_budget.py
python scripts/dagster_leak_check.py
python scripts/check_error_codes.py
python -m pytest tests/ctx/test_copy_from_<source>.py -v
python scripts/beachhead_e2e.py
```

All must pass.

---

## Step 13: Update `docs/internal/compatibility.md`

Add rows for each new package:
```markdown
| `<driver-package>` | `X.Y.Z` | MIT · GREEN | Upgrade with `<source>` connector ADR |
```

---

## Step 14: Write User Guide

Create `docs/site/guides/ingest-from-<source>.md` (see existing guides in `docs/site/guides/` as templates):

```markdown
# Ingest from <Source>

## Prerequisites
- `pip install nucleus-data[<source>]`

## Quick start
```bash
nucleus ingest <source>://user:pass@host:port/db --table my_table
```

## Connection string format
...

## Supported options
...

## Common errors
...
```

---

## Verification

After all 14 steps:

```
[ ] nucleus ingest <source>://... works on the command line (with a test instance)
[ ] All 5+ tests pass
[ ] check_error_codes.py EXIT 0 (new NE-codes are unique)
[ ] dagster_leak_check.py EXIT 0 (no source classnames in user output)
[ ] check_pinning.py EXIT 0 (new dep is exact-pinned)
[ ] beachhead_e2e.py 8/8 PASS (connector didn't break existing paths)
[ ] ADR authored and linked from ADR-012
[ ] CHANGELOG updated
[ ] docs/internal/compatibility.md updated
[ ] User guide created in docs/site/guides/
```

---

## Common Pitfalls

- **Forgetting the NE-code**: every `except` block must raise a `NucleusError` subclass with `error_code`.
- **Leaking the library classname**: `"OperationalError: ..."` in user_message → caught by `dagster_leak_check.py`.
- **Missing fix_hint**: every NE-code must have a concrete, actionable `fix_hint`. "Contact support" is not acceptable.
- **Using unpinned dependency**: `pip install <source_driver>` without pinning in `pyproject.toml` violates Constraint #11.
- **Skipping the official docs read**: if you use a method you're not sure about, add `# NEEDS VERIFICATION` and the docs URL. Never guess.

---

## Rollback

If the connector introduces a regression:
```bash
git revert <connector-commit>
pip install -e ".[dev]"   # re-install without new dep
```

Remove the ADR's Status from ACCEPTED back to PROPOSED with a note explaining the regression.

---

## References

- Gold standard connector: `src/nucleus/ctx/copy_from_postgres.py`
- dlt verified sources: https://dlthub.com/docs/dlt-ecosystem/verified-sources
- ADR-014 (dlt Postgres) — the template ADR for connectors
- `docs/dev-guides/06-error-translation-guide.md` — NE-codes and translator patterns
- `docs/internal/swap/dlt.md` — swap target documentation for dlt
