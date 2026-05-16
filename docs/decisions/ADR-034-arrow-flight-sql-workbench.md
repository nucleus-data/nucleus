# ADR-034: Arrow Flight SQL Endpoint for Workbench

**Status**: PROPOSED  
**Date**: 2026-05-15  
**Author**: Synthesis — ratification required from founder  
**Priority**: P2  
**Target phase**: v0.3  
**Source research**: `docs/internal/research/inspiration/storage_formats_2026.md` §8; `docs/internal/research/inspiration/embedded_analytics_bi.md` §7  
**Synthesis reference**: `docs/internal/research/inspiration/ADOPTION_SHORTLIST.md` §3 #10, §2.7

---

## Context

The Workbench v0.2 REST API returns query results as JSON. For analytics-scale result sets (100K+ rows), JSON serialisation is the dominant cost. Arrow Flight SQL is a binary SQL database protocol over gRPC/HTTP2 using native Arrow RecordBatches.

**Why `pyarrow` is already sufficient**: `pyarrow==18.1.0` is already in `pyproject.toml`. `FlightServerBase` exists in this version. A JDBC driver ships with Arrow since v10.0.0. ADBC client library (`adbc_driver_flightsql`) allows BI tools (Superset, Tableau, DBeaver) to connect without custom drivers.

**Performance**: >80% serialisation overhead reduction vs JDBC/JSON for analytics-scale result sets (R8 §8.1, Dremio blog benchmark).

**Key implementation constraint** (R8 §8.2): No native Python Flight SQL server library exists. `FlightServerBase` provides raw Flight RPC but NOT the Flight SQL protocol layer (catalog metadata endpoints, statement routing). Must manually implement Flight SQL message parsing on top of raw Flight RPC. Arrow issue #37700 tracking Python Flight SQL server helpers was closed as not-planned February 2026. This adds ~150 LOC of protocol glue.

**gRPC server lifecycle**: `FlightServerBase` runs a gRPC server in a background thread; must coexist with uvicorn (FastAPI). Clean solution: separate port (`:8766` Flight, `:8765` REST).

This is **additive only** — existing JSON REST stays for CLI and browser clients.

---

## Options Considered

| Option | Description | Reason considered/rejected |
|---|---|---|
| **A — Flight SQL on port :8766 (additive)** | ~500 LOC; `pyarrow.FlightServerBase`; 4 components (SQL metadata handlers + statement execution + tests); 1 new dev dep | ✅ SELECTED — additive; uses existing `pyarrow` pin; BI tool multiplier |
| B — Add Arrow IPC to HTTP layer | Return `application/vnd.apache.arrow.stream` from REST endpoints | ❌ REJECTED — breaks CLI and browser JSON clients; opt-in header approach is safer |
| C — Defer to v0.5 | No binary protocol until v0.5 | ⚠️ POSSIBLE ALTERNATIVE — if beachhead BI tools confirm ADBC adoption before v0.3; downgrade priority if no confirmed demand |

---

## Decision

**[PLACEHOLDER — awaiting founder ratification]**

Recommended: **Option A** at v0.3, conditional on at least one beachhead BI tool confirming ADBC adoption before v0.3 planning starts. If no confirmed demand, defer to v0.5 (change priority to P3).

Implementation scope (R8 §8.3):
- `FlightServerBase` subclass + DuckDB query wiring: ~150 LOC
- SQL metadata handlers (`GetSqlInfo`, `GetDbSchemas`, `GetDbTables`): ~100 LOC
- Statement execution (`GetFlightInfo` + `DoGet` streaming): ~150 LOC
- Integration tests: ~100 LOC

1 new dev dependency: `adbc-driver-flight-sql` — **NEEDS VERIFICATION**: current PyPI version + Python 3.11 compatibility (R8 NV-7: https://pypi.org/project/adbc-driver-flight-sql/).

**Must read official specs before writing any code:**
- Arrow Flight SQL spec: https://arrow.apache.org/docs/format/FlightSql.html
- PyArrow FlightServerBase: https://arrow.apache.org/docs/python/generated/pyarrow.flight.FlightServerBase.html
- ADBC Flight SQL driver: https://arrow.apache.org/adbc/current/python/api/adbc_driver_flightsql.html

---

## Consequences

- **LOC budget impact**: ~500 LOC (`src/nucleus/workbench/flight_sql.py`)
- **1 new dev-only dependency**: `adbc-driver-flight-sql` (version TBD — verify NV-7)
- **No new runtime dependency** (`pyarrow` already pinned)
- **Additive**: Existing JSON REST endpoints unchanged
- **Depends on**: ADR-026 (`nucleus.db` BI handshake) for the overall BI integration story

## Architecture Sections Touched

- `nucleus_architecture_v4.1.md` §7.2 (Workbench API layer)
- `nucleus_architecture_v4.1.md` §18.3 (v0.3 roadmap — Workbench v0.3)
