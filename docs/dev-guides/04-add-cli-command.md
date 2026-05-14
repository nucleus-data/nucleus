# 04 — Add a New CLI Command

> **What you're doing**: Adding a new `nucleus <command>` to the CLI.
> **Why it matters**: Every CLI command is a user-visible promise. Getting the UX, error handling, and help text right matters more than the implementation.
> **Pattern**: All v0.1 commands are in `src/nucleus/cli/main.py` and `src/nucleus/cli/commands/`. Read existing commands before writing a new one.
> **Time**: 2-4 hours for a simple command; 4-8 hours for a command with complex output

---

## Before You Start

1. Is the command in `nucleus_cli_spec.md`? If not, it needs an ADR or at least a GitHub Discussion before implementation.
2. Does the command serve the beachhead metric? If not, defer (per 8-question gate).
3. Is there already a similar command you can extend (e.g., add a `--flag` to `nucleus run`) instead of adding a new top-level command?

---

## Step 1: Decide: Top-Level or Subcommand?

**Top-level command** (`nucleus newcmd`): for major user-facing operations. Example: `nucleus run`, `nucleus ingest`.

**Subcommand** (`nucleus schedule list`): for related operations under a domain. Example: `nucleus schedule on/off/list/preview`. Already used for `schedule`.

Rule of thumb: if you're adding 3+ related commands, make them subcommands of a group.

---

## Step 2: Create the Command Module

For non-trivial commands, create `src/nucleus/cli/commands/<command>.py`:

```python
"""
nucleus <command> — <one-line description>.

Per nucleus_architecture_v4.1.md §8 (Experience layer) and nucleus_cli_spec.md §<section>.
"""
# Stability: Beta  (per ADR-005)

from __future__ import annotations

import logging
import sys

import typer

from nucleus.errors import NucleusError

_logger = logging.getLogger(__name__)

app = typer.Typer(help="<command> help text")


@app.command("main")    # or named subcommand
def <command>(
    arg: str = typer.Argument(..., help="Description of arg"),
    flag: bool = typer.Option(False, "--flag", "-f", help="Description of flag"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full error details"),
) -> None:
    """
    <Command description — one sentence>.

    Example:
        nucleus <command> <arg>
    """
    try:
        result = _do_the_thing(arg, flag)
        _render(result, output)
    except NucleusError as exc:
        _handle_error(exc, verbose)
        raise typer.Exit(1)
    except Exception as exc:
        _logger.debug("Unexpected error", exc_info=True)
        typer.echo(f"Unexpected error: {exc}", err=True)
        raise typer.Exit(1)


def _do_the_thing(arg: str, flag: bool) -> object:
    """Business logic — calls ctx SDK, coordination, etc."""
    ...


def _render(result: object, output: str) -> None:
    """Render result as table (default) or JSON."""
    from nucleus.cli.rendering import render_table, render_json
    if output == "json":
        render_json(result)
    else:
        render_table(result)


def _handle_error(exc: NucleusError, verbose: bool) -> None:
    typer.echo(f"Error [{exc.error_code}]: {exc.user_message}", err=True)
    typer.echo(f"Fix: {exc.fix_hint}", err=True)
    if verbose:
        typer.echo(f"\nFull details: {exc.cause}", err=True)
    typer.echo(f"Docs: {exc.docs_url}", err=True)
```

---

## Step 3: Register in `main.py`

```python
# src/nucleus/cli/main.py

from nucleus.cli.commands.<command> import app as <command>_app

# Add to the main typer app:
app.add_typer(<command>_app, name="<command>")
```

For simple, inline commands (< 30 LOC total), add directly in `main.py` without a separate module.

---

## Step 4: Click Decorators + Parameter Conventions

Follow these conventions for all CLI commands:

| Convention | Rule |
|---|---|
| Positional arguments | Required inputs only. Use `typer.Argument(...)` |
| Named options | Optional inputs. Use `typer.Option(default, "--name", "-n", help="...")` |
| `--output` | Always include for commands that produce structured output. Values: `table` (default), `json` |
| `--verbose` | Always include for commands that can fail. Shows full error traceback when set |
| `--dry-run` | Include for destructive commands (e.g., `nucleus release --dry-run`) |
| Help text | One sentence. No jargon. References vocabulary from `AGENTS.md §7` |

---

## Step 5: Output Formatting

Use `src/nucleus/cli/rendering.py` for consistent output:

```python
from nucleus.cli.rendering import render_table, render_json, print_success, print_error

# Success message
print_success("Asset materialized successfully.")

# Table output (Rich)
render_table(
    title="Assets",
    columns=["Key", "Status", "Last materialized"],
    rows=[["my_asset", "✓", "2026-05-15"]],
)

# JSON output (when --output json)
render_json({"key": "my_asset", "status": "ok"})
```

