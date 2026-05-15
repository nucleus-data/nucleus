---
title: CLI Reference
description: Complete reference for every nucleus CLI command, with global flags, error format, and stability guarantees.
---

# CLI Reference

The `nucleus` CLI is the primary surface in v0.1. Every command follows the same pattern:

```
nucleus <command> [options] [args]
```

Run `nucleus --help` (or `nucleus <command> --help`) at any time. The CLI is built on Typer; the `--help` output is always the source of truth for the version you have installed.

## Global flags

These flags work on every command.

| Flag | Description |
|------|-------------|
| `--format text\|json\|csv` | Output format. Defaults to **text** when stdout is a TTY and **NDJSON** otherwise — so pipes, CI logs, and `jq` Just Work. |
| `--quiet` / `-q` | Suppress non-error output. Errors still print to stderr. |
| `--no-progress` | Disable progress bars. Useful in CI logs. |
| `--version` | Print the installed version and exit. |
| `--help` | Show the command help and exit. |

Most commands also accept `--verbose` / `-v` (debug logging) and `--cwd <path>` (override the project root).

## Commands

| Command | Stability | Description |
|---------|-----------|-------------|
| [`init`](init.md) | Beta | Scaffold a new Nucleus project with the standard layout |
| [`up`](up.md) | Beta | Start the local stack (MinIO, catalog, scheduler) |
| [`down`](down.md) | Beta | Stop the local stack |
| [`run`](run.md) | Beta | Materialize one or more assets (`--asset name` or `--all`) |
| [`ingest`](ingest.md) | Beta | Ingest an external source into Iceberg via `ctx.copy_from` |
| [`query`](query.md) | Beta | Run SQL against the warehouse (DuckDB engine) |
| [`schedule`](schedule.md) | Beta | List and preview asset schedules |
| [`chat`](chat.md) | Beta (v0.2) | Single-turn AI Copilot |
| [`workbench`](workbench.md) | Beta (v0.2) | Launch the web Workbench |
| [`version`](version.md) | Beta | Print version information for `nucleus` and wrapped engines |

## Exit codes

The CLI follows standard Unix exit-code conventions:

| Exit code | Meaning |
|-----------|---------|
| `0` | Success |
| `1` | Generic failure (catch-all) |
| `2` | Misuse / invalid arguments (Typer-raised) |
| `64`–`78` | Reserved per `sysexits.h` (e.g. `64` USAGE, `66` NOINPUT, `73` CANTCREAT) |

Scripts and CI should branch on `exit_code != 0`, not parse text.

## Error format

All errors print to **stderr**, never stdout. The text format:

```
Error: Could not reach source 'postgres://...'. Connection refused.
Fix:   Check the host/port and that the database is running.
Docs:  https://nucleus.dev/errors/ne1xxx/#ne1001
       [NE1001]
```

`--format json` prints NDJSON to stderr — one JSON object per line, schema-versioned:

```json
{"_schema_version": 1, "level": "error", "error_code": "NE1001", "user_message": "Could not reach source 'postgres://...'. Connection refused.", "fix_hint": "Check the host/port and that the database is running.", "docs_url": "https://nucleus.dev/errors/ne1xxx/#ne1001"}
```

Every error code is documented under the [Error Reference](../errors/index.md). The `Docs:` URL in the error envelope deep-links to the right page.

## Stability tiers

| Surface | Stability through v1.0 | Notes |
|---------|------------------------|-------|
| Command **names** | **Frozen at v0.1** | `init`, `up`, `down`, `run`, `ingest`, `query`, `schedule`, `chat`, `workbench`, `version` |
| Flag taxonomy | Beta through v1.5 | We absorb [PoC #5](https://github.com/nucleus-data/nucleus/blob/main/poc/p5_beachhead/) external-tester feedback before locking |
| Output **wording** | Beta | The schema (`error_code`, `fix_hint`, `docs_url`) is stable; the human prose may improve |
| Output **schema** (NDJSON) | Versioned via `_schema_version` | Bumps documented in `CHANGELOG.md` |

This split lets us improve UX without breaking your scripts. See [ADR-005](../governance/architecture-decisions.md) for the full stability contract.
