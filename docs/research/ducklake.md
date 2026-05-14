# Research: DuckLake (watch item, not a swap target)

> **Status**: WATCH ITEM — Iceberg remains Tier 0 immortal per `nucleus_architecture_v4.1.md` §9.2; DuckLake is **not** a swap target.
> **Verified**: 2026-05-12 · **Opened by**: ADR-002 §4.2.
> **Re-evaluate before**: v0.3 ship (Mo 14).
> **Sources**: `docs/research/strategic/solo_oss_patterns_and_iceberg_2026.md` §B.4 (primary); `docs/research/strategic/competitive_landscape_2026.md` §3.B + §3.E (supporting).

## §1. What is DuckLake

DuckDB Labs's lakehouse format, launched May 2025 (solo §B.4). Distinguishing trait: **SQL-database metadata** (Postgres / DuckDB / SQLite as catalog backing store) **vs Iceberg's file-based metadata** (`vN.metadata.json` snapshots in object storage). v0.3 (Sept 2025) added Iceberg interop. Pitch: simpler operational story for single-engine DuckDB stacks at small scale — no separate REST catalog process, no manifest-list scan overhead, SQL queries against the metadata.

## §2. Why it threatens the Nucleus beachhead

DuckLake targets exactly the small-team DuckDB-everywhere shape that **is** Nucleus's beachhead persona (5-20 engineers, 100GB-5TB, greenfield, MacBooks, per v4.1 §1.5). Direct quote from solo §B.4: *"Real threat to single-engine DuckDB stacks under ~low-TB — exactly Nucleus's beachhead."* If a 5-engineer team picks DuckLake first, they will not pick Nucleus second. Competitive context: competitive §3.B + §3.E.

## §3. Why NOT a swap target right now

- **Iceberg multi-engine adoption is decisive** — 96.4% Spark, 60.7% Trino, 32.1% Flink, 28.6% DuckDB; ~31% enterprise share (solo §B.4, Ryft 2026 survey).
- **Iceberg won the "open" framing** — Apache governance + multi-vendor committers; Polaris graduated ASF TLP Feb 18, 2026 (solo §B.4 + §B.2).
- **DuckLake is single-engine + small-scale only** — no Spark / Trino / Snowflake / Databricks read path; no graduation story (solo §B.4).
- **Iceberg is Tier 0 immortal — by design does not swap**; Yield-to-Giants Mode 1 (graduation) requires Iceberg portability (v4.1 §9.2 + §10.1).

## §4. Decision threshold + watch metrics — re-evaluate before v0.3 (Mo 14)

Re-open when **any** holds: (1) DuckLake **>5,000 GitHub stars** with >100 weekly commits; (2) **two or more "yield-to-giants" partners** (Databricks, Snowflake, Trino, BigQuery) ship first-party DuckLake read paths; (3) Iceberg compatibility regression in PyIceberg or Polaris that makes the v0.3 catalog co-default unworkable (solo §B.3); (4) **a funded Nucleus-shaped competitor adopts DuckLake first** — flank-attack threat that may force a tactical response (still not a Tier 0 swap; possibly an optional `engine="ducklake"` adapter under v4.1 §9.3 swap protocol).

Quarterly competitive-scan watch metrics: GitHub stars trajectory; vendor mentions in `competitive_landscape_2026.md` quarterly refresh; Iceberg compat regression in `pyiceberg` 0.11.x → 0.12.x or Polaris; DuckDB Labs commercial trajectory (Labs-led — license-pivot risk parallel to v4.1 §9.4 health monitoring for DuckDB).

---

*Per v4.1 §9.2 + ADR-002 §4.2, this note explicitly does NOT propose adding a swap interface for DuckLake.*
