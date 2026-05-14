# 09 — Write Tests

> **What you're doing**: Writing pytest tests for new Nucleus code.
> **Why it matters**: Tests are the spec. Code that doesn't have tests can silently regress. The Nucleus test suite is the primary governance artifact alongside the governance scripts.
> **Philosophy**: Write the test FIRST (see `AGENTS.md §11.4` step 2). AI writes the implementation; human writes the tests.
> **Time**: 15-30 minutes for a well-scoped test file

---

## Directory Structure

Tests mirror the `src/nucleus/` tree exactly:

```
tests/
  cli/
    commands/
      test_<command>.py          # per CLI command
    test_main.py                 # CLI integration
    test_init.py                 # nucleus init
  coordination/
    test_error_translation.py   # Error Translation Layer
    test_sql_resolver.py        # ctx.sql Jinja resolver
    test_asset_materialization.py
  ctx/
    test_copy_from.py           # SQLite connector
    test_copy_from_postgres.py  # Postgres connector
    test_copy_from_mysql.py     # MySQL connector
    test_copy_from_unified.py   # unified _dispatch.py
    test_public_surface.py      # public ctx.__init__ exports
    test_sql.py                 # ctx.sql
    test_read.py                # ctx.read
  intelligence/
    test_copilot.py
    test_copilot_smoke.py
  sdk/
    test_decorators.py          # @nucleus.asset, @nucleus.check
    test_materialize.py         # ctx.materialize
    test_contracts.py           # runtime schema contracts
    test_schedule_kwarg.py      # schedule= kwarg
  upgrade_smoke/
    test_dlt_postgres.py        # one per dep: upgrade smoke
    test_litellm.py
    test_optional_extras.py
  chaos/                        # (v0.3+) concurrent/failure scenarios
    test_concurrent_run.py
    test_storage_failure.py
  conftest.py                   # shared fixtures
```

---

## Per-Directory `conftest.py`

```python
# tests/conftest.py (root)
import pytest

@pytest.fixture(scope="session")
def tmp_warehouse(tmp_path_factory):
    """Shared temporary warehouse directory for Iceberg tests."""
    return tmp_path_factory.mktemp("warehouse")

@pytest.fixture
def sample_df():
    """Minimal Polars DataFrame for tests."""
    import polars as pl
    return pl.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})
```

---

## Test Naming Conventions

```python
def test_<what>_<when>_<expected>():
    """Step N: <one sentence describing what this test validates>."""
    ...
```

Examples:
- `test_copy_from_postgres_bad_credentials_raises_auth_error`
- `test_nucleus_asset_invalid_schedule_raises_at_decoration_time`
- `test_sql_resolver_ref_resolution_replaces_token_with_path`

Every test function has a one-line docstring. It's the spec for that test.

---

## Mock Patterns

### Mocking external services (standard pattern)

```python
# Mocking SQLAlchemy connection for Postgres tests
from unittest.mock import patch, MagicMock

def test_copy_from_postgres_happy_path(tmp_path):
    """Step 1: Happy path — successful ingest replaces table."""
    mock_table = MagicMock()
    mock_table.count = 42

    with patch("nucleus.ctx.copy_from_postgres._make_dlt_source") as mock_src, \
         patch("nucleus.ctx.copy_from_postgres._run_pipeline") as mock_run:
        mock_src.return_value = mock_table
        mock_run.return_value = None

        copy_from_postgres("postgres://user:pass@localhost/db", table="orders")

        mock_src.assert_called_once()
        mock_run.assert_called_once()
```

### Mocking S3 / MinIO

Use `moto` for AWS S3 mocking (already in dev deps if needed):

```python
# NEEDS VERIFICATION: moto is not currently pinned; add if needed
# Docs: https://docs.getmoto.org/en/latest/
import moto

@moto.mock_s3
def test_iceberg_write_to_s3(tmp_path):
    ...
```

### Mocking Dagster internals

Do NOT mock Dagster internals directly. Test at the `ctx` level (the public surface):

```python
# GOOD: test through the ctx SDK
from nucleus.ctx import copy_from

# BAD: mock Dagster internals
from unittest.mock import patch
patch("dagster.materialize")   # ← Don't do this
```

---

## Marker Conventions

```python
@pytest.mark.slow      # tests that take > 2 s; skip in quick runs
@pytest.mark.integration   # requires live service (Docker, network)
@pytest.mark.chaos     # (v0.3+) chaos/failure scenarios; run nightly
```

