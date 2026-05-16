# Head-to-head: Nucleus vs the field (executive summary)

**Date**: 2026-05-15
**Researcher model**: Claude Opus 4.7 (architect tier per AGENTS.md
Section 11.14; preferred GPT-5.5 unavailable in this Cursor session,
fallback recorded).

This page is the one-pager to cite from the README, the v0.2.0 launch
post, HN, and Reddit. Each row links to a deep-dive report for the
methodology + raw numbers. **Do not quote a row without also linking
the deep-dive** -- the honest disclaimers live there.

---

## TL;DR

* Nucleus is **not** trying to be faster than DuckDB on raw query
  speed (DuckDB is already the engine -- `docs/specs/nucleus_architecture_v4.1.md`
  Section 5).
* Nucleus IS trying to be **faster to develop with**, **friendlier on
  errors**, and **portable** at the storage layer via Iceberg.
* The two head-to-heads below benchmark exactly those claims --
  honestly -- against the most credible alternative tools a startup
  data team would choose instead.

---

## Comparison matrix

| Competitor | Workload | Headline | Verdict | Deep-dive |
|---|---|---|---|---|
| **dbt-duckdb** | TPC-H Q1 (lineitem aggregation, 100,000 rows) | Harness ready; full run pending external network access (Bosch APAC proxy blocked `pip install dbt-duckdb`). On raw transformation we expect **near-parity** -- both engines run identical SQL through identical DuckDB. The differentiator is **portable Iceberg output** (Nucleus) vs **DuckDB native table** (dbt-duckdb). | RUN-PENDING -- re-measure on a network where dbt-duckdb installs cleanly | [`headtohead_dbt_duckdb.md`](headtohead_dbt_duckdb.md) |
| **Raw Dagster + DuckDB + pyiceberg** | 3-asset linear DAG (raw -> staging -> mart, 10,000 rows each), Iceberg-on-filesystem output for both | **LOC: Nucleus 36 vs raw 68 (raw is +89% larger).** **Boot-to-first-materialisation: Nucleus 12.43 s median vs raw 22.90 s median (Nucleus -46%).** **Error message quality: Nucleus surfaces `nucleus.errors.NucleusSchemaError` with no substrate class names; raw surfaces `duckdb.duckdb.BinderException` directly.** Nucleus wins decisively on every measured axis. | Measured 2026-05-15, n=3 | [`headtohead_dagster_duckdb.md`](headtohead_dagster_duckdb.md) |

---

## What we are NOT comparing (yet, and why)

| Tool | Why no benchmark |
|---|---|
| Spark / Databricks | Different category -- distributed cluster vs single laptop. Per `docs/specs/nucleus_architecture_v4.1.md` Section 10 (yield to giants), Nucleus does not compete here. The comparison would mislead. |
| Snowflake / BigQuery | Same -- managed cloud warehouses. Nucleus graduates TO them via Iceberg portability rather than competes WITH them. |
| Airflow | Different shape -- task-centric vs asset-centric. Migration guide tracked at `docs/swap/airflow.md`; benchmark would compare apples to oranges. |
| Prefect | Different shape -- flow/task vs asset. See `docs/internal/research/parity_vs_dbt_dagster_airflow.md` Section 3.5. |
| SQLMesh | Closest spirit-competitor (Python-first, local-first, DuckDB-capable). Worth a future head-to-head; deferred to v0.3 prep. |

---

## Methodology guardrails (mandatory)

Every claim above:

* **Hardware spec captured**: AMD64, 4 physical / 8 logical cores,
  15.7 GB RAM, Windows 10, Python 3.11.9. Documented in each
  deep-dive Section 1.1.
* **Software pins captured**: duckdb 1.1.3, polars 1.18.0,
  pyiceberg 0.11.1, dagster 1.9.5, nucleus 0.2.0. Documented in each
  deep-dive Section 1.2.
* **n=3-5 runs reported with median + stddev**. Raw samples kept in
  the result JSON for audit.
* **Honest disclaimer**: single-machine benchmark; production
  workloads vary; the **<30 minutes from clone to first Iceberg
  table** beachhead metric (`docs/specs/nucleus_architecture_v4.1.md`
  Section 1.5) is the user-facing claim. Raw transformation speed is
  **secondary** and largely inherited from DuckDB / Polars --
  Nucleus does not win on that axis by being clever with compute,
  it wins on developer-experience axes.
* **No overclaiming**: where Nucleus wins by 5% or less, the report
  says **"~parity, slight Nucleus edge"**. Where Nucleus loses, the
  report says so plainly. Where a measurement could not run, the
  report says **RUN-PENDING** rather than filling in a number.

---

## Reproduce

```bash
# Validate harnesses (no engines invoked):
python -m scripts.benchmarks.headtohead_dbt_duckdb       --dry-run
python -m scripts.benchmarks.headtohead_dagster_duckdb   --dry-run

# Full runs (require the competitor installed; Nucleus already in repo):
pip install dbt-duckdb     # in a side venv
python -m scripts.benchmarks.headtohead_dbt_duckdb       --runs 5 --rows 100000
python -m scripts.benchmarks.headtohead_dagster_duckdb   --runs 5 --rows 10000

# Result JSON paths:
# docs/benchmarks/_results/headtohead_dbt_duckdb.json
# docs/benchmarks/_results/headtohead_dagster_duckdb.json
```

---

## When to pick which (1-line summaries)

* **Pick Nucleus** when you want one tool, portable Iceberg output,
  AI-ready surface, and substrate-class names hidden from your error
  catalogue.
* **Pick dbt-duckdb** when you already have a dbt monorepo + macro
  ecosystem and a `.duckdb` file is a fine artefact.
* **Pick raw Dagster + DuckDB + pyiceberg** when you already run a
  Dagster mega-monorepo with custom IO managers + ResourceDefinitions
  that you would have to rewrite.

For the full pick-which matrix see each deep-dive's Section 4 / 5.

---

## References

* `docs/internal/research/headtohead_dbt_duckdb.md`
* `docs/internal/research/headtohead_dagster_duckdb.md`
* `docs/internal/research/benchmarks_v0.2.0.md` -- single-engine v0.2.0 baseline
* `docs/internal/research/parity_vs_dbt_dagster_airflow.md` -- full parity matrix
* `docs/specs/nucleus_architecture_v4.1.md` Section 1.5 (beachhead metric),
  Section 6.4 (error translation), Section 9 (composability),
  Section 10 (yield to giants)
* `AGENTS.md` Section 10.8 (be brutally honest about scope)
* Harnesses: `scripts/benchmarks/headtohead_*.py`
* Result JSONs: `docs/benchmarks/_results/headtohead_*.json`

---

*Cite this page as the executive summary; cite the deep-dives for any
quantitative claim. Numbers were measured on 2026-05-15 on the host
described in each deep-dive's Section 1.1. Re-measure on
beachhead-spec hardware before publicly quoting the absolute numbers;
the relative direction is the durable claim.*
