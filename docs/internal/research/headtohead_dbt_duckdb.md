# Head-to-head: Nucleus vs dbt-duckdb (TPC-H Q1)

**Status**: Harness ready, full run pending external execution.
**Date**: 2026-05-15
**Researcher model**: Claude Opus 4.7 (architect tier per AGENTS.md
Section 11.14; preferred GPT-5.5 unavailable in this Cursor session,
fallback recorded).
**Honest framing**: per `AGENTS.md` Section 10.8 -- be brutally honest
about scope. The numbers below are either empirically measured on the
test host described in Section 1.1 or marked `RUN-PENDING` when an
external dependency could not be installed inside the Bosch APAC
corporate proxy environment. Nothing here is fabricated.

---

## TL;DR

* **What we compared**: TPC-H Q1 (lineitem aggregation) on a 100,000-row
  synthetic dataset against `dbt-duckdb`.
* **What Nucleus produces**: a portable Iceberg snapshot
  (`marts.q1`) committed via the Asset Materialization Adapter -- a
  `<namespace>.<name>` asset addressable by `ctx.read("marts.q1")`,
  consumable downstream by any tool that speaks Iceberg (Spark,
  Trino, Snowflake, Databricks, DuckDB).
* **What dbt-duckdb produces**: a DuckDB native `q1` table inside a
  `.duckdb` file. NOT an Iceberg snapshot. Portability requires a
  separate "export" step that dbt-duckdb does not automate.
* **The asymmetry is the point**: Nucleus adds the Iceberg commit +
  lineage emit + error translation tax to every materialisation; the
  trade-off is that the output is a portable snapshot the user can
  graduate to any catalog (Polaris, Lakekeeper, Unity, R2) per
  `docs/specs/nucleus_architecture_v4.1.md` Section 10 (yield to giants).
* **Numerical headline**: full run blocked by network (see Section 4).
  Harness validated end-to-end via `--dry-run`; reproducer command
  documented in Section 6.

---

## 1. Methodology

### 1.1 Hardware (test host)

Captured by `scripts/benchmarks/_common.py:hardware_specs()` and
embedded in every result JSON.

| Property | Value |
|---|---|
| CPU | AMD64; 4 physical / 8 logical cores |
| RAM | 15.7 GB total; ~3 GB free at run start |
| OS | Windows 10 (10.0.26100 SP0) |
| Disk | NTFS local SSD |
| Python | 3.11.9 |

This is the SAME host as the v0.2.0 single-engine baseline in
`docs/internal/research/benchmarks_v0.2.0.md` Section 1.1, so cross-reference
across the two reports is valid.

### 1.2 Software pins

Per `AGENTS.md` Hard Constraint #11 -- exact pins required.

| Library | Pin | Docs |
|---|---|---|
| duckdb | 1.1.3 | https://duckdb.org/docs/api/python/overview |
| polars | 1.18.0 | https://docs.pola.rs/api/python/stable/ |
| pyarrow | 18.1.0 | https://arrow.apache.org/docs/python/ |
| pyiceberg | 0.11.1 | https://py.iceberg.apache.org/ |
| nucleus | 0.2.0 (this repo) | local checkout |
| dbt-duckdb | NOT INSTALLED in this run | https://github.com/duckdb/dbt-duckdb |
| dbt-core | NOT INSTALLED in this run | https://docs.getdbt.com/ |

### 1.3 Workload

A 100,000-row synthetic Parquet file with reduced TPC-H lineitem
schema:

```
id              BIGINT
l_quantity      DOUBLE
l_extendedprice DOUBLE
l_discount      DOUBLE
l_tax           DOUBLE
l_returnflag    VARCHAR(1)  -- 'A', 'N', 'R'
l_linestatus    VARCHAR(1)  -- 'F', 'O'
l_shipdate      DATE
```

The transformation is canonical TPC-H Q1: a `GROUP BY (l_returnflag,
l_linestatus)` with `SUM`/`AVG`/`COUNT` aggregates filtered by
`l_shipdate <= DATE '1998-09-02'`. Reference:
https://www.tpc.org/tpch/.

### 1.4 Run protocol

