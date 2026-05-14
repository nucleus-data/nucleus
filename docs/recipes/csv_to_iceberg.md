# Recipe: CSV → Iceberg in 15 minutes

> **Time**: ~15 min (no Docker, no source DB) · **Difficulty**: Junior DE · **Prereqs**: Python 3.11 / 3.12, ~500 MB disk
> **Status**: pre-v0.1; CLI lines marked `<!-- pre-v0.1 -->`
> **Refs**: [`postgres_to_iceberg.md`](./postgres_to_iceberg.md) · [`docs/patterns/partitioning.md`](../patterns/partitioning.md) · [`nucleus_poc_plan.md`](../../nucleus_poc_plan.md) §3 · [`nucleus_cli_spec.md`](../../nucleus_cli_spec.md)

Shortest path from "I have a CSV" to "I have a partitioned, BI-queryable Iceberg asset". No Docker, no source database.

---

## What you'll build

A `seasons.csv` (timestamped events) → Iceberg `raw.events` source asset → re-partitioned `staging.events_partitioned` asset bucketed by month for fast time-range queries.

## Why this matters

"I exported some CSV from a vendor — now what?" is most teams' first encounter. This is the smallest viable answer — the no-source-DB shape of the beachhead promise per [v4.1 §1.5](../../nucleus_architecture_v4.1.md).

---

## Step 1: Confirm prerequisites (~1 min)

```bash
python --version    # 3.11.x or 3.12.x
```

That's it. v0.1 default catalog is filesystem-backed ([v4.1 §5.7](../../nucleus_architecture_v4.1.md)) — writes land in `.nucleus/warehouse/`. If Python isn't installed, see [`SETUP.md`](../../SETUP.md) §1-§3.

## Step 2: Drop a CSV in place (~2 min)

Create `data/seasons.csv`:

```csv
event_id,event_ts,event_type,user_id,value
1,2026-01-05T08:23:00Z,signup,user_abc,1
2,2026-01-12T11:09:14Z,purchase,user_xyz,49.99
3,2026-02-03T16:42:00Z,signup,user_def,1
4,2026-02-19T09:55:30Z,purchase,user_abc,12.50
5,2026-03-08T14:30:00Z,churn,user_xyz,0
```

5 rows make the recipe inspectable end-to-end and let you eyeball the partitioning effect in Step 6; realistic CSVs have thousands.

## Step 3: Initialize and boot (~2 min)

```bash
nucleus init events-demo                         # <!-- pre-v0.1; nucleus_cli_spec.md §3.1 -->
cd events-demo
mv ../data .
nucleus up                                       # <!-- pre-v0.1; nucleus_cli_spec.md §3.2 -->
```

Same `<10 s` boot as the Postgres recipe ([v4.1 §11.1](../../nucleus_architecture_v4.1.md)) — MinIO + filesystem catalog + Dagster substrate.

## Step 4: Ingest the CSV (~3 min)

```bash
nucleus ingest file://./data/seasons.csv --as raw.events    # <!-- pre-v0.1; v4.1 §5.5.1 -->
```

Auto-infers `event_id INTEGER`, `event_ts TIMESTAMP`, `event_type STRING`, etc. Atomic commit. 5-row preview. Iceberg destination at `.nucleus/warehouse/raw/events/`.

## Step 5: Verify (~1 min)

```bash
nucleus sql "SELECT count(*), min(event_ts), max(event_ts) FROM raw.events"   # <!-- pre-v0.1; nucleus_cli_spec.md §4.5 -->
# Expected: 5 | 2026-01-05 08:23:00 | 2026-03-08 14:30:00
```

## Step 6: Add a monthly partition + incremental materialization (~6 min)

`assets/staging/events_partitioned.py`:

```python
import nucleus

@nucleus.sql_asset(
    materialize="incremental",
    partition_by="month(event_ts)",
)
def events_partitioned(ctx):
    """Re-partitioned by month. Subsequent runs only add new months' data."""
    return ctx.sql("""
        SELECT event_id, event_ts, event_type, user_id, value
        FROM {{ ref('raw.events') }}
    """)
```

```bash
nucleus run staging.events_partitioned          # <!-- pre-v0.1; nucleus_cli_spec.md §4.1 -->
```

`month(event_ts)` is one of seven Iceberg partition transforms — pick the right one per [`docs/patterns/partitioning.md`](../patterns/partitioning.md) §3 + §9 (decision tree). For 5 rows spanning 3 months you'll get one Parquet file per month.

---

## Verification

| Signal | Pass criterion |
|---|---|
| `.nucleus/warehouse/raw/events/data/` | non-empty Parquet file |
| `nucleus sql "SELECT * FROM raw.events"` | returns the 5 input rows |
| `.nucleus/warehouse/staging/events_partitioned/data/` | one Parquet file per distinct month |
| `nucleus lineage staging.events_partitioned` | shows `raw.events` upstream |

## Troubleshooting

- **CSV header has spaces or unicode** — auto-infer normalizes to lowercase snake_case (NEEDS VERIFICATION on exact rules); pre-clean exotic headers.
- **Wrong timestamp parse** — confirm `event_ts` is ISO-8601 UTC. Mixed timezones break `month(event_ts)` silently per [`docs/patterns/partitioning.md`](../patterns/partitioning.md) §7.
- **"Too many small files" on repeated ingests** — classic CSV-then-`incremental` fragmentation; see [`docs/patterns/compaction.md`](../patterns/compaction.md).

## What's next

- **Got Postgres or MySQL?** [`postgres_to_iceberg.md`](./postgres_to_iceberg.md) — same primitives, real source DB, the canonical 25-min beachhead path.
- **Agent access (v0.5+)?** [`slack_bot_on_data.md`](./slack_bot_on_data.md). **Not runnable today.**
- **Patterns**: [`partitioning.md`](../patterns/partitioning.md) · [`compaction.md`](../patterns/compaction.md) · [`snapshot_retention.md`](../patterns/snapshot_retention.md).

---

## NEEDS VERIFICATION

1. **`nucleus ingest file://...csv`** — CSV is one of v0.1's 6 source types ([`nucleus_poc_plan.md`](../../nucleus_poc_plan.md) §3) but PoC #3 validates only SQLite ([`poc/p3_ingest/STATUS.md`](../../poc/p3_ingest/STATUS.md)).
2. **CSV header normalization rules** — auto-infer on spaces / unicode / duplicates is unspecified in [v4.1 §5.5.1](../../nucleus_architecture_v4.1.md).
3. **`@nucleus.sql_asset(materialize="incremental")`** — per [v4.1 §13.2](../../nucleus_architecture_v4.1.md), `incremental` lands v0.3+, not v0.1. For a v0.1 trial use `materialize="table"` (full-refresh).
4. **`partition_by="month(event_ts)"` string DSL** — exists in [`docs/patterns/partitioning.md`](../patterns/partitioning.md) §6 but the parser inside `@nucleus.asset` is not implemented.
5. **One-Parquet-per-month commit semantics** — confirmable via `nucleus snapshot list` ([`nucleus_cli_spec.md`](../../nucleus_cli_spec.md) §6.1) once the snapshot CLI ships.

Hit any of these? Log to [`docs/research/ai_hallucinations.md`](../research/ai_hallucinations.md). Re-validate after PoC #3 expands beyond SQLite.