Run subsets:
```bash
pytest tests/ -m "not slow and not integration"   # fast tests only
pytest tests/ -m "slow"                           # slow tests only
```

---

## TDD Discipline (Per `AGENTS.md §11.4`)

The correct order:
1. **Human writes the test** (what must the code do?).
2. **Run the test** — it should fail (red).
3. **AI scaffolds the implementation** to make the test pass.
4. **Run the test** — it should pass (green).
5. **AI expands tests** for edge cases.
6. **Human reviews** the expanded tests.

If the test is written AFTER the code, it tests what the code does — not what the code should do. These are very different things.

---

## Coverage Targets

Per `AGENTS.md §11.6`:
- No explicit coverage percentage target (coverage theater).
- Every new module in `src/nucleus/` MUST have at least one test file.
- Every public function in `ctx/`, `sdk/`, `cli/` must have at least one happy-path test.
- Every `NucleusError` subclass must have at least one test that verifies the `error_code` and `fix_hint`.

Check coverage:
```bash
python -m pytest tests/ --cov=nucleus --cov-report=term-missing -q
```

---

## Error Translation Tests

Every connector and command that can raise `NucleusError` needs at least these tests:

```python
def test_<operation>_no_classnames_in_error_output():
    """
    Error output contains no external library classnames.
    Verified by dagster_leak_check discipline (AGENTS.md §11.7).
    """
    with pytest.raises(NucleusError) as exc_info:
        <operation_that_fails>()

    err = exc_info.value
    for banned in ["DagsterError", "duckdb", "pyiceberg", "sqlalchemy", "OperationalError"]:
        assert banned.lower() not in err.user_message.lower()
        assert banned.lower() not in err.fix_hint.lower()


def test_<operation>_error_preserves_cause():
    """Original exception is accessible via exc.cause for --verbose mode."""
    with pytest.raises(NucleusError) as exc_info:
        <operation_that_fails>()

    assert exc_info.value.cause is not None
```

---

## Upgrade Smoke Tests

Every pinned dependency needs a smoke test that runs on every upgrade:

```python
# tests/upgrade_smoke/test_<package>.py
"""
Upgrade smoke test for <package>.
Run when upgrading the pinned version in pyproject.toml.

Per AGENTS.md §11.13 (Hard Constraint #11 — upgrade safety).
"""
import pytest


def test_<package>_imports():
    """<package> imports cleanly at pinned version."""
    import <package>
    assert hasattr(<package>, "<key_symbol>")


def test_<package>_basic_operation():
    """Core operation works after upgrade."""
    import <package>
    result = <package>.<core_operation>()
    assert result is not None


def test_<package>_version_matches_pin():
    """Installed version matches pyproject.toml pin."""
    import <package>
    import tomllib
    with open("pyproject.toml", "rb") as f:
        config = tomllib.load(f)
    # Find the pin in project.dependencies
    pins = config["project"]["dependencies"]
    matching = [p for p in pins if p.startswith("<package>==")]
    assert len(matching) == 1, f"Expected one pin for <package>, found: {matching}"
    pinned_version = matching[0].split("==")[1]
    assert <package>.__version__ == pinned_version
```

---

## Common Pitfalls

- **Tests that match code instead of requirements**: write tests from the spec, not from reading the implementation.
- **Mocking at the wrong level**: mock at the boundary (the external library), not inside Nucleus.
- **`assert True` or empty tests**: test must actually assert something meaningful.
- **Tests that only test the happy path**: every NE-code needs a test; every error case needs a test.
- **Slow tests without `@pytest.mark.slow`**: blocks CI for everyone.
- **Testing implementation details**: test behavior (what the function does), not internals (how it does it).

---

## Verification

```
[ ] Test file exists at tests/<layer>/test_<component>.py
[ ] Every new public function has at least one test
[ ] All NucleusError subclasses tested for error_code and fix_hint
[ ] Error translation tests: no classnames in user output
[ ] Upgrade smoke test created if new dependency added
[ ] All tests pass: python -m pytest tests/ -q 0 failures
```

---

## References

- `AGENTS.md §11.2` — Author vs Reviewer discipline
- `AGENTS.md §11.3` — AI Boundary Map (which tasks AI handles)
- `AGENTS.md §11.4` — Per-feature workflow (tests before code)
- pytest docs: https://docs.pytest.org/en/stable/ (pinned dev dep)
- typer test guide: https://typer.tiangolo.com/tutorial/testing/ (for CLI tests)