* n=5 iterations per engine.
* `time.perf_counter()` (monotonic) outside the engine for wall-clock
  (https://docs.python.org/3/library/time.html#time.perf_counter).
* `psutil.Process().memory_info().rss` sampled every 50 ms by a
  background thread for peak RSS (`RSSWatcher` in
  `scripts/benchmarks/_common.py`).
* Median + stddev reported; raw samples preserved in the result JSON
  for audit.
* No retry-until-pass. A run that errors records FAIL with the
  exception verbatim.
* The dbt project is recreated in a fresh temp directory on every
  iteration so dbt's manifest cache cold-start cost is captured.

---

## 2. Nucleus path

```
@nucleus.asset("raw.lineitem")
def _raw():
    return pl.read_parquet(parquet_path)

@nucleus.asset("marts.q1", deps=["raw.lineitem"])
def _q1():
    return ctx.sql(
        "SELECT l_returnflag, l_linestatus, SUM(l_quantity), ... "
        "FROM {{ ref('raw.lineitem') }} "
        "WHERE l_shipdate <= DATE '1998-09-02' "
        "GROUP BY l_returnflag, l_linestatus",
        warehouse_dir=warehouse,
    ).collect()

nucleus.materialize("raw.lineitem",  warehouse_dir=warehouse)
nucleus.materialize("marts.q1",      warehouse_dir=warehouse)
```

Each `nucleus.materialize` call walks the AMA pipeline per
`docs/specs/nucleus_architecture_v4.1.md` Section 6.2: validate -> partition
enforce -> catalog atomic commit (ADR-001) -> OpenLineage emit ->
registry update. The output is a real Iceberg snapshot in the
filesystem catalog under `warehouse/marts/q1/`.

## 3. dbt-duckdb path

A minimal dbt project written to a temp directory:

```
dbt_project.yml
profiles.yml
models/raw_lineitem.sql   -- view over read_parquet('lineitem.parquet')
models/q1.sql             -- TPC-H Q1 against {{ ref('raw_lineitem') }}
```

Driven via `python -m dbt.cli.main run --project-dir <tmp> ...` so the
subprocess captures the full cold-start cost (process spawn + dbt boot
+ adapter init + DuckDB connect + render + execute).

Output is a DuckDB native table at `q1` inside a `.duckdb` file. Not
an Iceberg snapshot. There is no built-in dbt-duckdb path that writes
Iceberg without third-party extensions (see
https://github.com/duckdb/dbt-duckdb#materializations); the comparison
therefore favours dbt-duckdb on raw transformation speed (no Iceberg
commit ceremony) and Nucleus on portability (graduation path to any
catalog).

## 4. Results

### 4.1 Empirical numbers

**RUN-PENDING** -- the Bosch APAC corporate proxy blocked
`pip install dbt-duckdb` on the test host. Per the explicit founder
directive ("DO NOT fake numbers"), no measured numbers are quoted in
this section. The harness is fully wired and validated by
`--dry-run`; a tester on a network where the dbt-duckdb install
succeeds can run the full thing in under five minutes:

```bash
pip install dbt-duckdb       # in a side venv to avoid polluting Nucleus
python -m scripts.benchmarks.headtohead_dbt_duckdb --runs 5 --rows 100000
```

The result JSON is then written to
`docs/internal/benchmarks/_results/headtohead_dbt_duckdb.json` with full
hardware + software snapshot + per-run samples + medians + stddev.

### 4.2 Honest expectations (NOT measured here)

Based on the v0.2.0 baseline (`docs/internal/research/benchmarks_v0.2.0.md`):

| Metric | Nucleus expectation | dbt-duckdb expectation | Source |
|---|---|---|---|
| Cold-start time | ~10-15 s on the test host (Dagster + AMA boot) | ~3-5 s (dbt-core boot, no Iceberg) | inferred from B5 cold boot 2.11 s + Dagster 3-7 s + AMA ~1 s |
| Transform wall-clock for TPC-H Q1 on 100K rows | sub-second compute, dominated by ~80 ms ctx.sql per-call cost (B7) + Iceberg commit | sub-second compute, dominated by ~50 ms dbt render + DuckDB execute | DuckDB published TPC-H -- https://duckdb.org/2024/06/26/benchmarks-and-pretty-pictures.html |
| Output size on disk | Iceberg snapshot ~10-20 KB (single Parquet + manifest + metadata.json) | DuckDB native table ~5-10 KB inside the `.duckdb` file | informational -- formats differ structurally |
| Output row count | 6 (3 returnflag x 2 linestatus) | 6 (same) | TPC-H Q1 produces same output rows by definition |

Honest reading of this table: on raw transform speed we expect
**near-parity** -- both engines run identical SQL against identical
Parquet through identical DuckDB. Where Nucleus pays an extra cost is
**boot time** (Dagster import + AMA init) and **output ceremony**
(Iceberg commit). What Nucleus buys with that cost is portability +
lineage + atomicity guarantees. **Do not quote these as measured
numbers.** Re-run when the install succeeds.

## 5. When to pick which

This is the report's most important section: it is what a startup
engineer reads to decide.

### Pick Nucleus when

* You want one tool for your whole pipeline -- ingest + transform +
  schedule + lineage + UI -- without separately wiring dbt + Dagster +
  Airflow + a metadata service.
* You want your output to be **portable** -- an Iceberg snapshot you
  can read from Spark / Trino / Databricks / Snowflake without
  changing your transformation code (`docs/specs/nucleus_architecture_v4.1.md`
  Section 10 Mode 1).
* You want **AI-readiness by design** -- the `ctx` SDK + the MCP server
  (v0.5+) make assets first-class for LLM-based agents.
* You are starting greenfield (5-20 person startup data team).

### Pick dbt-duckdb when

* You already have a mature dbt monorepo (dbt-core models, macros,
  tests) and want zero migration cost. dbt-duckdb's surface is
  drop-in compatible with that ecosystem.
* You need dbt's macro library + package manager (`dbt deps`) -- a
  marketplace Nucleus deliberately did not build (`AGENTS.md`
  Section 4).
* You do not need Iceberg portability today. A `.duckdb` file is a
  fine artefact when the only consumer is more DuckDB.
* You need dbt's plan-time governance (`dbt-checkpoint`,
  `dbt-project-evaluator`) right now.

### Pick BOTH when

`nucleus enable dbt` (roadmap v0.3+ per
`docs/internal/research/parity_vs_dbt_dagster_airflow.md` Section 6) wraps a
dbt-duckdb model graph as Nucleus assets -- you keep your dbt SQL +
get Iceberg output + scheduled execution. Not in v0.2; tracked.

## 6. Reproduce

```bash
# 1. Validate the harness without running engines (dependency-free):
python -m scripts.benchmarks.headtohead_dbt_duckdb --dry-run

# 2. Run the full head-to-head (requires dbt-duckdb installed):
pip install dbt-duckdb
python -m scripts.benchmarks.headtohead_dbt_duckdb --runs 5 --rows 100000

# 3. The result JSON is written to
#    docs/internal/benchmarks/_results/headtohead_dbt_duckdb.json
```

The harness writes hardware + software snapshot + per-run samples,
so a third-party tester can confirm or refute every number.

## 7. Limitations

* Single host, single OS. Numbers do not portably translate to other
  CPUs / RAM tiers. The companion `benchmarks_v0.2.0.md` Section 1.1
  has the full caveat list.
* Single workload (TPC-H Q1). Real warehouses run dozens of queries
  with widely varying shapes. This benchmark is one data point, not a
  general claim.
* Output formats differ structurally (Iceberg snapshot vs DuckDB
  native table). The comparison is fair on transform speed; it is
  asymmetric on storage by design -- the asymmetry is the
  differentiator, not a bug.
* No cluster scale-out -- both engines are single-machine. Per the
  beachhead persona (`docs/specs/nucleus_architecture_v4.1.md` Section 1.5), a
  single laptop is the target.

## 8. References

* Harness: `scripts/benchmarks/headtohead_dbt_duckdb.py`
* Common utilities: `scripts/benchmarks/_common.py`
* TPC-H spec: https://www.tpc.org/tpch/
* DuckDB published TPC-H: https://duckdb.org/2024/06/26/benchmarks-and-pretty-pictures.html
* dbt-duckdb adapter: https://github.com/duckdb/dbt-duckdb
* Nucleus AMA pipeline: `docs/specs/nucleus_architecture_v4.1.md` Section 6.2
* Single-engine baseline: `docs/internal/research/benchmarks_v0.2.0.md`
* Companion report: `docs/internal/research/headtohead_dagster_duckdb.md`
* Executive summary: `docs/internal/research/headtohead_summary.md`

---

*All measured numbers in this report (none in this run; harness
validated by `--dry-run`) follow the methodology in
`scripts/benchmarks/_common.py`. When a benchmark could not run due to
a host-conditional gap (proxy block on `pip install dbt-duckdb`), it is
recorded as RUN-PENDING. Founder directive: never silently fill in
numbers. Re-measure on a network where dbt-duckdb installs cleanly
before quoting publicly.*
