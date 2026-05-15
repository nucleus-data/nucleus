---
title: Support
description: Where to get help with Nucleus.
---

# Support

## Self-service (fastest)

1. **[Troubleshooting guides](../troubleshooting/index.md)** — common issues and fixes
2. **[Error reference](../errors/index.md)** — every NE-code explained
3. **[FAQ](#frequently-asked-questions)** — common questions below

## GitHub (recommended)

- **Bug reports:** [Open an issue](https://github.com/nucleus-data/nucleus/issues/new?template=bug_report.md)
- **Feature requests:** [Open a discussion](https://github.com/nucleus-data/nucleus/discussions/new?category=ideas)
- **Questions:** [GitHub Discussions Q&A](https://github.com/nucleus-data/nucleus/discussions/new?category=q-a)

## Frequently asked questions

### Is Nucleus production-ready?

Nucleus v0.1 is **beta software**. The API is stable within v0.1 and breaking changes follow [ADR-005](../governance/architecture-decisions.md). We recommend pinning versions and testing upgrades carefully.

### What Python versions are supported?

Python 3.11 is the primary supported interpreter. Python 3.12 is tested but not the CI primary. Python 3.13 is not yet validated.

### Does Nucleus work on Windows?

Yes, via WSL2. Native PowerShell is functional but WSL2 is recommended for the best Docker performance. See [Install](../getting-started/installation.md).

### Does Nucleus work with my existing dbt project?

Yes — Nucleus's `{{ ref() }}` syntax is dbt-compatible. You can point Nucleus's DuckDB engine at the same Iceberg tables dbt writes. A dbt-duckdb adapter (v0.3+) will provide tighter integration.

### Can I use Nucleus with Delta Lake?

Not natively — Nucleus is Iceberg-first. You can read Delta tables via DuckDB's `delta_scan()` extension, but Nucleus assets are always written as Iceberg.

### What's the difference between `@nucleus.asset` and `@nucleus.sql_asset`?

`@nucleus.asset` — Python function that returns a DataFrame. Use for Python-native transforms.
`@nucleus.sql_asset` — Python function that returns a SQL string. Use for SQL-primary transforms with `{{ ref() }}` syntax.

### When does active scheduling ship?

`nucleus schedule on/off/trigger` — v0.2 (Mo 8-14). In v0.1, use `nucleus run` manually.
