# Nucleus CLI — Specification

> The complete command surface for the `nucleus` CLI. Git-like, kubectl-like ergonomics. Every command, every flag, every output format.
>
> Companion to `nucleus_architecture_v3.md` §10 and `nucleus_ctx_sdk_spec.md`. Locked for v1.0.

---

## 0. Principles

1. **One verb per concept.** No `nucleus do-the-thing-with-flags`.
2. **Composable output.** Every command supports `--output {human,json,yaml}`. `human` is default.
3. **Predictable exit codes.** 0 success, 1 user error, 2 system error, 3 contract/check failure.
4. **Idempotent where possible.** Re-running a deploy doesn't break it.
5. **`--help` is the source of truth.** Every command, every flag, documented.
6. **Quiet by default in CI.** `--quiet` removes progress bars. `--verbose` adds debug logs.

---

## 1. Command Tree

```
nucleus
├── init <name>                Scaffold new project
├── up                         Boot local stack
├── down                       Stop local stack
├── status                     Show platform health
├── version                    Print version info
│
├── run <asset>                Materialize a single asset
├── build [<selector>]         Materialize multiple assets (default: all)
├── backfill <asset>           Re-materialize over a range
├── test [<selector>]          Run tests + checks + contracts
├── sql <query>                Ad-hoc SQL query
│
├── list                       List all assets (filterable)
├── describe <asset>           Show full asset details
├── lineage <asset>            Show upstream/downstream graph
├── runs                       Recent run history
├── logs <run_id>              Stream logs of a run
│
├── snapshot
│   ├── list <asset>           Iceberg snapshots
│   ├── show <asset> <version> Show snapshot details
│   ├── revert <asset> <ver>   Roll back to snapshot
│   └── expire <asset>         Garbage-collect old snapshots
│
├── connect <connector>        Add new data source
├── connections list           List configured connections
│
├── enable <module>            Turn on optional module
├── disable <module>           Turn off optional module
├── modules list               Show available modules + status
│
├── deploy --target <target>   Ship to environment (k3s, k8s, docker)
├── upgrade                    Upgrade Nucleus binary + migrate metadata
│
├── secrets
│   ├── set <key>              Set a secret (prompts for value)
│   ├── list                   List secret names (not values)
│   └── unset <key>            Remove secret
│
└── doctor                     Diagnose environment problems
```

---

## 2. Global Flags

Available on **every** command:

| Flag | Default | Purpose |
|---|---|---|
| `--env <name>` | `dev` | Environment (matches `environments/<name>.yaml`) |
| `--project <path>` | `.` | Path to project root |
| `--output {human,json,yaml}` | `human` | Output format |
| `--quiet` | false | Suppress progress UI |
| `--verbose` | false | Debug logging |
| `--config <key=val>` | — | Override `nucleus.yaml` field |
| `--help` | — | Show command help |

---

## 3. Core Commands

### 3.1 `nucleus init <name>`

Scaffold a new project.

```bash
nucleus init my-project
nucleus init my-project --template=medallion
nucleus init my-project --template=dbt-migrate --from=./my-dbt-project
```

| Flag | Description |
|---|---|
| `--template <name>` | One of `basic`, `medallion`, `dbt-migrate`, `enterprise`. Default: `basic`. |
| `--from <path>` | Source project for migration templates. |
| `--no-git` | Skip git init. |

**Output (human)**:
```
Creating my-project/...
  ✓ nucleus.yaml
  ✓ pyproject.toml
  ✓ assets/raw/example.py
  ✓ assets/staging/example.py
  ✓ .gitignore
  ✓ README.md
Initialized git repository.

Next steps:
  cd my-project
  uv sync
  nucleus up
```

### 3.2 `nucleus up`

Boot the local stack: MinIO + Lakekeeper + DuckDB Arrow Flight + Dagster (hidden) + Portal.

```bash
nucleus up
nucleus up --port 8080            # custom Portal port
nucleus up --detach               # background
```

**Output**:
```
Starting Nucleus (env=dev)...
  ✓ Storage (MinIO embedded)            :9000
  ✓ Catalog (Lakekeeper)                :8181
  ✓ Query engine (DuckDB Flight)        :9090
  ✓ Orchestrator (internal)              ready
  ✓ Portal                              http://localhost:3000

Ready in 18.3s.
Open Portal: http://localhost:3000
```

