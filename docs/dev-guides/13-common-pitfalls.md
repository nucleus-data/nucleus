# 13 — Common Pitfalls

> **What you're doing**: Understanding the 25 most common mistakes contributors make in this codebase, so you don't make them.
> **Why it matters**: Most bugs in Nucleus are not algorithmic errors — they are discipline violations (wrong vocabulary, missing NE-code, leaked classname). This guide prevents them.

---

## Error Translation Pitfalls

### Pitfall 1: Forgetting the NE-code on a New `except` Block

**Symptom**: CI passes but `check_error_codes.py` will fail after someone checks.

```python
# BAD: no NucleusError subclass, no error_code
except Exception as exc:
    raise RuntimeError(f"Ingestion failed: {exc}")

# GOOD: translates to NucleusError with error_code
except Exception as exc:
    raise translate(exc) from exc
```

**Fix**: Always end `except` blocks with either `raise translate(exc) from exc` or `raise NucleusSpecificError(...) from exc`.

---

### Pitfall 2: Leaking External Classnames in Error Messages

**Symptom**: `dagster_leak_check.py` fails with "DuckDBPyConnection found in user-facing string."

```python
# BAD: "DuckDBPyConnection" leaks to user
user_message = f"DuckDBPyConnection error: {exc}"

# GOOD: sanitized message
user_message = f"SQL engine returned an error: {_safe_message(exc)}"
```

**Fix**: Use `_safe_message(exc)` which strips class names and paths.

---

### Pitfall 3: Re-raising Without `from exc`

**Symptom**: `--verbose` mode shows no cause chain; impossible to debug.

```python
# BAD: breaks cause chain
raise NucleusSourceConnectionError(...)

# GOOD: preserves cause
raise NucleusSourceConnectionError(...) from exc
```

---

### Pitfall 4: Double-Translating (Catching NucleusError with broad except)

**Symptom**: A `NucleusError` is caught by a broad `except Exception` and translated again, losing the original error code.

```python
# BAD: re-translates a NucleusError → loses NE-code
try:
    inner_call()  # raises NucleusSourceConnectionError
except Exception as exc:
    raise translate(exc) from exc  # translate() wraps it again

# GOOD: pass NucleusError through
try:
    inner_call()
except NucleusError:
    raise  # already translated; pass through
except Exception as exc:
    raise translate(exc) from exc
```

---

### Pitfall 5: Missing `fix_hint`

**Symptom**: User sees the error but has no idea what to do.

```python
# BAD: vague or empty fix_hint
NucleusSourceConnectionError(
    user_message="Cannot connect.",
    fix_hint="Check your configuration.",  # too vague
)

# GOOD: specific, actionable
NucleusSourceConnectionError(
    user_message="Cannot connect to the database server.",
    fix_hint=(
        "Verify the connection URI format: postgres://user:pass@host:5432/db. "
        "Check that the server is running with: psql -h host -p 5432. "
        "Ensure firewall allows connections from this machine."
    ),
)
```

---

## Dependency Pitfalls

### Pitfall 6: Adding a Dependency Without Pinning

**Symptom**: `check_pinning.py` fails: "some-package is not exactly pinned."

```toml
# BAD: unpinned
dependencies = ["some-package>=1.0"]

# GOOD: exact pin
dependencies = ["some-package==1.2.3"]
```

**Fix**: `pip index versions some-package` to find the latest; pin it exactly.

---

### Pitfall 7: Bulk-Upgrading Dependencies

**Symptom**: CI fails in a mysterious way; impossible to bisect which upgrade broke it.

**Fix**: ONE component per PR. If you're doing multiple, open multiple PRs and merge them 24h apart.

---

### Pitfall 8: Using a Library Without Adding It to `pyproject.toml`

**Symptom**: Works in your environment (it was installed transitively) but fails for other users who install from PyPI.

```python
# BAD: pyyaml installed transitively via dlt; not pinned in pyproject.toml
import yaml  # this works in your env but is fragile

# GOOD: explicitly pin pyyaml==6.0.3 in pyproject.toml first
```

**Fix**: Always `grep <package> pyproject.toml` before importing. If not there: add it.

---

## Vocabulary Pitfalls

### Pitfall 9: Using "table" as a Primitive

**Symptom**: `check_vocabulary.py` fails: "'table' found in user-facing string."

```python
# BAD: "table" as the primitive
user_message = "Table 'orders' was not found."

# GOOD: "asset" as the primitive
user_message = "Asset 'orders' was not found."
```

---

### Pitfall 10: Using "metastore" Instead of "catalog"

```python
# BAD
help="Path to the metastore configuration."

# GOOD
help="Path to the catalog configuration."
```

---

### Pitfall 11: Using "job" or "task"

```python
# BAD: "job" is Dagster vocabulary leaking through
print("Starting job 'daily_rollup'...")

# GOOD: use "materialization" or "asset"
print("Starting materialization of asset 'daily_rollup'...")
```

---

## Architecture Pitfalls

### Pitfall 12: Building When Wrapping Was Available

**Symptom**: Large custom implementation that does what a 3rd-party library already does.

**Fix**: Before implementing ANY new component, check `AGENTS.md §4` (Do-Not-Build list) and apply the wrap-vs-build decision from `docs/dev-guides/02-wrap-not-build-decisions.md`.

---

### Pitfall 13: Cross-Layer Import

**Symptom**: `check_layering.py` fails: "L4 cli imports from L3 intelligence via private path."

