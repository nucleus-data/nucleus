---
title: Schedule an Asset
description: Declare cron schedules on assets and preview next run times.
---

# Schedule an Asset

Scheduling tells Nucleus when an asset should automatically materialize. Declaring a schedule in v0.1 makes the intent explicit and inspectable; the active execution engine lands in v0.2.

## Step 1 — Declare the schedule

```python
@nucleus.asset(
    table="analytics.daily_revenue",
    schedule="@daily",
)
def daily_revenue(ctx) -> pl.DataFrame:
    ...
```

Valid values:
- Preset aliases: `"@hourly"`, `"@daily"`, `"@weekly"`, `"@monthly"`, `"@yearly"`
- 5-field cron: `"0 2 * * *"` (2 AM UTC daily)
- `None` (no schedule — run manually)

Nucleus validates the cron expression at **import time** using croniter. A typo in a cron string is caught before any code runs.

## Step 2 — Inspect declared schedules

```bash
nucleus schedule list
```

```
┌──────────────────────────┬──────────────┬───────────────────────┐
│ asset                    │ schedule     │ next_run (UTC)        │
├──────────────────────────┼──────────────┼───────────────────────┤
│ analytics.daily_revenue  │ @daily       │ 2026-05-16 00:00:00   │
│ raw.events               │ 0 */6 * * *  │ 2026-05-15 06:00:00   │
└──────────────────────────┴──────────────┴───────────────────────┘
```

## Step 3 — Preview upcoming runs

```bash
nucleus schedule preview analytics.daily_revenue --count 7
```

```
Next 7 runs for analytics.daily_revenue (schedule: @daily):
  2026-05-16 00:00:00 UTC
  2026-05-17 00:00:00 UTC
  ...
```

## Triggering manually (v0.1)

Until active scheduling is available in v0.2, trigger a scheduled asset manually:

```bash
nucleus run analytics.daily_revenue
```

## Active scheduling (v0.2)

```bash
# v0.2+ commands
nucleus schedule on analytics.daily_revenue     # activate daemon
nucleus schedule off analytics.daily_revenue    # deactivate
nucleus schedule trigger analytics.daily_revenue # fire immediately
```

These commands raise `NucleusFeatureDeferredError` (NE5008) in v0.1 with a clear message.

## JSON output

```bash
nucleus schedule list --format json
```

```json
{"_schema_version": 1, "asset": "analytics.daily_revenue", "schedule": "0 0 * * *", "next_run": "2026-05-16T00:00:00Z"}
{"_schema_version": 1, "asset": "raw.events", "schedule": "0 */6 * * *", "next_run": "2026-05-15T06:00:00Z"}
```

## Related

- [Concepts: Schedule](../concepts/schedule.md)
- [CLI: nucleus schedule](../cli-reference/schedule.md)
- [ADR-017: Schedule exposure v0.1](../governance/architecture-decisions.md)