### 3.3 `nucleus down`

Stop everything started by `up`. Preserves data in `.nucleus/`.

### 3.4 `nucleus status`

```
Project:     acme-data-platform
Environment: dev
Version:     1.0.3

Components:
  ✓ Storage          healthy   :9000
  ✓ Catalog          healthy   :8181  (12 tables)
  ✓ Query engine     healthy   :9090
  ✓ Orchestrator     healthy
  ⚠ obs module       disabled
  ⚠ auth module      disabled

Recent activity:
  Last run:    fact.orders (2 min ago, succeeded)
  Failed runs: 0 in last 24h
  Assets:      27 total, 25 succeeded, 0 failed, 2 never run
```

### 3.5 `nucleus version`

```
nucleus 1.0.3 (build abc123, 2026-05-11)
  duckdb       1.1.2
  polars       1.18.0
  iceberg-rust 0.4.0
  lakekeeper   0.5.1
  dagster      1.8.7 (embedded)
  dlt          1.4.0
```

---

## 4. Execution Commands

### 4.1 `nucleus run <asset>`

Materialize one asset (and its missing upstream, optionally).

```bash
nucleus run fact.orders
nucleus run fact.orders --partition 2024-01-15
nucleus run fact.orders --upstream         # also run all missing upstream
nucleus run fact.orders --param start_date=2024-06-01
nucleus run fact.orders --dry-run          # show plan, don't execute
```

| Flag | Description |
|---|---|
| `--partition <key>` | Single partition value |
| `--partitions <range>` | Range, e.g. `2024-01-01..2024-01-15` |
| `--upstream` | Materialize missing upstream first |
| `--force` | Re-materialize even if up-to-date |
| `--param key=value` | Pipeline parameter |
| `--dry-run` | Show execution plan, no side effects |

### 4.2 `nucleus build [<selector>]`

Materialize multiple assets via selector syntax (dbt-compatible).

```bash
nucleus build                              # all assets
nucleus build fact.*                       # all under fact namespace
nucleus build "+fact.orders"               # fact.orders + all upstream
nucleus build "fact.orders+"               # fact.orders + all downstream
nucleus build "+fact.orders+"              # full neighborhood
nucleus build "tag:finance"                # by tag
nucleus build "owner:data-team@acme.com"   # by owner
nucleus build --modified                   # only assets whose code changed since last run
```

### 4.3 `nucleus backfill <asset>`

Re-materialize over a partition range.

```bash
nucleus backfill events.clicks --range 2024-01-01..2024-01-31
nucleus backfill events.clicks --range 2024-01-01..2024-01-31 --parallelism 4
```

### 4.4 `nucleus test [<selector>]`

Run tests + checks + contracts.

```bash
nucleus test                               # all
nucleus test fact.orders                   # one asset
nucleus test --contracts-only
nucleus test --checks-only
nucleus test --pytest                      # also run pytest in tests/
```

Exit code 3 if any contract/check fails.

### 4.5 `nucleus sql <query>`

Ad-hoc SQL via DuckDB.

```bash
nucleus sql "SELECT COUNT(*) FROM fact.orders"
nucleus sql -f my_query.sql
nucleus sql -f my_query.sql --output json
echo "SELECT 1" | nucleus sql -
```

---

## 5. Discovery Commands

### 5.1 `nucleus list`

```bash
nucleus list                          # all assets
nucleus list --tag pii
nucleus list --owner data-team@acme.com
nucleus list --kind sql_asset
nucleus list --schedule daily
nucleus list --stale                  # not materialized in freshness SLA
```

**Output (human)**:
```
NAME                       KIND      SCHEDULE   LAST RUN          STATUS
raw.orders                 source    @hourly    2 min ago         ✓
raw.stripe_charges         source    @hourly    1 min ago         ✓
staging.orders             asset     @daily     20 min ago        ✓
dim.customers              asset     @daily     20 min ago        ✓
fact.orders                asset     @daily     5 min ago         ✓
analytics.daily_revenue    sql       @daily     never             —
analytics.country_revenue  sql       @daily     1 day ago         ⚠ stale
```

### 5.2 `nucleus describe <asset>`

```bash
nucleus describe fact.orders
nucleus describe fact.orders --output yaml
```

Full metadata: name, kind, owner, tags, schedule, partitions, code location, last run, contract, lineage summary.

