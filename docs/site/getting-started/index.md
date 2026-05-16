---
title: Getting Started
description: Install Nucleus and build your first Iceberg-backed asset in under 30 minutes.
---

# Getting Started

New to Nucleus? You're in the right place. This section takes you from a clean machine to a queryable Iceberg snapshot in under 30 minutes — the same path the v0.1 beachhead metric is measured against.

## What you will build

By the end of this section you will have:

- A scaffolded Nucleus project (`my-project/`) with the standard layout
- A local stack running on your laptop (DuckDB engine, MinIO object store, filesystem catalog)
- One **source asset** ingested from a database or file
- One **derived asset** produced by a SQL transformation
- A real Iceberg snapshot you can query from `nucleus query`, DBeaver, or any Iceberg-aware client
- Working lineage and a passing **contract** + **check**

That set of artifacts is what we call a **data product** — the unit Nucleus ships.

## The learning path

Follow these in order. Each builds on the previous.

| # | Guide | Time | What you learn |
|---|-------|------|----------------|
| 1 | [Installation](installation.md) | ~5 min | `pip install nucleus-data`, system requirements, first `nucleus version` |
| 2 | [Quickstart](quickstart.md) | ~30 min | The full beachhead path: `init` → `up` → `ingest` → `run` → `query` |
| 3 | [Your First Asset](your-first-asset.md) | ~15 min | Anatomy of a `@nucleus.asset` — function, return value, contract, check |
| 4 | [First BI-Ready Table](first-bi-table.md) | ~20 min | End-to-end Postgres → Iceberg → BI tool, with cross-asset lineage |

Total: under 90 minutes for the entire on-ramp. If you only have 30, do (1) and (2).

## Prerequisites

| Requirement | Why | How to check |
|-------------|-----|-------------|
| **Python 3.11** | Pinned for reproducibility per [upgrade policy](../governance/upgrade-policy.md) (3.12 may work but is unsupported) | `python3.11 --version` |
| **Docker Desktop** | Boots the local MinIO object store (skip if you point at a remote S3 endpoint) | `docker ps` |
| **Git** | Projects are git-native; the catalog and asset graph live in your repo | `git --version` |
| **A SQL source** | Postgres, MySQL, or SQLite to ingest from. None handy? `nucleus init` ships with a starter SQLite fixture so you can finish the quickstart with no external dependency. | n/a |
| **Disk space** | ~2 GB for Iceberg data + Docker image cache (the [PoC #4 boot test](https://github.com/nucleus-data/nucleus/blob/main/internal/poc/p4_local_stack/) measured the local stack at 117 MB RAM and ~5.8 s warm boot) | `df -h .` |

## After Getting Started

Once you have a passing first asset, three good next stops:

- [Concepts](../concepts/index.md) — the eight-word vocabulary (asset, materialization, snapshot, contract, check, catalog, lineage, schedule) that covers 95% of the mental model
- [Guides](../guides/index.md) — task-oriented recipes (ingest from Postgres / S3 / Snowflake, schedule an asset, query results, use the AI Copilot)
- [Cookbook](../cookbook/index.md) — pattern-oriented recipes (CDC, slowly changing dimensions, deduplication, schema evolution, Iceberg time travel)

If you get stuck, jump straight to [Troubleshooting](../troubleshooting/index.md) or the [Error Reference](../errors/index.md) — every `NE`-code includes a one-line **Fix** and a docs URL.
