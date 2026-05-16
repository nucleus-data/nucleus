# Research: OpenTelemetry (OTEL)

> **Status in Nucleus**: **Layer 0 (Physics) — immortal** per `docs/specs/nucleus_architecture_v4.1.md` §4.1. Library (`opentelemetry-api` + `opentelemetry-sdk`) is **already a v0.1 runtime dep** (boot-time tracing, escape-hatch counters); full stack (OTLP → VictoriaMetrics + VictoriaLogs collector) ships v0.5+ per §11.4. Cost meter (v0.5+, §6.3) sits on OTEL metrics.
> **Pin candidate (current)**: `opentelemetry-api==1.29.0`, `opentelemetry-sdk==1.29.0` (in `pyproject.toml`; released **2024-12-11**, verified on PyPI 2026-05-13).
> **Latest stable on PyPI**: `1.41.1` (released **2026-04-24**) — pin **12 minor versions behind**; `1.29.0 → 1.41.x` needs its own ADR (§6).
> **License**: **Apache-2.0** (verified at `raw.githubusercontent.com/open-telemetry/opentelemetry-python/main/LICENSE`, 2026-05-13)  •  **JVM-free**: **YES** — pure Python; transitive deps `Deprecated`, `importlib-metadata`, `typing-extensions`. Hard Constraint #1 satisfied.
> **Research date**: 2026-05-13
> **Used in**: nowhere yet (phase gate per AGENTS.md §11.1). First wire-up lands in the AMA when PoC #1 graduates.

Anchor for AGENTS.md Hard Constraint #10. Read before adding any new tracing/metric/log instrumentation and before any `opentelemetry-*` bump. OTEL is the rare case where we wrap an L0 *protocol*, not an L1 *engine* — wrapping rules differ from DuckDB/Polars/dlt (§7).

---

## §1. What OpenTelemetry is, in Nucleus terms

CNCF spec + Python reference implementation for three signals — **Traces / Metrics / Logs** — plus context propagation (Baggage). Nucleus treats OTEL as a **Layer 0 protocol** alongside Arrow / Iceberg / Parquet / OpenLineage (`v4.1.md` §4.1). We never invent a telemetry wire format; we emit OTLP, users pick the backend.

| Signal | Python status (verified 2026-05-13) | Nucleus use |
|---|---|---|
| **Traces** | **Stable** | Root span per asset materialization; child spans for `ctx.sql`/`read`/`write`, contract checks, Iceberg commit (§4.1–4.2). |
| **Metrics** | **Stable** | Asset / duration / row counters; escape-hatch usage; cost-meter primitives (§4.3). |
| **Logs** | **Development** | Bridge from `structlog` v0.5+ once Python Logs lands GA. v0.1 keeps `structlog` user-facing (§4.4). |
| **Baggage** | Stable | Carries `run_id`, `asset_name`, `openlineage_run_id` across `ctx.*` (§4.4). |
| Events / Profiles | Proposal (Events folded into Logs `event_name`, ≥1.36) | Use Span Events for now. |

| OTEL concept | Nucleus surface |
|---|---|
| `TracerProvider` / `MeterProvider` | Global, lazy-init on first `ctx` use → `coordination/telemetry/__init__.py` (planned). |
| `Tracer` / `Meter` | Hidden — `ctx` opens spans / records metrics inside the AMA. |
| `Span` + attributes | One per materialization; Nucleus vocab only (no raw OSS classnames per §6.4). |
| `Counter` / `Histogram` / `Gauge` | Backs `ctx.metrics` (v0.2+). |
| `LoggerProvider` | **v0.5+** bridge from `structlog`. Deferred. |
| `Resource` | `service.name=nucleus`, `service.version=__version__`, `nucleus.project_id=…` — set at boot. |
| OTLP exporter | Off by default (local-first); user opt-in via `OTEL_EXPORTER_OTLP_ENDPOINT`. |