### 5.3 `nucleus lineage <asset>`

```bash
nucleus lineage fact.orders                   # ASCII upstream + downstream
nucleus lineage fact.orders --upstream-only
nucleus lineage fact.orders --depth 2
nucleus lineage fact.orders --column total    # column-level lineage
nucleus lineage fact.orders --output json     # for tooling
```

**Output (human)**:
```
fact.orders
├── upstream
│   ├── raw.orders (source)
│   └── dim.customers
│       └── raw.customers (source)
└── downstream
    ├── analytics.daily_revenue
    └── analytics.country_revenue
```

### 5.4 `nucleus runs`

```bash
nucleus runs                                  # recent across all assets
nucleus runs --asset fact.orders
nucleus runs --status failed --since 24h
nucleus runs --limit 100
```

### 5.5 `nucleus logs <run_id>`

```bash
nucleus logs run_01HZ...                      # full log
nucleus logs run_01HZ... --follow             # stream
nucleus logs run_01HZ... --since 5m
```

---

## 6. Snapshot Commands

### 6.1 `nucleus snapshot list <asset>`

```
VERSION   TIMESTAMP             SIZE     ROWS       OPERATION
42        2024-05-10 02:00:01   142 MB   1,204,883  append
41        2024-05-09 02:00:01   139 MB   1,189,201  append
40        2024-05-08 02:00:01   137 MB   1,176,442  overwrite
```

### 6.2 `nucleus snapshot show <asset> <version>`

Full snapshot metadata: schema, partition spec, file count, properties, parent snapshot.

### 6.3 `nucleus snapshot revert <asset> <version>`

```bash
nucleus snapshot revert fact.orders 41        # rollback (creates new snapshot pointing at v41 data)
nucleus snapshot revert fact.orders 41 --dry-run
```

Requires `--confirm` flag if production env.

### 6.4 `nucleus snapshot expire <asset>`

```bash
nucleus snapshot expire fact.orders --keep-last 10
nucleus snapshot expire fact.orders --older-than 30d
```

---

## 7. Connection & Source Commands

### 7.1 `nucleus connect <connector>`

Interactive: prompts for connection details.

```bash
nucleus connect postgres
nucleus connect stripe
nucleus connect kafka --non-interactive --config=conn.yaml
```

Creates `connections/<name>.yaml` and optionally a starter source asset.

### 7.2 `nucleus connections list`

```
NAME           TYPE      LAST USED         STATUS
prod-db        postgres  5 min ago         ✓
stripe-prod    stripe    1 hour ago        ✓
warehouse-s3   s3        ongoing           ✓
old-mysql      mysql     never             ⚠ unused
```

---

## 8. Module Commands

### 8.1 `nucleus enable <module>`

```bash
nucleus enable obs           # installs OTel + VictoriaMetrics + Grafana
nucleus enable auth          # installs Authentik + Casbin
nucleus enable streaming     # installs Bento
nucleus enable vector        # installs LanceDB
nucleus enable scale         # installs Daft + Ray
nucleus enable bi-metabase   # installs Metabase OSS
```

Idempotent. Re-running shows current state.

### 8.2 `nucleus disable <module>`

Stops module containers. Preserves data unless `--purge` passed.

### 8.3 `nucleus modules list`

```
MODULE         STATUS      VERSION       NOTES
obs            enabled     0.5.2         OTel + VictoriaMetrics + Grafana
auth           disabled    —             Required for multi-user
streaming      disabled    —             Activate for CDC
vector         disabled    —             LanceDB retrieval
scale          disabled    —             Distributed (Daft + Ray)
bi-metabase    enabled     v0.50.0       Metabase bundled
governance     disabled    —             PII scanner, column lineage UI
```

---

## 9. Deployment

### 9.1 `nucleus deploy --target <target>`

```bash
nucleus deploy --target docker-compose --env prod
nucleus deploy --target k3s --env prod
nucleus deploy --target k8s --env prod --context my-cluster
nucleus deploy --target k8s --env prod --dry-run
```

Generates manifests + applies. Idempotent.

| Flag | Description |
|---|---|
| `--target` | `docker-compose`, `k3s`, `k8s` |
| `--context` | k8s context |
| `--namespace` | k8s namespace |
| `--dry-run` | Print manifests, don't apply |
| `--force-recreate` | Recreate pods even if unchanged |