Do NOT use `print()` directly. Use `typer.echo()` for raw output or the rendering helpers above.

---

## Step 6: Error Handling

Every command must:
1. Catch `NucleusError` and print the structured message (error_code, user_message, fix_hint, docs_url).
2. Exit with code 1 on any error.
3. Log full details when `--verbose`.
4. NEVER let a raw exception leak to the user.

```python
try:
    result = do_something()
except NucleusError as exc:
    typer.echo(f"[{exc.error_code}] {exc.user_message}", err=True)
    typer.echo(f"Fix: {exc.fix_hint}", err=True)
    if verbose:
        import traceback
        typer.echo(traceback.format_exc(), err=True)
    raise typer.Exit(1)
```

---

## Step 7: Help Text Discipline

Help text rules:
- No jargon ("Dagster", "pyiceberg", "DuckDB") — use vocabulary from `AGENTS.md §7`.
- First word is a verb (e.g., "Run an asset", "List scheduled assets", "Show asset schema").
- Include an example in the docstring.
- `--verbose` help: "Show full error details including stack trace."

Run `nucleus <command> --help` after implementation and read it as a new user would. If it's confusing, fix it.

---

## Step 8: Tests

Create `tests/cli/commands/test_<command>.py`:

```python
# tests/cli/commands/test_<command>.py
"""Tests for `nucleus <command>`."""
import pytest
from typer.testing import CliRunner
from nucleus.cli.main import app

runner = CliRunner()


def test_<command>_happy_path():
    """<command> with valid args exits 0."""
    result = runner.invoke(app, ["<command>", "valid-arg"])
    assert result.exit_code == 0
    assert "expected output" in result.output


def test_<command>_invalid_arg_exits_1():
    """<command> with invalid arg exits 1 with NucleusError message."""
    result = runner.invoke(app, ["<command>", "bad-arg"])
    assert result.exit_code == 1
    assert "NE" in result.output  # error code present


def test_<command>_help_text_no_jargon():
    """Help text contains no banned vocabulary."""
    result = runner.invoke(app, ["<command>", "--help"])
    assert result.exit_code == 0
    for banned in ["Dagster", "pyiceberg", "DuckDB", "metastore", "job"]:
        assert banned not in result.output, f"Banned term '{banned}' in help text"


def test_<command>_json_output():
    """--output json produces valid JSON."""
    import json
    result = runner.invoke(app, ["<command>", "valid-arg", "--output", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)  # should not raise
    assert isinstance(data, (dict, list))
```

---

## Step 9: Update `nucleus_cli_spec.md`

Add the new command to the CLI spec:

```markdown
## `nucleus <command> [OPTIONS] <ARG>`

**Description**: <one sentence>

**Arguments**:
- `<arg>`: Description

**Options**:
- `--flag`: Description
- `--output`: Output format (table, json)
- `--verbose`: Show full error details

**Exit codes**: 0 = success, 1 = error

**Example**:
```bash
nucleus <command> my-arg
```
```

---

## Step 10: Update CHANGELOG

```
### Added
- `nucleus <command>` — <one-line description> (per nucleus_cli_spec.md §X.Y).
```

---

## Verification

```
[ ] nucleus <command> --help works and has clean vocabulary
[ ] nucleus <command> <valid-arg> exits 0
[ ] nucleus <command> <bad-arg> exits 1 with NE-code in output
[ ] All tests pass
[ ] nucleus_cli_spec.md updated
[ ] CHANGELOG updated
[ ] dagster_leak_check.py EXIT 0 (no classnames in --help output)
```

---

## Common Pitfalls

- **`print()` instead of `typer.echo()`**: typer cannot capture `print()` in tests.
- **Missing `--verbose` flag**: makes debugging impossible for users.
- **Missing `--output json`**: breaks scripting workflows.
- **Printing to stdout on error**: use `err=True` for error output so stdout stays clean for piping.
- **Jargon in help text**: "DuckDB", "pyiceberg", "Dagster" must not appear in `--help`. CI catches this via `dagster_leak_check.py`.

---

## Rollback

If the new command causes issues:
1. `git revert <commit>` — remove the command.
2. Update `nucleus_cli_spec.md` to move the command back to "planned".
3. Update CHANGELOG to remove the entry from `[Unreleased]`.

---

## References

- Existing commands: `src/nucleus/cli/main.py`, `src/nucleus/cli/commands/`
- Rendering helpers: `src/nucleus/cli/rendering.py`
- Error handling: `docs/dev-guides/06-error-translation-guide.md`
- CLI spec: `nucleus_cli_spec.md`
- typer docs: https://typer.tiangolo.com/ (pinned version in `pyproject.toml`)