**OTEL is an API contract, not a vendor.** Emit OTLP; users point any OTLP-compatible backend (VictoriaMetrics, Tempo, Jaeger, Datadog, Honeycomb, Grafana Cloud, X-Ray, Cloud Trace) at it. Nucleus Cloud (v0.5+) defaults to VM + VL.

---

## §2. Official documentation URLs

Verified by `WebFetch` 2026-05-13. Every fact cites this set.

- Main / What-is: https://opentelemetry.io/docs/ • .../../what-is-opentelemetry/
- Signals: https://opentelemetry.io/docs/concepts/signals/ (Traces / Metrics / Logs / Baggage sub-pages)
- Python status + version support: https://opentelemetry.io/docs/languages/python/
- **Python instrumentation (the API surface we wrap)**: https://opentelemetry.io/docs/languages/python/instrumentation/
- Python exporters / propagation: https://opentelemetry.io/docs/languages/python/exporters/ • .../../propagation/
- Python API ref (RTD, per-version): https://opentelemetry-python.readthedocs.io/en/latest/api/trace.html (`metrics.html`, `_logs.html`; leading underscore intentional — Logs pre-GA)
- Spec stability / versioning: https://opentelemetry.io/docs/specs/otel/versioning-and-stability/
- Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/general/trace/ • .../../general/metrics/ • .../../database/
- GitHub / Releases / PyPI: https://github.com/open-telemetry/opentelemetry-python • .../../releases • https://pypi.org/project/opentelemetry-api/ • .../../opentelemetry-sdk/
- Contrib (instrumentations + exporters): https://github.com/open-telemetry/opentelemetry-python-contrib • Collector (v0.5+ stack): https://opentelemetry.io/docs/collector/

**Gotcha**: two API-reference families exist. Cite RTD for Python signatures; the cross-language spec uses pseudo-code — never cite spec snippets as Python signatures.

---

## §3. APIs Nucleus will wrap

Target wrap module: `coordination/telemetry/` (≤300 LOC v0.1; +~300 LOC v0.5 Logs bridge). Verified against §2 docs on 2026-05-13.

### §3.1 SDK setup (called once, on first `ctx` use)

Imports from `opentelemetry`, `opentelemetry.sdk.resources`, `opentelemetry.sdk.trace[.export]`, `opentelemetry.sdk.metrics[.export]` — see https://opentelemetry.io/docs/languages/python/instrumentation/. Sequence: `Resource.create({"service.name":"nucleus","service.version":__version__,"nucleus.project_id":<sha1>})` → `TracerProvider(resource=...)` (effective only on first `trace.set_tracer_provider` call) → `BatchSpanProcessor(exporter)` (`schedule_delay_millis` default `5000` at 1.29.0, **`1000` at 1.41.0**, PR #4998) → `MeterProvider(metric_readers=[reader], resource=...)` → `PeriodicExportingMetricReader(exporter, export_interval_millis=60000)`.

### §3.2 Tracer API (`ctx.materialize`, `ctx.sql`, …)

Signatures verified at 1.29.0 against https://opentelemetry.io/docs/languages/python/instrumentation/.

| Symbol | Use |
|---|---|
| `trace.get_tracer(name, version=None, schema_url=None)` | `tracer = trace.get_tracer("nucleus")` once per module. |
| `tracer.start_as_current_span(name, context=None, kind=SpanKind.INTERNAL, attributes=None, links=None, record_exception=True, set_status_on_exception=True)` — **context manager** | Workhorse. §4.1. |
| `tracer.start_span(...)` | Non-context; spans outliving the caller (async hand-offs). |
| `Span.set_attribute(key, value)` | `value` ∈ `str/bool/int/float` or homogeneous sequence; else coerces/drops. |
| `Span.add_event(name, attributes=None, timestamp=None)` | Point-in-time markers (`"contract.validated"`, `"snapshot.committed"`). |
| `Span.record_exception(exc, attributes=None, escaped=False)` + `Span.set_status(Status(StatusCode.ERROR))` | Called by Error Translation Layer **after** mapping to `NucleusError`. `from opentelemetry.trace import Status, StatusCode`. |
| `trace.get_current_span()` / `trace.Link(span_context)` | Enrichment from arg-less helpers / link backfill or sensor-triggered runs to their trigger. |

