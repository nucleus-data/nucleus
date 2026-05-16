# 15 — Performance Profiling

> **What you're doing**: Measuring and improving Nucleus performance — boot time, materialization latency, query latency.
> **Why it matters**: The beachhead metric is `<30 min` for the full workflow and `<10 s` for cold boot. Any regression breaks the brand promise. Per `docs/specs/nucleus_architecture_v4.1.md` §16.
> **Time**: 30-60 minutes for a profiling session

---

## Performance Targets

Per `docs/specs/nucleus_architecture_v4.1.md` §16 (# NEEDS VERIFICATION — refine with `docs/internal/research/performance_reliability_targets.md` when available):

| Metric | Target | Current (2026-05-14) |
|---|---|---|
| Cold boot (`nucleus up`) | < 10 s | ~7 s (WSL, validated in beachhead E2E) |
| `nucleus --version` (import time) | < 1 s | — |
| `nucleus ingest` SQLite 1GB | < 120 s | — |
| `nucleus ingest` Postgres 1GB | < 180 s | — |
| `ctx.sql` query 1GB Iceberg table | < 10 s | — |
| `nucleus run` simple asset | < 5 s overhead (excluding data compute) | — |

---

## Tool 1: Wall-Clock Timing

```bash
# Cold boot time (nucleus up):
Measure-Command { nucleus up }   # PowerShell
time nucleus up                  # bash

# Import time (nucleus CLI cold start):
Measure-Command { nucleus --version }   # PowerShell
time nucleus --version                  # bash

# Materialization overhead:
time nucleus run example.greeting
```

---

## Tool 2: Python Import Time Audit

Slow imports are the #1 cause of slow CLI startup:

```bash
# Per-module import timing:
python -X importtime -m nucleus.cli.main version 2>&1 | sort -rn -k2 | head -20

# Simpler version:
python -X importtime -c "import nucleus" 2>&1 | grep "import nucleus" | head -10
```

**What to look for**: any module taking > 100ms to import. Common culprits:
- Heavy optional deps imported at module level (should be lazy-imported inside functions)
- `import dagster` at module level (should be inside coordination functions only)

**Fix pattern** (lazy import):
```python
# BAD: imports Dagster at module load time
import dagster

def run_asset():
    return dagster.materialize(...)

# GOOD: imports Dagster only when the function is called
def run_asset():
    import dagster  # lazy import; doesn't add to startup time
    return dagster.materialize(...)
```

---

## Tool 3: cProfile for Hot Paths

```bash
# Profile a specific operation:
python -m cProfile -s cumulative -m nucleus.cli.main run my_asset \
  2>&1 | head -40
```

Or from Python:
```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# ... run the operation ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # top 20 most expensive
```

---

## Tool 4: py-spy (Live Attach, No Code Changes)

For profiling a long-running operation without modifying code:

```bash
# Install (not in default deps; use separately):
# NEEDS VERIFICATION: py-spy version and compatibility with Python 3.11
# Docs: https://github.com/benfred/py-spy
pip install py-spy

# Attach to a running nucleus process:
nucleus run big_asset &   # start in background
py-spy top --pid <PID>   # live profile
```

---

## Tool 5: OpenTelemetry Tracing (v0.5+)

When the observability extras are installed:

```bash
pip install nucleus-data[observability]
```

Set an OTLP exporter:
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
NUCLEUS_OTEL_ENABLED=1 \
nucleus run my_asset
```

View traces in Grafana Tempo or Jaeger. This shows per-operation latency across the full stack (DuckDB query time, Iceberg write time, Dagster overhead).

---

## Beachhead E2E Performance Check

The beachhead E2E script (`scripts/beachhead_e2e.py`) includes timing assertions:

```bash
python scripts/beachhead_e2e.py --timing
```

Expected output:
```
Gate 1: nucleus up                 PASS (7.2 s, target < 10 s)
Gate 2: nucleus version            PASS (0.8 s, target < 1 s)
Gate 3: nucleus ingest sqlite://...  PASS (12.3 s, target < 30 s)
...
```

If any gate exceeds its target: investigate with `cProfile` on that specific command.

---

## Benchmark Regression Check

Before merging any PR that touches performance-sensitive code:

```bash
python scripts/benchmark_regression.py
```

This script (if present; verify with `ls scripts/benchmark_regression.py`) compares key metrics against the baseline stored in `.nucleus/benchmark_baseline.json`.

Acceptance: < 10% regression on any metric.

**If no `benchmark_regression.py` exists**: manually time the key operations before and after your change:
```bash
# Before change:
Measure-Command { nucleus run example.greeting } | Select TotalSeconds
# [make change]
# After change:
Measure-Command { nucleus run example.greeting } | Select TotalSeconds
```

---

## DuckDB Query Performance

```python
# Docs: https://duckdb.org/docs/guides/performance/overview.html
import duckdb

conn = duckdb.connect()

# EXPLAIN to see query plan:
conn.execute("EXPLAIN SELECT * FROM read_parquet('path/to/file.parquet')").fetchall()

# EXPLAIN ANALYZE to get actual timing:
conn.execute("EXPLAIN ANALYZE SELECT COUNT(*) FROM read_parquet('path/to/file.parquet')").fetchall()
```

Common DuckDB performance tips:
- Use `read_parquet` with partition pruning for large tables.
- `SELECT` only needed columns (avoid `SELECT *` on large schemas).
- For repeated queries: materialize intermediate results.

---

## MinIO Throughput

For slow ingestion (suspecting I/O bottleneck):

```bash
# MinIO admin — check throughput:
# From MinIO console (http://localhost:9001):
# Monitor → Metrics → Disk Usage, Network Transfer

# Or mc (MinIO client):
mc admin info local
mc du --recursive s3://nucleus-warehouse/
```

---

## Memory Usage

```bash
# Peak memory of nucleus run:
python -m memory_profiler -m nucleus.cli.main run my_asset

# Or with psutil (in dev extras):
# NEEDS VERIFICATION: psutil API for memory tracking
# Docs: https://psutil.readthedocs.io/en/latest/
python -c "
import psutil, subprocess
proc = subprocess.Popen(['nucleus', 'run', 'my_asset'])
p = psutil.Process(proc.pid)
print(p.memory_info().rss / 1024 / 1024, 'MB')
proc.wait()
"
```

---

## Numeric Targets Reference

Cross-reference with `docs/internal/research/performance_reliability_targets.md` when available (Wave 1H output).

Current known targets (per WSL beachhead E2E 2026-05-14):
- Boot time: 7 s actual, 10 s target ✓
- RAM at idle: ~117 MB ✓
- Full beachhead (init → ingest → run → query): < 30 min ✓

---

## References

- `docs/specs/nucleus_architecture_v4.1.md` §16 (Performance Targets)
- DuckDB performance guide: https://duckdb.org/docs/guides/performance/overview.html
- pyiceberg performance notes: https://py.iceberg.apache.org/configuration/
- `docs/internal/research/performance_reliability_targets.md` — target definitions (Wave 1H)
- `scripts/beachhead_e2e.py` — the authoritative E2E timing benchmark
