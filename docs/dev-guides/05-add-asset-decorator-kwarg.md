# 05 — Add a New `@nucleus.asset(...)` Kwarg

> **What you're doing**: Adding a new keyword argument to the `@nucleus.asset` decorator.
> **Why it matters**: `@nucleus.asset` is the primary user-facing API. Per ADR-005, it has a strict stability tier policy. Adding kwargs carelessly breaks backward compatibility and violates the API freeze.
> **Time**: 2-4 hours

---

## Before You Start

**Read ADR-005** (`docs/decisions/ADR-005-ctx-sdk-api-freeze-policy.md`) in full. The `@nucleus.asset` decorator is Frozen-tier from v1.0 onward. In v0.1, it's Beta — but the stability policy still applies.

Ask yourself:
1. Can the user achieve the same goal without a new kwarg?
2. Does the kwarg serve the `<30-min` beachhead metric directly?
3. Will this kwarg still make sense in v0.5 and v1.0?

If any answer is "no" or "unclear": defer.

---

## Step 1: Validate the Kwarg

Every new kwarg must:
1. Have a concrete v0.1 caller in a user-facing use case (not "v0.5 might need this").
2. Not duplicate an existing kwarg or a planned kwarg in `docs/specs/nucleus_ctx_sdk_spec.md`.
3. Have a sensible default that preserves backward compatibility (existing code still works without the kwarg).
4. Not collide with reserved kwarg names (`table`, `materialization`, `key` are reserved).

Check `docs/specs/nucleus_ctx_sdk_spec.md` for the full kwarg surface before proposing.

---

## Step 2: Define the Type and Default

Design the kwarg signature:

```python
# Good: explicit type, sensible default, clear purpose
@nucleus.asset(
    schedule="@daily",           # str | None = None
    compute="local",             # Literal["local", "databricks", "snowflake"] = "local"
    partition_by="date",         # str | None = None
    freshness_sla_hours=24,      # int | None = None
)

# Bad: untyped, no default, unclear semantics
@nucleus.asset(
    config={"key": "value"},     # Too broad; use specific kwargs instead
)
```

Type rules:
- Use `str | None = None` for optional string kwargs.
- Use `Literal[...]` for kwargs with a fixed set of valid values.
- Use `int | float | None` for numeric kwargs.
- Never use `Any`, `dict`, or `object` for new kwargs.

---

## Step 3: Add Validation in `sdk/decorators.py`

```python
# src/nucleus/sdk/decorators.py

# Per docs/specs/nucleus_architecture_v4.1.md §13 (ctx SDK contract) and ADR-005.

_VALID_COMPUTE_VALUES = frozenset({"local"})   # add "databricks" in v0.5


def asset(
    *,
    key: str | None = None,
    schedule: str | None = None,
    compute: str = "local",
    # ... existing kwargs ...
    new_kwarg: SomeType = default_value,
):
    """
    Register a function as a Nucleus asset.

    Args:
        ...existing args...
        new_kwarg: <Description>. Default: <default>.
            Stability: Beta (per ADR-005).
    """
    def decorator(fn):
        # Step 1: validate new_kwarg at decoration time (fail fast)
        _validate_new_kwarg(new_kwarg)
        # Step 2: store in asset registry
        ...
    return decorator


def _validate_new_kwarg(value: SomeType) -> None:
    """
    Validate <new_kwarg> at decoration time.
    Raises NucleusInvalidAssetDefinition if invalid.
    """
    if value is not None and not isinstance(value, ExpectedType):
        from nucleus.errors import NucleusInvalidAssetDefinition
        raise NucleusInvalidAssetDefinition(
            user_message=f"'new_kwarg' must be <type>, got {type(value).__name__!r}.",
            fix_hint="Pass a valid <type>. Example: @nucleus.asset(new_kwarg=<example>)",
            docs_url="https://nucleus.dev/errors/asset-not-found",  # update when docs exist
        )
```

**Key rule**: validate at decoration time (when `@nucleus.asset` is applied), not at materialization time. Fail fast with a clear message.

---

## Step 4: Backward Compatibility

Every new kwarg MUST have a default that makes existing code work unchanged:

```python
# Before (existing code — must still work):
@nucleus.asset
def my_asset():
    return df

# After (new kwarg with default — backward compatible):
@nucleus.asset(new_kwarg=None)  # None is the default; same as not passing it
def my_asset():
    return df
```