### §3.3 Meter API (`ctx.metrics` v0.2+, cost meter v0.5+)

`metrics.get_meter("nucleus")` once per module. Factories: `create_counter(name, unit="1", description="")` → `Counter.add(amount, attrs)`; `create_up_down_counter(...)`; `create_histogram(name, unit, description)` → `Histogram.record(value, attrs)`; `create_observable_gauge(name, callbacks=[fn], unit, description)` for periodic snapshots (catalog table count, idle RAM).

### §3.4 Logs API (v0.5+ — currently **Development**)

Namespaced under `_logs` (underscore intentional — pre-GA, https://opentelemetry.io/docs/languages/python/). At 1.29.0 `ConsoleLogExporter`; **renamed `ConsoleLogRecordExporter` in 1.39.0** (PR #4647). v0.1 keeps `structlog==24.4.0` user-facing; OTEL Logs bridge plumbed v0.5 once Python promotes Logs to Stable, or via explicit ADR accepting pre-GA churn.

---

## §4. Integration points with Nucleus

### §4.1 `ctx.materialize` → one root trace span per asset run

Per `v4.1.md` §6.1 (AMA, ~500 LOC). Target: `coordination/ama.py`. Open one root span named `nucleus.asset.materialize`, `kind=SpanKind.INTERNAL`, with attributes `nucleus.asset` (e.g. `"sales.fct_orders"` — **never** the Dagster op name), `nucleus.materialization_mode` (`table` / `view` / `incremental` / `snapshot`), `nucleus.engine` (`duckdb` / `polars` / `datafusion`), `nucleus.run_id`. On success, add `nucleus.iceberg.snapshot_id` and `nucleus.rows_written`. On `NucleusError`: `span.record_exception(e); span.set_status(Status(StatusCode.ERROR))` (the translator has already mapped wrapped-OSS exceptions; `__cause__` preserved). Docs: https://opentelemetry.io/docs/languages/python/instrumentation/#creating-spans.

**Discipline**: span/attribute names follow Nucleus vocabulary (AGENTS.md §7). **No `dagster.*` / `duckdb.*` / `polars.*` / `pyiceberg.*` namespaces in attributes** — those leak wrapped-library identity into Grafana/Jaeger, defeating §6.4 Error Translation. Per `v4.1.md` §6.6, escape-hatch usage **is** tracked here (`nucleus.escape_hatch={feature}`), giving the >5%/3-month replacement trigger its data.

### §4.2 `ctx.sql` → child span carrying the SQL

Child span `nucleus.ctx.sql`; attributes `nucleus.sql.dialect`, `nucleus.sql.statement` (redacted), `nucleus.sql.statement_hash` (`sha256(raw)[:16]`), `nucleus.engine`, `nucleus.rows_returned`.

**PII rule**: never set raw SQL containing user data. Run through the Jinja resolver's redaction pass (`{{ param.* }}` typed, secrets substituted at param-binding time per `docs/specs/nucleus_ctx_sdk_spec.md` §5). Long statements: hash + first ~200 chars; backends truncate ~1-4 KB anyway. Semconv key is `db.statement` (https://opentelemetry.io/docs/specs/semconv/database/) — we **prefix `nucleus.` instead** so vendor-classname leak risk doesn't sneak into attribute keys. Revisit at v0.5.

### §4.3 Mandatory metrics (v0.2 surface, cost meter v0.5+)

Names follow OTEL semconv (https://opentelemetry.io/docs/specs/semconv/general/metrics/): lowercase, dot-separated, unit in `unit=`, plural for countable nouns.

| Metric (OTEL dot-namespace) | Kind | Unit | Attributes |
|---|---|---|---|
| `nucleus.assets.materialized` | `Counter` | `1` | `asset`, `result={ok,error}`, `materialization_mode` |
| `nucleus.asset.materialization.duration` | `Histogram` | `s` | `asset`, `engine` |
| `nucleus.asset.rows_written` | `Histogram` | `1` | `asset` |
| `nucleus.escape_hatch.calls` | `Counter` | `1` | `feature` |
| `nucleus.snapshot.commit.duration` | `Histogram` | `s` | `table` |
| `nucleus.runtime.boot` | `Histogram` | `s` | `subsystem` |
| `nucleus.cost.compute_seconds` (v0.5+) | `Counter` | `s` | `asset`, `engine` |

**Naming reconciliation**: the user spec uses Prom-style snake_case (`assets_materialized_total`, `materialization_duration_seconds`); OTEL semconv prefers dot-namespace. The OTEL Prometheus exporter auto-rewrites dots to underscores and appends `_total` / `_seconds` — on-the-wire Prom names are identical (`nucleus_assets_materialized_total`, `nucleus_asset_materialization_duration_seconds`). We use **dot-namespace on the OTEL side**, let the exporter rewrite. Lock in the AMA PR.

### §4.4 Log correlation with OpenLineage event IDs

Per asset materialization we emit one OL `runEvent` with UUID `run.runId`. To stitch traces ↔ lineage ↔ logs, plant the OL run id as **both** span attribute and baggage entry (`from opentelemetry import baggage`; https://opentelemetry.io/docs/concepts/signals/baggage/): `baggage.set_baggage("nucleus.openlineage.run_id", ol_run_id)`; `span.set_attribute("nucleus.openlineage.run_id", ol_run_id)`; bind both `openlineage_run_id` and `trace_id` (= `span.get_span_context().trace_id`, hex-formatted per §8) into every `structlog` record. `structlog==24.4.0` gets a processor that pulls `trace_id`/`span_id` from the current span — same shape OTEL Logs bridge produces later, so v0.5 swap is a no-op for downstream consumers. The OL `runEvent` carries OTEL `trace_id` in `facets.environment` per OL↔OTEL convention (confirm when `openlineage.md` lands).

### §4.5 v0.5+: Nucleus Cloud collector destination

OTLP/gRPC and OTLP/HTTP exporters are available today but **not pinned in v0.1** (locked behind v0.5 ADR). Default destinations once wired: **VictoriaMetrics** (metrics; native OTLP — confirm at https://docs.victoriametrics.com/) and **VictoriaLogs** (logs; native OTLP/HTTP — confirm at https://docs.victoriametrics.com/victorialogs/) for Nucleus Cloud; OSS users target whatever they have (Jaeger, Tempo, Grafana, Datadog, Honeycomb, cloud-vendor — all accept OTLP via standard `OTEL_EXPORTER_OTLP_*` env vars).

**v0.5 in scope**: pin one of `opentelemetry-exporter-otlp-proto-{grpc,http}` (≤30 LOC config); ship `docker-compose.observability.yml` with VM+VL for local sanity; document env-var matrix in `docs/specs/nucleus_cli_spec.md`. **Out of scope until v0.7+ Cloud GA**: hosting the collector, signed multi-tenant ingest, retention/quota.

---

## §5. Performance characteristics

No Nucleus benchmark yet — re-measure under PoC #4 conditions before quoting.

- **`api` import**: ~10–30 ms; zero exporter deps. Safe on v0.1 boot path.
- **`sdk` import**: ~80–150 ms; `TracerProvider`+`MeterProvider` init <10 ms warm. Within PoC #4 `nucleus up <10s`; **lazy-init SDK on first `ctx` call**, not at `import nucleus`.
- **Span overhead**: ~1–5 µs with SDK loaded + `BatchSpanProcessor` + no exporter reachable (queue drops, never blocks — 32 s post-retry sleep removed in 1.36, PR #4564). Noise vs our `ctx.sql` hot path (~10–100 µs/row).
- **Metric record overhead**: <1 µs synchronous; export every 60 s.
- **`BatchSpanProcessor.schedule_delay_millis`**: 5000 at 1.29.0 → **1000 at 1.41.0** (PR #4998). **5× more frequent exports** on upgrade — flag for metered-egress users.

**Cardinality is the worry, not per-call cost.** Asset names → attributes → one time-series per combination. v0.5 lint: warn on unbounded-cardinality attribute values; budget cardinality per project.

---

## §6. Compatibility with Nucleus pins (2026-05-13)

### §6.1 Current pin (already in `pyproject.toml`) — `opentelemetry-api==1.29.0`, `opentelemetry-sdk==1.29.0`

`api` + `sdk` are version-locked together. Python `>=3.11,<3.13` (Nucleus) vs `>=3.9` (OTEL 1.29.0 PyPI metadata) — no conflict. `opentelemetry-semantic-conventions` is **not pinned** (matches sdk transitively); pin alongside in next upgrade PR — semconv re-versions ~6 weeks (1.36 → 1.40 in our window). OTLP exporters and `opentelemetry-instrumentation-*` are **not pinned**; each lands in a dedicated v0.5 ADR. `structlog==24.4.0` is independent — it keeps owning user-facing logs in v0.1.

### §6.2 Latest stable on PyPI

`1.41.1`, uploaded **2026-04-24T13:15:15Z**, `Development Status :: 5 - Production/Stable`, `requires_python >=3.9`. Cadence: monthly (12 minors in 17 months).

### §6.3 Upgrade implications (`1.29.0 → 1.41.x` needs an ADR per Hard Constraint #11)

Traces + Metrics APIs stable in the window. **Logs SDK churned hard** and **default span-export cadence changed**. From `github.com/open-telemetry/opentelemetry-python/releases` (read 2026-05-13):

- **1.41.0 (2026-04-09)** — `BatchLogRecordProcessor.schedule_delay_millis` 5000 → 1000 (PR #4998).
- **1.40.0 (2026-03-04)** — Breaking: `NoOpTracer.start_span`/`start_as_current_span` propagate current span context (PR #4861). `LoggingHandler` deprecated for `opentelemetry-instrumentation-logging`. Python 3.14 supported.
- **1.39.0 (2024-12-03)** — Breaking: `Log* → LogRecord*` renames (PR #4647); `LogData` removed (PR #4676); `ConsoleLogExporter` → `ConsoleLogRecordExporter`.
- **1.36.0 (2024-07-11)** — `LogRecordProcessor.emit` → `on_emit` (PR #4648); OTLP retry/backoff tightened.

**Recommended one-component-per-PR sequencing**: (A) `1.29.0 → 1.36.0` (pin semconv alongside) — smoke-test Traces+Metrics; (B) `1.36.0 → 1.39.0` — Logs rename; (C) `1.39.0 → 1.41.1` — surface cadence change. ADR: `docs/decisions/ADR-NNN-opentelemetry-1.29-to-1.41.md`. **No upgrade is functionally needed for v0.1** — 1.29.0 covers the Traces + Metrics surface §3 wraps. Pressure rises only when we wire Logs (v0.5+) or pull an OTLP exporter.

---

## §7. Swap-target analysis (`v4.1.md` §9.3) — Tier 0 (no swap)

**Tier**: Tier 0 (immortal) per §9.2 ("Arrow, Iceberg, Parquet, Lance, S3 API, OpenLineage, OpenTelemetry"). **Swap target maintained? No.** Tier 0 components do not have swap targets; they *are* the standards.

**Risk if OTEL dies?** ~Zero. CNCF Top-Level (Aug 2021), 90+ vendor backends, dual implementations in every major language, OTLP de-facto.

**If the Python implementation stagnates?** Library ≠ implementation. We could swap to a custom ~100-LOC OTLP emitter for our small surface (Counter/Histogram + Span/Event/Link ≈ 6 wire messages). Build trigger: maintenance stall ≥6 mo + critical CVE unpatched. Est: 500–1000 LOC.

**Vendor offers "better than OTLP"? Reject.** `v4.1.md` §4.2: "we never depend on a single-vendor 'open standard'." Vendor shims (Datadog StatsD, NR Insights, Splunk HEC) are user opt-ins via OTEL Collector — never first-class Nucleus.

**Skip OTEL entirely?** Considered, rejected. Costs: (a) `ctx.metrics` has no clean backend; (b) cost meter (v0.5+) needs structured primitives; (c) AI Copilot run-replay (v0.7+) needs span structure; (d) we'd reinvent context propagation for MCP server (v0.5+).

**No `/docs/swap/opentelemetry.md` stub needed.** Tier 0 is explicitly outside the swap-interface discipline.

---

## §8. Known gotchas + AI hallucination risks

Log every catch in `docs/internal/research/ai_hallucinations.md` per AGENTS.md §11.12.

### Likely AI hallucinations (verify before merge)

- ❌ **OTEL ≠ Datadog Python SDK / `ddtrace` / OpenCensus.** OTEL is always `from opentelemetry import trace, metrics, baggage`. Datadog's *OTLP receiver* accepts OTEL emission; Datadog SDK calls are forbidden. OpenCensus merged into OTEL in 2019 — `import opencensus` is dead.
- ❌ **OTEL ≠ `prometheus_client`.** `prometheus_client.Counter("foo").inc()` is a different API. OTEL exposes a Counter via `meter.create_counter(...)`; the OTEL Prometheus *exporter* converts on the wire.
- ❌ `opentelemetry.start_trace(...)`, `span.set_tag(k,v)`, `span.log_kv({...})`, `meter.counter("name").inc()`, `metrics.gauge("name", value)` — all fabricated / Jaeger-Zipkin-isms. Correct: `tracer.start_as_current_span(...)`, `span.set_attribute(...)`, `span.add_event(name, attributes={...})`, `c = meter.create_counter("name"); c.add(1, {...})`. (No synchronous Gauge prior to 1.27.)
- ❌ Logs SDK rename traps: at ≥1.39 `ConsoleLogExporter → ConsoleLogRecordExporter` (PR #4647); `LogData` removed (PR #4676; use `ReadableLogRecord` / `ReadWriteLogRecord`); at ≥1.36 `LogRecordProcessor.emit → on_emit` (PR #4648).
- ❌ `tracer.start_as_current_span(...)` outside `with` returns an unentered context-manager, not a Span. Use `start_span` for that.
- ❌ `OTEL_TRACES_SAMPLER=AlwaysOn` — case matters; correct is `always_on`.
- ❌ Assuming `opentelemetry-semantic-conventions` is auto-installed by `api` — separate package; pin explicitly when first used.
- ❌ `str(span.context.trace_id)` yields decimal. OTLP wire format is **16-byte hex**: `format(trace_id, '032x')` for trace_id, `'016x'` for span_id.
- ❌ Treating `opentelemetry-instrumentation-*` as shipped with `opentelemetry-sdk` — they live in `opentelemetry-python-contrib`, aren't pinned today. Each addition needs its own ADR.

### Real gotchas from official docs

- **Logs API "Development" in Python** (https://opentelemetry.io/docs/languages/python/, 2026-05-13) — breaking changes allowed per spec. Wire at v0.5.
- **Attribute value types** at 1.29.0: non-`str/bool/int/float` (or homogeneous sequences) coerce or drop; 1.34.0 (PR #4808) more permissive.
- **Global state**: `trace.set_tracer_provider(p)` is effective only on first call; subsequent calls log a warning. Boot order matters. `Span.is_recording()` is cheap; call before building expensive attribute payloads.
- **Async**: default `ContextVar` propagator handles `asyncio`; for `threading.Thread` you must `context.attach(context.get_current())` in the target. v0.1 runtime sync.
- **`BatchSpanProcessor.shutdown()`**: at 1.29.0 "export until empty" semantics; 1.35.0+ caps at 30 s (PR #4638). `nucleus down` calls shutdown last. **OTLP retry** at 1.36+ adds +/-20% jitter + timeout inclusive of retries (PR #4564) — different at 1.29.0.

---

## §9. Decision log

**Why OpenTelemetry — not custom, not Prometheus-only, not vendor SDK:** No JVM, pure Python (Hard Constraint #1; vendor agents JVM-free but proprietary). Layer 0 immortality — CNCF Top-Level, ≥90 vendor backends, multi-vendor steering (`v4.1.md` §4.1, §9.2). One library, three signals — custom telemetry means reinventing context propagation (≥1 kLOC) or shipping three libs. AI Copilot run-replay (v0.8+, `v4.1.md` §1.3 row 17) needs a span graph keyed by run id; MCP server (v0.5+) needs distributed propagation (W3C Trace Context + Baggage out of the box); cost meter (v0.5+) needs structured metric primitives. Yield-to-giants: Databricks, Snowflake, AWS, GCP, Azure, Datadog, Honeycomb, Grafana Cloud, Tempo, Jaeger all ingest OTLP.

**Why pin OTEL in v0.1 (not deferred to v0.5)**: §6.6 escape-hatch tracking needs telemetry day-one; §11.4 (Disconnected Operation) needs the SDK locally; PoC #4 boot-time histogram. Lazy import keeps cold-start <30 ms (api only) until first `ctx` call.

**Why NOT pin OTLP exporters in v0.1**: local-first beachhead — no network telemetry on `git clone → first table in 30 min`. gRPC exporter pulls `grpcio` (~30 MB wheel) for zero beachhead value.

**Why defer Logs API to v0.5**: Python Logs is **Development** with three breaking changes in our pin window. `structlog` is stable. No churn cost for zero v0.1 gain.

---

## §10. Next reads when v0.5 observability work starts

- [ ] **VictoriaMetrics** + **VictoriaLogs** — ingest APIs, retention, cardinality limits, OTLP receiver maturity. Write `docs/internal/research/victoriametrics.md` and `docs/internal/research/victorialogs.md`. https://docs.victoriametrics.com/ • https://docs.victoriametrics.com/victorialogs/
- [ ] **OTEL Collector** (`opentelemetry-collector-contrib`): OTLP receivers + `prometheusremotewrite`/`otlp` exporters for VM/VL. Default `otel-collector.yaml` in the Cloud helm chart.
- [ ] **Pin OTLP exporter** — `opentelemetry-exporter-otlp-proto-http==<latest>` (HTTP/Protobuf, JVM-free, gRPC-free). ADR.
- [ ] **`opentelemetry-instrumentation-logging`** (replaces deprecated `LoggingHandler` ≥1.40): wire `structlog` through it.
- [ ] **Semantic conventions audit** — `.../../database/` + `.../../general/metrics/`. Decide which `nucleus.*` attributes rename to standard `db.*` / `code.*` keys.
- [ ] **Re-fetch latest OTEL Python release** and re-run §6.3 — releases monthly; will have drifted.
- [ ] **OpenLineage ↔ OTEL trace_id convention** once `docs/internal/research/openlineage.md` lands. Co-design with §4.4.
- [ ] **MCP server propagation** (`v4.1.md` §18.4): how MCP clients pass W3C Trace Context into `ctx`.
- [ ] **AI Copilot cost audit** (AGENTS.md §9 stop-condition: token cost >30% of Cloud margin): OTEL spans are the ground truth.

---

*Last verified: 2026-05-13 against `opentelemetry-api / opentelemetry-sdk == 1.29.0` (pinned in `pyproject.toml`) and latest `1.41.1` on PyPI. Re-verify when (a) opening the v0.5 observability ADR, (b) opening the `1.29 → 1.41` upgrade ADR, or (c) any major bump (`1.x → 2.x`). Log AI-fabricated OTEL APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