### 9.2 `nucleus upgrade`

Upgrade Nucleus binary + run metadata migrations.

```bash
nucleus upgrade                  # latest stable
nucleus upgrade --version 1.2.0
nucleus upgrade --dry-run        # show migration plan
```

Always backs up metadata DB to `.nucleus/backups/` before migrating.

---

## 10. Secrets

```bash
nucleus secrets set STRIPE_API_KEY            # prompts (hidden input)
nucleus secrets set STRIPE_API_KEY --from-file=key.txt
nucleus secrets list                          # names only, never values
nucleus secrets unset OLD_KEY
```

Backend: OS keychain → `secrets` module (Infisical) if enabled.

---

## 11. `nucleus doctor`

Diagnose common problems.

```
Running Nucleus doctor...

System:
  ✓ Python 3.11.7
  ✓ uv installed
  ✓ Docker running
  ✓ Disk space (47 GB free)

Project:
  ✓ nucleus.yaml valid
  ✓ pyproject.toml valid
  ✓ Dependencies resolved (47 packages)
  ⚠ assets/dim/customers.py: missing docstring
  ✗ assets/fact/orders.py:42: imports `iceberg` directly (anti-pattern)
  
Connections:
  ✓ prod-db: reachable, credentials valid
  ✗ stripe-prod: connection refused (check STRIPE_API_KEY secret)

Catalog:
  ✓ Lakekeeper reachable
  ✓ Warehouse writable
  ⚠ 3 tables have no contract defined

Suggestions:
  - Add contracts: nucleus describe fact.orders --suggest-contract
  - Fix import: see assets/fact/orders.py:42

Exit code: 2 (1 error, 3 warnings)
```

---

## 12. Output Format

### 12.1 `--output human` (default)

Tables, colors, progress bars, emoji for terminal use.

### 12.2 `--output json`

Machine-readable. Stable schema (versioned).

```json
{
  "command": "list",
  "version": 1,
  "data": [
    {
      "name": "fact.orders",
      "kind": "asset",
      "schedule": "@daily",
      "last_run": {"id": "run_01HZ...", "status": "succeeded", "finished_at": "..."}
    }
  ]
}
```

### 12.3 `--output yaml`

Same data as JSON, YAML format. Useful for diffing configs.

---

## 13. Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | User error (bad command, missing file, invalid config) |
| 2 | System error (network, disk, dependency failure) |
| 3 | Contract or check failure (data quality, not platform) |
| 124 | Timeout |
| 130 | User-interrupted (Ctrl-C) |

Consistent with standard Unix conventions.

---

## 14. Configuration Precedence

Highest to lowest priority:

1. CLI flags (`--config key=val`)
2. Env vars (`NUCLEUS_CATALOG_ENDPOINT=...`)
3. `environments/<env>.yaml`
4. `nucleus.yaml`
5. Built-in defaults

---

## 15. Environment Variables

Standard env vars Nucleus respects:

| Var | Effect |
|---|---|
| `NUCLEUS_ENV` | Equivalent to `--env` |
| `NUCLEUS_PROJECT` | Equivalent to `--project` |
| `NUCLEUS_CONFIG_<KEY>` | Override `nucleus.yaml` field |
| `NUCLEUS_LOG_LEVEL` | `debug`, `info`, `warn`, `error` |
| `NO_COLOR` | Disable terminal colors |
| `NUCLEUS_CACHE_DIR` | Custom cache location |

---

## 16. Shell Completions

```bash
nucleus completions bash > /etc/bash_completion.d/nucleus
nucleus completions zsh > ~/.zsh/completions/_nucleus
nucleus completions fish > ~/.config/fish/completions/nucleus.fish
```

Tab completion for: commands, asset names (queried from catalog), tag names, environment names.

---

## 17. The CLI Promise

The CLI is the user's *primary surface* for production operations. The Portal is for exploration; the CLI is for automation. Therefore:

1. **Every Portal action has a CLI equivalent** (except interactive query/notebook).
2. **CLI output is scriptable** (`--output json` is stable).
3. **No interactive prompts in non-TTY mode** (CI safety).
4. **Idempotency where it matters** — `enable`, `deploy`, `upgrade` all safe to re-run.
5. **Errors are actionable** — every error message includes "try X" suggestions when possible.

---

*The CLI is how power users hold the platform. Make it a tool they trust.*
