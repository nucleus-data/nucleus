---
title: nucleus schedule
description: List declared asset schedules and preview upcoming run times.
---

# `nucleus schedule`

Inspect declared asset schedules.

## Subcommands

| Subcommand | Stability | Description |
|-----------|-----------|-------------|
| `list` | Beta | List all assets with schedules |
| `preview KEY` | Beta | Show next N run times for one asset |
| `on KEY` | Beta (v0.2) | Activate scheduling for an asset |
| `off KEY` | Beta (v0.2) | Deactivate scheduling |
| `trigger KEY` | Beta (v0.2) | Fire immediately, regardless of schedule |

## `nucleus schedule list`

```bash
nucleus schedule list [--format text|json]
```

Output:

```
┌──────────────────────────┬──────────────┬───────────────────────┐
│ asset                    │ schedule     │ next_run (UTC)        │
├──────────────────────────┼──────────────┼───────────────────────┤
│ analytics.daily_revenue  │ @daily       │ 2026-05-16 00:00:00   │
│ raw.events               │ 0 */6 * * *  │ 2026-05-15 06:00:00   │
└──────────────────────────┴──────────────┴───────────────────────┘
```

## `nucleus schedule preview`

```bash
nucleus schedule preview analytics.daily_revenue [--count 5] [--format text|json]
```

Output:

```
Next 5 runs for analytics.daily_revenue (schedule: @daily):
  2026-05-16 00:00:00 UTC
  2026-05-17 00:00:00 UTC
  2026-05-18 00:00:00 UTC
  2026-05-19 00:00:00 UTC
  2026-05-20 00:00:00 UTC
```

Options:

| Option | Default | Description |
|--------|---------|-------------|
| `--count N` | 3 | Number of upcoming runs to show (max 20) |
| `--format text\|json` | text | Output format |

## Deferred subcommands (v0.2)

`nucleus schedule on/off/trigger` raise `NucleusFeatureDeferredError` (NE5008) in v0.1:

```
Error: Active scheduling ('schedule on/off/trigger') ships in v0.2.
Fix:   Use 'nucleus run analytics.daily_revenue' to trigger manually.
Docs:  https://nucleus.dev/errors/ne5xxx/#ne5008
       [NE5008]
```

## Errors

| Error | Code | Cause |
|-------|------|-------|
| `NucleusScheduleNotFoundError` | NE5006 | Asset key not found or has no schedule |
| `NucleusScheduleParseError` | NE5005 | Invalid cron expression (caught at import time) |
| `NucleusFeatureDeferredError` | NE5008 | v0.2 subcommand called in v0.1 |

## Related

- [Concepts: Schedule](../concepts/schedule.md)
- [Guide: Schedule an Asset](../guides/schedule-asset.md)
- [ADR-017](../governance/architecture-decisions.md)