Test backward compatibility explicitly:
```python
def test_existing_assets_unchanged_with_new_kwarg():
    """Existing @nucleus.asset usage without new_kwarg still works."""
    @nucleus.asset
    def my_asset():
        return []
    # should not raise
```

---

## Step 5: ADR-005 Stability Tier

Add a `# Stability:` tag to the kwarg's docstring section:

```python
def asset(
    *,
    new_kwarg: str | None = None,
    # Stability: Beta  (per ADR-005; changes allowed within minor versions with warning)
):
```

- **Beta** (default for v0.1 additions): may change within minor versions.
- **Frozen** (reserved for v1.0+ when API is stable): requires 2-year deprecation cycle.

Per ADR-005, all new kwargs in v0.1 are Beta until explicitly promoted.

---

## Step 6: Update `docs/specs/nucleus_ctx_sdk_spec.md`

Add the kwarg to the `@nucleus.asset` specification section:

```markdown
### `new_kwarg` (Beta, v0.2+)

**Type**: `SomeType | None`
**Default**: `None`
**Added**: v0.2.0

Description of what this kwarg does.

Example:
```python
@nucleus.asset(new_kwarg=<example>)
def my_asset():
    ...
```

Validation: <description of validation rules>
```

---

## Step 7: Write Tests

Minimum tests for any new kwarg:

```python
def test_new_kwarg_default_is_backward_compatible():
    """Default kwarg doesn't change existing behavior."""
    ...

def test_new_kwarg_valid_value_accepted():
    """Valid value accepted at decoration time."""
    ...

def test_new_kwarg_invalid_type_raises_invalid_asset_definition():
    """Invalid type raises NucleusInvalidAssetDefinition at decoration time."""
    with pytest.raises(NucleusInvalidAssetDefinition) as exc_info:
        @nucleus.asset(new_kwarg=invalid_value)
        def bad_asset():
            pass
    assert "new_kwarg" in exc_info.value.user_message

def test_new_kwarg_propagated_to_materialization():
    """Kwarg value is accessible in asset materialization context."""
    ...

def test_new_kwarg_help_text_no_jargon():
    """Kwarg docstring contains no banned vocabulary."""
    import inspect
    sig = inspect.signature(nucleus.asset)
    docstring = nucleus.asset.__doc__
    for banned in ["Dagster", "pyiceberg", "DuckDB"]:
        assert banned not in docstring
```

---

## Step 8: Update CHANGELOG

```
### Added (in @nucleus.asset)
- `new_kwarg` parameter — <one-line description> (Beta tier, ADR-005).
  Validated at decoration time; NucleusInvalidAssetDefinition on invalid value.
  Backward-compatible: default None preserves existing behavior.
```

---

## Verification

```
[ ] Existing @nucleus.asset usages unchanged (backward compat test passes)
[ ] New kwarg validates correctly at decoration time
[ ] Invalid value raises NucleusInvalidAssetDefinition with NE-code
[ ] check_api_stability.py EXIT 0 (stability tier tagged)
[ ] docs/specs/nucleus_ctx_sdk_spec.md updated
[ ] CHANGELOG updated
```

---

## Common Pitfalls

- **Validating at materialization time instead of decoration time**: users don't discover the error until they run.
- **Missing default**: existing code breaks if there's no default for the new kwarg.
- **Using `dict` as the type**: use explicit types. `dict` kwargs become unmaintainable.
- **Forgetting the stability tag**: `check_api_stability.py` will fail without it.
- **Not updating `docs/specs/nucleus_ctx_sdk_spec.md`**: the spec is the contract; code without spec is a hidden API.

---

## Deprecating an Existing Kwarg

Deprecation follows ADR-005 discipline:

```python
def asset(
    *,
    old_kwarg: str | None = None,  # Deprecated since v0.3; remove in v1.5
    ...
):
    if old_kwarg is not None:
        import warnings
        warnings.warn(
            "old_kwarg is deprecated since v0.3 and will be removed in v1.5. "
            "Use new_kwarg instead.",
            NucleusDeprecationWarning,
            stacklevel=2,
        )
```

Deprecated kwargs must stay in the signature for the full deprecation cycle.

---

## References

- ADR-005: `docs/decisions/ADR-005-ctx-sdk-api-freeze-policy.md` — stability tier policy
- `src/nucleus/sdk/decorators.py` — the `@nucleus.asset` implementation
- `docs/specs/nucleus_ctx_sdk_spec.md` — the API surface specification
- Schedule kwarg example: `src/nucleus/sdk/decorators.py` (schedule parameter added in v0.1.1)
