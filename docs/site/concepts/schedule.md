---
title: Schedule
description: Declare when an asset should be materialized using cron expressions or preset aliases.
---

# Schedule

A **schedule** is a cron expression attached to an asset that declares when it should be automatically materialized. Declaring a schedule in v0.1 stores the expression and makes it inspectable; active execution (the scheduler daemon) lands in v0.2.

## Declaring a schedule

```python
@nucleus.asset(
    table="analytics.daily_revenue",
    schedule="@daily",
)
def daily_revenue(ctx) -> pl.DataFrame:
    ...
```

## Preset aliases

| Alias | Cron equivalent | Description |
|-------|----------------|-------------|
| `"@hourly"` | `"0 * * * *"` | Every hour |
| `"@daily"` | `"0 0 * * *"` | Every day at midnight UTC |
| `"@weekly"` | `"0 0 * * 0"` | Every Sunday midnight UTC |
| `"@monthly"` | `"0 0 1 * *"` | First of the month |
| `"@yearly"` | `"0 0 1 1 *"` | First of January |

## Custom cron expressions

```python
schedule="0 2 * * *"     # 2 AM UTC daily
schedule="0 */6 * * *"   # Every 6 hours
schedule="30 8 * * 1-5"  # 8:30 AM weekdays
```

Nucleus uses [croniter](https://github.com/kiorky/croniter) for validation and preview. Invalid expressions raise `NucleusScheduleParseError` (NE5005) **at import time** — a bad schedule expression is caught before any code runs.

## Viewing schedules

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

```bash
nucleus schedule preview analytics.daily_revenue --count 5
```

```
Next 5 runs for analytics.daily_revenue (schedule: @daily):
  2026-05-16 00:00:00 UTC
  2026-05-17 00:00:00 UTC
  2026-05-18 00:00:00 UTC
  2026-05-19 00:00:00 UTC
  2026-05-20 00:00:00 UTC
```

## Active scheduling (v0.2)

In v0.2, `nucleus schedule on <key>` activates the Dagster scheduler daemon for an asset. Until then, use `nucleus run` to materialize manually:

```bash
# v0.1 workflow — trigger manually
nucleus run analytics.daily_revenue

# v0.2+ — enable automatic execution
nucleus schedule on analytics.daily_revenue
```

!!! info "v0.1 scope"
    Declaring `schedule=` in v0.1 stores the expression and exposes it via `nucleus schedule list / preview`. Active scheduling (`nucleus schedule on`) raises `NucleusFeatureDeferredError` (NE5008) with a clear "v0.2" message.

## Related

- [ADR-017: Schedule exposure v0.1](../governance/architecture-decisions.md)
- [Schedule an Asset guide](../guides/schedule-asset.md)
- [CLI reference: nucleus schedule](../cli-reference/schedule.md)
