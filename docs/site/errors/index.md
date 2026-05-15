---
title: Error Reference
description: Complete NE-code index for all Nucleus errors.
---

# Error Reference

Every `NucleusError` carries a three-field contract:

```
Error: <what went wrong, in user language>
Fix:   <concrete suggestion>
Docs:  https://nucleus.dev/errors/<slug>
       [NE<L><CCC>]
```

## NE-code scheme

Code format: `NE[L][CCC]` where `L` is the architecture layer (1–5) and `CCC` is a monotonic three-digit counter.

| Layer | Prefix | Source | Page |
|-------|--------|--------|------|
| L0 Physics | `NE1xxx` | Iceberg, Parquet, Arrow, S3, network IO | [NE1xxx](ne1xxx.md) |
| L1 Engines | `NE2xxx` | DuckDB, Polars; compute, parse, plan | [NE2xxx](ne2xxx.md) |
| L2 Coordination | `NE3xxx` | Asset graph, Dagster wrap, contracts, lineage | [NE3xxx](ne3xxx.md) |
| L3 Intelligence | `NE4xxx` | AI Copilot, agent (v0.2+) | [NE4xxx](ne4xxx.md) |
| L4 Experience | `NE5xxx` | CLI, SDK, Workbench, scheduling | [NE5xxx](ne5xxx.md) |

## v0.1 error codes

| Code | Class | Description |
|------|-------|-------------|
| `NE1001` | `NucleusSourceConnectionError` | Cannot reach external source |
| `NE1002` | `NucleusCommitConflictError` | Concurrent write conflict |
| `NE1003` | `NucleusCommitUnknownError` | Commit status unknown |
| `NE1004` | `NucleusSchemaEvolutionError` | Schema change violates Iceberg rules |
| `NE1005` | `NucleusIOError` | Filesystem or object-store failure |
| `NE1006` | `NucleusPermissionError` | OS or storage permission denied |
| `NE2001` | `NucleusSchemaError` | Data didn't match declared schema |
| `NE2002` | `NucleusSQLSyntaxError` | SQL failed to parse |
| `NE2003` | `NucleusResourceError` | Engine resource limit exceeded |
| `NE3001` | `NucleusInternalError` | Catch-all — please file a bug |
| `NE3002` | `NucleusAssetNotFound` | Asset key not registered |
| `NE3003` | `NucleusAssetNotMaterialized` | Asset defined but never run |
| `NE3004` | `NucleusInvalidAssetDefinition` | Invalid asset definition |
| `NE3005` | `NucleusTimeoutError` | Operation timed out |
| `NE4001` | `NucleusCopilotAuthError` | LLM provider authentication failed |
| `NE4002` | `NucleusCopilotRateLimitError` | LLM provider rate limit |
| `NE4003` | `NucleusCopilotProviderError` | LLM provider 5xx error |
| `NE4004` | `NucleusCopilotContentFilterError` | Response blocked by content filter |
| `NE4005` | `NucleusBudgetExceededError` | Estimated cost exceeds ceiling |
| `NE5001` | `NucleusConfigError` | Configuration error |
| `NE5002` | `NucleusDockerUnavailable` | Docker not running |
| `NE5003` | `NucleusPortBound` | Required port already in use |
| `NE5005` | `NucleusScheduleParseError` | Invalid cron expression |
| `NE5006` | `NucleusScheduleNotFoundError` | Scheduled asset not found |
| `NE5008` | `NucleusFeatureDeferredError` | Feature not yet available in this version |

## Reserved ranges

- `NEx900`–`NEx999` (every layer) — internal codes, never user-facing
- `NE0xxx` — never allocated; reserved for "uninitialized" in tooling
