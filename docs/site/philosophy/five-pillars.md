---
title: Five Pillars
description: The five design principles that every Nucleus decision must satisfy.
---

# Five Pillars

Every architectural decision in Nucleus must serve at least one of these pillars without harming another. If a proposal violates even one pillar, it is rejected or deferred.

## Pillar 1 — High performance on minimal resources

**Test:** Does this hurt boot time, idle RAM, or query latency?

Nucleus runs on a MacBook. The local stack boots in &lt;10 seconds. DuckDB handles multi-billion-row queries in seconds on a laptop. Polars processes gigabytes in milliseconds with minimal memory. These aren't aspirational targets — they are the v0.1 beachhead spec.

Any feature that meaningfully increases boot time, idle RAM, or query latency is rejected for the core path.

## Pillar 2 — Composable by constitution

**Test:** Does this introduce a non-swappable dependency?

Every Tier 1/2 component (DuckDB, Polars, Dagster, Lakekeeper) has a documented swap interface and smoke tests in CI. When (not if) a vendor pivots or dies, Nucleus swaps the engine without breaking user code. This is the architectural insurance policy.

## Pillar 3 — AI-assisted by design

**Test:** Does this make the platform easier or harder for LLMs to operate?

Nucleus surfaces clean, structured metadata (asset graphs, schemas, error codes) that AI agents can reason about. The `ctx` SDK uses plain Python return types that LLMs understand. Error messages are natural-language first. The MCP server (v0.5+) exposes the asset graph directly to MCP-compatible agents.

Note: AI assistance is a feature, not the product headline. It is opt-in, privacy-gated, and does not affect the core data pipeline.

## Pillar 4 — Familiar UX from proven giants

**Test:** Are we inventing new vocabulary that doesn't exist in dbt/Dagster/Cursor?

Nucleus borrows vocabulary deliberately: `@nucleus.asset` mirrors Dagster's asset model; `{{ ref('...') }}` mirrors dbt's `ref()`; `nucleus init` mirrors `create-next-app`; `nucleus up/down` mirrors docker-compose. Engineers already know these patterns. We build on familiarity rather than fighting it.

## Pillar 5 — Friendly to giants, hostile to no-one

**Test:** Does this make Databricks/Snowflake graduation harder?

Iceberg portability is the graduation path. Every Nucleus asset is a standard Iceberg table readable by Databricks, Snowflake, Athena, Spark, or any Iceberg REST catalog. When a team outgrows a laptop, we celebrate the graduation and make it frictionless — we don't fight it.

---

## Applying the pillars

When evaluating any new feature:

1. List which pillars it serves
2. Check if it harms any pillar
3. "Serves 1, harms 0" → proceed (if it passes the [8-question gate](eight-question-gate.md))
4. "Serves 0, harms any" → reject
5. "Serves 1, harms 1" → trade-off analysis required; usually defer

The five pillars and the eight-question gate together are the complete decision framework for Nucleus v0.1 through v1.0.
