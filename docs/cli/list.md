# `nucleus list`

> **Stability**: Beta (v0.2) · **Spec**: `docs/specs/nucleus_cli_spec.md` §3
> **Closes**: PoC #5 Checkpoint 7 — asset discoverability blocker
> (`docs/poc/p5_beachhead/FEEDBACK_FORM.md` Friction #5 + "What would make
> me a paying user" #3).

List every registered asset (and check) in the current Nucleus project,
alongside materialization status pulled from the Iceberg catalog. Closes
the discoverability gap surfaced by the PoC #5 external-tester field
test: testers had no first-class way to see which assets a project
exposed without grepping `assets/*.py`.

## Synopsis

```
nucleus list [--namespace <name>] [--format text|json|jsonl]
```

## Options

| Option                     | Env var          | Default | Description |
|----------------------------|------------------|---------|-------------|
| `--namespace <name>`, `-n` | —                | (none)  | Filter to keys starting with `<name>.` (e.g. `--namespace raw`). |
| `--format <fmt>`, `-f`     | `NUCLEUS_FORMAT` | `text`  | Output format. Accepts `text` (Rich table), `json` (NDJSON), or `jsonl` (alias for `json`). |

`--format json` and `--format jsonl` produce identical output — the alias
exists so `nucleus list --format jsonl | jq .` matches the broader jq
ecosystem convention.

## Output

### Text mode (default)

```
                            Registered assets (3)
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ asset key           ┃ type  ┃ materialized ┃ last materialized ┃ description                ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ example.greeting    │ asset │ yes          │ 4m ago            │ A tiny self-contained …    │
│ raw.orders          │ asset │ no           │ -                 │ Bronze layer for orders.   │
│ raw.orders          │ check │ no           │ -                 │ amount >= 0 sanity check.  │
└─────────────────────┴───────┴──────────────┴───────────────────┴────────────────────────────┘
```

Description is truncated to 60 characters with an ellipsis when longer.
Rows are sorted alphabetically by asset key, then by type
(`asset` rows precede `check` rows for the same key).

### JSON / JSONL mode

One self-contained NDJSON object per row, schema-versioned via
`_schema_version`:

```json
{"key":"example.greeting","type":"asset","namespace":"example","materialized":true,"last_materialized_ms":1747000000000,"last_materialized_relative":"4m ago","description":"A tiny self-contained example…","_schema_version":1}
```

Field reference:

| Field                        | Type             | Notes |
|------------------------------|------------------|-------|
| `key`                        | string           | Asset key, e.g. `raw.orders` (v0.1 keys are 2-level per `docs/specs/nucleus_cli_spec.md` §10 NV #6). |
| `type`                       | `asset` / `check`| Registry source — `@nucleus.asset` or `@nucleus.check`. |
| `namespace`                  | string           | First segment of `key` (matches the `--namespace` filter). |
| `materialized`               | bool             | `true` iff the Iceberg table has at least one committed snapshot. |
| `last_materialized_ms`       | int \| null      | Snapshot `timestamp_ms` from the Iceberg metadata. `null` if not materialized. |
| `last_materialized_relative` | string           | Coarse phrase: `Ns ago` / `Nm ago` / `Nh ago` / `Nd ago` / `-`. |
| `description`                | string           | First non-empty line of the decorated function's docstring, truncated to 60 chars. |
| `_schema_version`            | `1`              | Bumps per ADR-005 §3 when fields change incompatibly. |

## Examples

```bash
# Every registered asset, sorted alphabetically.
nucleus list

# Only assets in the `raw` namespace.
nucleus list --namespace raw

# Machine-readable NDJSON for piping into jq / scripts.
nucleus list --format json | jq -r 'select(.materialized == false) | .key'

# Pipe through jq via the jsonl alias.
nucleus list --format jsonl | jq '.key'

# Read the format from the environment instead of a flag.
NUCLEUS_FORMAT=json nucleus list
```

## Empty states

`nucleus list` is informational — empty results exit `0` and print a hint.

When no assets are registered in the project:

```
No assets found. Add @nucleus.asset(...) to a file under assets/,
or run `nucleus init <project>` to scaffold one.
```

When `--namespace` matches no assets:

```
No assets registered in namespace 'foo'.
Check the spelling or drop --namespace to see every asset.
```

## Errors

Per `docs/specs/nucleus_cli_spec.md` §5.4, every error path raises a
`NucleusError` subclass and exits non-zero with the three-block render
on stderr (`Error [NEXXXX]:` + `Fix:` + `Docs:`). No `pyiceberg`,
`duckdb`, `dagster`, or `polars` class names ever appear in user
output — enforced by `scripts/dagster_leak_check.py` per AGENTS.md §11.7.

| Error class                     | Code   | Trigger |
|---------------------------------|--------|---------|
| `NucleusInvalidAssetDefinition` | NE3004 | Unknown `--format` value (only `text` / `json` / `jsonl`). |
| `NucleusInvalidAssetDefinition` | NE3004 | Invoked outside a project (no `nucleus_project.yaml` in any ancestor). |
| `NucleusInvalidAssetDefinition` | NE3004 | One or more files under `assets/` failed to import. |
| `NucleusCatalogError`           | NE1007 | The Iceberg catalog file is unreadable or corrupt. |

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | Listing rendered (including the empty-state hint). |
| 1    | A `NucleusError` was raised — see the stderr `Error [NEXXXX]:` block. |
| 2    | CLI usage error (Typer-driven) — bad flag, unknown subcommand. |

## See also

- [`nucleus run`](./run.md) — materialize one of the listed assets.
- [`nucleus query`](./query.md) — SQL-query a materialized asset via DuckDB.
- [`nucleus schedule list`](./schedule.md) — assets carrying a `schedule=` declaration.

---

*Spec source: `docs/specs/nucleus_cli_spec.md` §3.* *Implementation: `src/nucleus/cli/commands/list.py`.* *Tests: `tests/cli/commands/test_list.py` (12 cases).*