```python
# BAD: cli (L4) importing coordination private internals (L2)
from nucleus.coordination.sql_resolver import _parse_refs

# GOOD: use the public interface
from nucleus.ctx import sql
```

---

### Pitfall 14: Skipping the ADR for a Major Version Upgrade

**Symptom**: Dependency upgraded from `pyiceberg==0.8.1` to `pyiceberg==1.0.0` without an ADR.

**Fix**: Major version bumps (X.y.z → X+1.0.0) require an ADR before the upgrade PR. See `docs/dev-guides/08-author-adr.md`.

---

### Pitfall 15: Speculative Code ("v0.5 might need this")

**Symptom**: LOC budget creeping up with code that has no v0.1 caller.

**Fix**: Per Anti-Over-Engineering: "If there is no v0.1 caller today, the code is not added today." Delete speculative code. Document the imagined need in `docs/internal/FOUNDER_ACTION_QUEUE.md`.

---

## AI and Testing Pitfalls

### Pitfall 16: Hallucinating an API Without Docs Check

**Symptom**: `pyiceberg.commit_atomic()` in a PR. Method doesn't exist.

**Fix**: Any unfamiliar method → `# NEEDS VERIFICATION` comment + check official docs at the pinned version URL. Never ship `# NEEDS VERIFICATION` comments without resolving them.

---

### Pitfall 17: Tests That Match Code Instead of Requirements

**Symptom**: Tests were written by reading the implementation, not the spec. They pass trivially but don't catch regressions.

**Fix**: Write tests from the spec first. Tests should describe behavior ("when X happens, user sees Y"), not implementation ("when `_internal_method()` is called, it returns Z").

---

### Pitfall 18: Marking Tests as Skip to Make CI Pass

**Symptom**: `@pytest.mark.skip("TODO: fix this")` accumulating without dates or issue numbers.

**Fix**: If a test is skipped because the feature isn't ready, the test file shouldn't exist yet. If it's skipped because of a flaky dependency, that's a bug — surface it.

---

### Pitfall 19: Trusting AI's "File Edited" Report Without Verifying

**Symptom**: AI claims to have edited 5 files. `git diff` shows only 2 were actually changed.

**Fix**: Always run `git diff --stat` or read the file after AI edits. AI fabrications are most common on documentation + multi-file edits. See `docs/internal/research/ai_hallucinations.md` for real examples.

---

## PR and Commit Pitfalls

### Pitfall 20: Multi-File PR That Hides Leaks

**Symptom**: A 15-file diff that no reviewer can meaningfully review.

**Fix**: Max 5 files per logic change. If more files are needed: split into multiple PRs.

---

### Pitfall 21: Forgetting to Run Governance Before Push

**Symptom**: CI fails on a script that takes 10 seconds to run locally.

**Fix**: Run all 8 governance scripts before every `git push`. Add a pre-commit hook: `pre-commit install`.

---

### Pitfall 22: No `docs_url` on New `NucleusError`

**Symptom**: User sees error code but clicking the docs_url gives a 404.

```python
# GOOD: use the convention even if the page doesn't exist yet
# The docs site will be built; the slug will eventually resolve.
docs_url = "https://nucleus.dev/errors/source-connection"
```

---

### Pitfall 23: Not Updating `docs/internal/compatibility.md` After Adding a Dep

**Symptom**: `upgrade_smoke.py` fails: "ADR-012 cross-check: package not in compatibility.md."

**Fix**: Every new dep in `pyproject.toml` gets a row in `docs/internal/compatibility.md` on the same PR.

---

### Pitfall 24: Importing `dagster` Directly in User-Facing Code

**Symptom**: `dagster_leak_check.py` fails.

```python
# BAD: direct Dagster import in ctx/ (user-visible layer)
from dagster import materialize

# GOOD: Dagster is only imported in coordination/
# ctx/ calls coordination/ which calls Dagster internally
```

---

### Pitfall 25: Assuming PoC Code Is Production-Ready

**Symptom**: PoC code in `poc/` gets imported directly by production code without promotion checklist.

**Fix**: PoC code lives in `poc/` until the PoC passes its validation criteria AND goes through the promotion checklist (`poc/<N>/PROMOTION_CHECKLIST.md`). The `.cursor/skills/nucleus-poc-promotion/SKILL.md` skill guides this process.

---

## Quick Reference

| Symptom | Likely Pitfall | First place to look |
|---|---|---|
| `check_vocabulary.py` fails | #9, #10, #11 | `scripts/check_vocabulary.py` output |
| `dagster_leak_check.py` fails | #2, #24 | The file + line number in the output |
| `check_pinning.py` fails | #6, #8 | `pyproject.toml` for the package |
| `check_error_codes.py` fails | #1, #5 | `src/nucleus/errors.py` |
| CI red after dep upgrade | #7 (bulk upgrade) | `git log --oneline -10` |
| Test passes but behavior is wrong | #17 | Re-read the spec; rewrite the test |
| AI hallucinated an API | #16 | `docs/internal/research/ai_hallucinations.md` |
| `check_layering.py` fails | #13 | The import path in the error output |
| LOC budget RED | #15 (speculative code) | `python scripts/loc_budget.py --detail` |

---

## References

- `AGENTS.md §11.7` — error translation discipline
- `docs/dev-guides/06-error-translation-guide.md` — full error translation patterns
- `docs/dev-guides/10-governance-scripts.md` — what each script enforces
- `docs/internal/research/ai_hallucinations.md` — AI hallucination log
