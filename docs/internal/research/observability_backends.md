# Observability Backends (VictoriaMetrics + VictoriaLogs + Marquez) — Research Notes

> **Component status in Nucleus**: **v0.5+ optional observability stack.** Off by default; opt-in via `nucleus enable obs` (reserved in [`docs/specs/nucleus_cli_spec.md`](../specs/nucleus_cli_spec.md) §`enable`). v0.1-v0.3 has **no** backend — OL writes JSONL to `.nucleus/lineage/` ([`openlineage.md`](./openlineage.md) §5.3), OTEL exports to console ([`opentelemetry.md`](./opentelemetry.md) §4.5). Per `docs/specs/nucleus_architecture_v4.1.md` §11 (Local-First Guarantee — §11.2 boot budget, §11.4 telemetry buffer-and-flush) + §4.1 (OTEL = Tier 0 protocol) + AGENTS.md §4 ("Custom observability backend → use OpenTelemetry + VictoriaMetrics + VictoriaLogs"). Tier 2 (wrappable, swappable) per v4.1 §9.
> **Pin candidates (2026-05-13)**: see §2.1. None pinned in `pyproject.toml` — all three are external service binaries / images, not Python deps.
> **License**: **Apache-2.0** for all three (verified against raw `LICENSE` files §2.1).
> **JVM-free?** Mixed: VM + VL are Go single-binaries (Constraint #1 ✓). **Marquez = Java 17 + Postgres** — explicit exception parallel to [`polaris.md`](./polaris.md) §1: external sidecar, not in core path. See §2.3 + §9.
> **Research date**: 2026-05-13  •  **Used in**: nowhere yet. Pre-research artifact for the v0.5 observability ADR.

Official-docs anchor per AGENTS.md Hard Constraint #10. Bundle = **wrap-not-build** for three co-deployed services: telemetry + logs + lineage UI (Pillar #2). We will never write our own TSDB, log indexer, or lineage server.

---

## §1. What this stack is, in Nucleus terms

Three loosely-coupled services covering the three signals Nucleus emits: **metrics**, **logs**, **lineage**. All sit at L0 (Physics) as external binaries — `ctx` never imports them. **OpenTelemetry** is the wire format for the first two (`opentelemetry.md` §1, §4.3); **OpenLineage** for the third (`openlineage.md` §1, §5.3). Per v4.1 §4.1, OTEL + OL are Tier 0 **protocols**; the backends are Tier 2 — swappable while the wire format stays fixed.

Traces are deferred. OTEL spans are emitted but have no first-class backend until v0.7+ Cloud — VictoriaTraces is **Preview** per https://docs.victoriametrics.com/ landing (2026-05-13); Tempo/Jaeger remain user opt-in via `OTEL_EXPORTER_OTLP_*` env vars. The v0.5 `obs` module ships metrics + logs + lineage only.

The three are co-deployed but loosely coupled: no shared schema. The join key is the **OpenLineage `run.runId` (UUIDv7)** — also planted in OTEL Baggage + every `structlog` record per `opentelemetry.md` §4.4. That one ID is what makes them feel like a stack instead of three monitoring tools.

---

## §2. Per-component overview

### §2.1 Versions, licenses, runtimes (verified 2026-05-13)

| Component | Latest release | Released | License | Runtime | Image |
|---|---|---|---|---|---|
| **VictoriaMetrics** | `v1.143.0` (community); `v1.136.x` LTS (12-mo support) | 2026-05-08 | Apache-2.0 (verified `Copyright 2019-2026 VictoriaMetrics, Inc.` at https://raw.githubusercontent.com/VictoriaMetrics/VictoriaMetrics/master/LICENSE) | Go single-binary; pure-Go build (`CGO_ENABLED=0`) | `docker.io/victoriametrics/victoria-metrics` |
| **VictoriaLogs** | `v1.50.0` | 2026-04-14 | Apache-2.0 (verified at https://raw.githubusercontent.com/VictoriaMetrics/VictoriaLogs/master/LICENSE) | Go single-binary | `docker.io/victoriametrics/victoria-logs` |
| **Marquez** | **`0.50.0`** — last *Released* tag (un-released `0.51.0` / `0.51.1` tags exist) | **2024-10-24** — ⚠️ **18 months stale** | Apache-2.0 (verified at https://raw.githubusercontent.com/MarquezProject/marquez/main/LICENSE) | **Java 17 + PostgreSQL 14** | `docker.io/marquezproject/marquez` (latest tag pushed ~May 2025 per Docker Hub) |

Sources: VM at https://github.com/VictoriaMetrics/VictoriaMetrics/releases; VL at https://github.com/VictoriaMetrics/VictoriaLogs/releases — **VL has a separate repo** since 2025 (AI agents will hallucinate `VictoriaMetrics/VictoriaMetrics/.../logstorage` paths — dead). Marquez `/releases/latest` API → `tag_name: 0.50.0`; tags `0.51.0`/`0.51.1` exist with **no Release cut** — don't pin. Marquez health: latest commit `2026-04-12` — *active* but *release cadence stalled* 18 months. 2,188 stars; LF AI & Data **Graduated**.

### §2.2 Default ports + endpoints

| Component | Port | OTLP/OL endpoint | UI |
|---|---|---|---|
| VictoriaMetrics single-node | `:8428` | `POST /opentelemetry/v1/metrics` (OTLP/HTTP protobuf; gzip via `Content-Encoding`) — https://docs.victoriametrics.com/victoriametrics/integrations/opentelemetry/ | `/vmui` |
| VictoriaLogs single-node | `:9428` | `POST /insert/opentelemetry/v1/logs` (OTLP/HTTP) — https://docs.victoriametrics.com/victorialogs/data-ingestion/opentelemetry/ | `:9428/select/vmui` |
| Marquez API (Docker) | `:5000` (admin `:5001`) | `POST /api/v1/lineage` (OpenLineage events) — https://marquezproject.github.io/marquez/openapi.html | n/a |
| Marquez Web UI | `:3000` | n/a | the lineage graph |

**Source-build Marquez** uses `:8080`/`:8081`; **Docker Compose remaps to `:5000`/`:5001`**. AI agents conflate. `/api/v1/lineage` is Marquez's REST API, not the OL spec itself — OL mandates only the JSON payload shape. Marquez also exposes `/api/v1/{namespaces,jobs,datasets}` that we read from for the Workbench (v0.2+) graph view.

### §2.3 Marquez JVM exception — same justification as Polaris

Constraint #1 forbids JVM **in Nucleus's core path**. Marquez is Java 17. Resolution identical to [`polaris.md`](./polaris.md) §1 + ADR-002 §6: opt-in external sidecar in its own container is **not** in the core path. Never blocks `nucleus up`; never counts against v0.1's <500 MB idle / <10 s boot budget (v4.1 §11.2). JVM heap (typ. 1-2 GB) lives outside Nucleus's RAM accounting, identical to external Postgres or Polaris. Document in the v0.5 ADR; do not re-litigate. VM + VL satisfy Constraint #1 unconditionally.

---

## §3. Integration with Nucleus pipelines

### §3.1 OTEL → VictoriaMetrics (metrics)

Per `opentelemetry.md` §4.5: pin `opentelemetry-exporter-otlp-proto-http` in the v0.5 ADR; default endpoint `${OTEL_EXPORTER_OTLP_METRICS_ENDPOINT}=http://victoriametrics:8428/opentelemetry/v1/metrics`. Resource attributes (`service.name=nucleus`, `service.version=__version__`, `nucleus.project_id`) auto-promoted to labels per https://docs.victoriametrics.com/victoriametrics/integrations/opentelemetry/.

Metrics Nucleus emits (from `opentelemetry.md` §4.3; OTEL dot-namespace → VM Prom exporter rewrites to `_underscore_` + `_total`/`_seconds` suffixes): `nucleus.assets.materialized` (Counter, KPI), `nucleus.asset.materialization.duration` (Histogram), `nucleus.asset.rows_written`, `nucleus.escape_hatch.calls` (drives v4.1 §6.6 replacement trigger), `nucleus.snapshot.commit.duration` (Iceberg hot path), `nucleus.runtime.boot` (`nucleus up <10 s`), `nucleus.cost.compute_seconds` (v0.5+ cost-meter input, v4.1 §6.3).

**Naming flag** for v0.5 ADR: `-opentelemetry.usePrometheusNaming` (full OTLP→Prom rewrite). Default **off** in OSS Compose for least surprise; **on** in v0.7+ Cloud where Grafana assumes Prom names. **Temporality**: VM "works best with cumulative"; OTEL Python SDK 1.29.0 defaults to cumulative — no action. Future delta-emitting contrib routes through OTEL Collector `deltatocumulativeprocessor`.

### §3.2 OTEL → VictoriaLogs (logs)

VL accepts OTLP/HTTP at `/insert/opentelemetry/v1/logs` on `:9428`. Per https://docs.victoriametrics.com/victorialogs/data-ingestion/opentelemetry/, OTEL resource labels become **log stream fields**; override via `VL-Stream-Fields` header. Natural stream-field set for Nucleus is `service.name,nucleus.project_id,nucleus.environment`; high-cardinality fields (`nucleus.asset`, `nucleus.run_id`) stay as regular log fields.

Per `opentelemetry.md` §3.4 + §4.4, OTEL Logs Python SDK is **Development**; breaking renames (`Log*`→`LogRecord*`, `emit`→`on_emit`) land between 1.29.0 → 1.39.0. v0.5 plan: **if** Python Logs API is Stable at ADR time, wire `structlog`→OTEL Logs→OTLP/HTTP→VL; **otherwise** ship a thin `structlog` JSON-line exporter POSTing directly to VL's `/insert/jsonline` (~30 LOC, zero new pins). Migrates later without user-API churn.

Log fields emitted (correlated with OL via `run_id`): `level, message, asset, run_id (= OL run.runId), trace_id, span_id, nucleus.materialization_mode, nucleus.engine, error.type, error.user_message`. `error.cause` (raw wrapped-OSS exception per v4.1 §6.4) is **NOT** emitted by default — credential-shape risk; v0.5 ADR decides redact-and-ship vs drop. Per [`docs/patterns/secret_management.md`](../patterns/secret_management.md), anything crossing trust boundary passes the redaction filter.

### §3.3 OpenLineage → Marquez (lineage)

Per `openlineage.md` §4 + §5.3: AMA wraps `OpenLineageClient(transport=HttpTransport(HttpConfig(url="http://marquez-api:5000", endpoint="api/v1/lineage", timeout=5.0, compression="gzip")))`. Marquez consumes OL `RunEvent` JSON directly — **reference implementation** of OpenLineage per its `README.md` "Status".

Events Marquez surfaces: **Run state graph** (six exact states per `openlineage.md` §4); **Input/output Datasets** as clickable nodes; **Schema facets** in per-dataset view; **Column-lineage facets** (`ColumnLineageDatasetFacet`; key `columnLineage`; `DIRECT`/`INDIRECT` transformations; rendered since Marquez `0.47.0` "Redesigned Web UI Featuring Column Lineage"); **Job facets** (`sourceCode`, `sql_job`, `nominal_time_run`).

**OL spec ↔ Marquez compat** per Marquez README: `UNRELEASED` main = `CURRENT` (OL `2-0-2`); `0.50.0` = `RECOMMENDED` (OL `2-0-2`); `0.49.0` = `MAINTENANCE`. OL spec version matches our `openlineage.md` §1 pin (`2-0-2`). No shear between OL Python client `1.47.1` and Marquez `0.50.0`.

### §3.4 v0.1-v0.3 fallback (no backend)

| Signal | v0.1-v0.3 behaviour | Upgrade trigger |
|---|---|---|
| Lineage (OL) | `FileTransport` → `.nucleus/lineage/events.jsonl`; `jq` greppable | v0.5 ADR or earlier `nucleus enable marquez` opt-in |
| Metrics (OTEL) | `ConsoleMetricExporter` to stderr | v0.5 ADR pins OTLP/HTTP exporter |
| Logs | `structlog==24.4.0` JSON to stderr; no OTLP | v0.5 ADR per §3.2 |
| Traces | OTEL spans created but not exported | **Out of scope until v0.7+** — VictoriaTraces still Preview |

Preserves the 30-min beachhead (v4.1 §1.5): zero infra; lineage in JSONL; metrics in `nucleus runs <id> --verbose`.

---

## §4. Deployment patterns

### §4.1 Local dev — `nucleus enable obs`

Reserved per `docs/specs/nucleus_cli_spec.md` line 394. v0.5 ADR emits `docker-compose.observability.yml` extending the user's `docker-compose.yml` with **four** services:

| Service | Image | Idle RAM (rough) | Port |
|---|---|---|---|
| `victoriametrics` | `victoriametrics/victoria-metrics:v1.143.0` | ~50-150 MB | `8428` |
| `victorialogs` | `victoriametrics/victoria-logs:v1.50.0` | ~30-80 MB | `9428` |
| `marquez-api` | `marquezproject/marquez:0.50.0` (JVM) | **~600-900 MB** (JVM heap + Jetty + JDBI) | `5000` (admin `5001`) |
| `marquez-db` | `postgres:14` (per Marquez `docker-compose.yml`) | ~30-80 MB | `5432` |

**Total idle ~750 MB-1.2 GB.** Marquez + Postgres dominate. **Cannot ship as v0.1 default**: violates v4.1 §11.2 idle target (<500 MB) by 2-3× and 4 extra containers blow the boot budget (v0.1 already runs MinIO + filesystem-catalog SQLite + Dagster substrate). This is the empirical reason observability infra is gated to v0.5+. Marquez Web UI runs as a **fifth** container in upstream Compose (port 3000); v0.5+ may fold it into `marquez-api` — verify by reading Marquez `web/` Dockerfile in the ADR.

### §4.2 Production

- **VM**: single-node to ~10M time series; beyond → cluster (`vminsert`+`vmselect`+`vmstorage`). Helm `victoria-metrics-k8s-stack`. Push topology (OTLP/HTTP from Nucleus); `vmagent` only if Prom scrape targets added.
- **VL**: VLSingle or VLCluster (`vlinsert`/`vlselect`/`vlstorage`). Helm `victoria-logs-single`.
- **Marquez**: official Helm chart at `chart/`. External Postgres required (bundled `postgres:14` is dev only). No built-in HA at `0.50.0`; pattern is single API + clustered Postgres. Postgres is a third operational domain for Cloud — already required for Lakekeeper/Polaris, so net-add is zero.

Per-tenant isolation: VM has native multi-tenancy (`-tenant=<id>` via `vminsert`); VL has stream-field-based (looser); Marquez uses `namespace`. v0.7+ Cloud ADR decides VM/VL tenant ID + Marquez namespace vs full stack per tenant.

---

## §5. Performance characteristics

Numbers below are vendor docs / benchmarks; **no Nucleus benchmark yet** — measure under PoC #4 before quoting.

- **VM ingest**: vendor benchmark ~1M+ data points/sec/core, <30 ns CPU/sample, ~10× compression vs uncompressed Prom protobuf. **Cardinality matters more than throughput** — every unique `{asset, mode, engine, project_id, env}` tuple is one time series; cardinality budget per project is a v0.5 design point (`opentelemetry.md` §5).
- **VL ingest**: vendor benchmark ~190k log entries/sec/core; ~10-50× compression vs raw JSON. **NEEDS VERIFICATION** before v0.5 ADR.
- **Marquez per-event latency**: no published P50/P99. PRs in the 2026-04 commit log fixed `/api/v1/jobs` "7+ minute query times per job" at scale — known query-perf pathologies on large lineage graphs. **NEEDS VERIFICATION**: trigger a 10k-event/day fixture against `0.50.0`.
- **OL → Marquez emission overhead**: per `openlineage.md` §6, `HttpTransport.emit()` is sync (`httpx` POST, 5 s timeout, 5× retry 0.3 backoff). **A slow Marquez stalls user materializations** — v0.5 ADR must default `AsyncHttpTransport` once OL drops `experimental`, or wrap with a separate timeout/queue layer in the AMA.
- **Storage per asset-materialization-day**: ~10 KB OL JSON + ~1 KB metric points + ~2.5 KB logs → **~13 KB / mat** ingress. At 1k mats/day/project: ~13 MB/day raw, ~1-3 MB/day compressed. Marquez Postgres dominates the long tail — estimate 100-500 MB/year/project. **NEEDS VERIFICATION**.

---

## §6. Compatibility with Nucleus pins (2026-05-13)

All three are external service binaries — none is a Python dep in `pyproject.toml`. What we DO pin is the wire-format library on the Python side.

| Nucleus dep | Pin (current/candidate) | Backend requires | Resolution |
|---|---|---|---|
| `openlineage-python` | `1.47.1` candidate | Marquez `0.50.0` accepts OL spec `2-0-2` ✓ | Aligned per `openlineage.md` §2 + Marquez README. |
| `opentelemetry-api`/`-sdk` | `1.29.0` pinned | VM + VL accept OTLP/HTTP v1 (stable wire) | No shear: OTLP wire is API-stable across OTEL 1.x. |
| `opentelemetry-exporter-otlp-proto-http` | **not pinned** (v0.5 ADR) | VM `/opentelemetry/v1/metrics`, VL `/insert/opentelemetry/v1/logs` | Pin in v0.5 ADR; HTTP variant avoids `grpcio` ~30 MB wheel. |
| `httpx` | `>=0.27.0` (transitive via OL) | n/a | Pin alongside OL per `openlineage.md` §7. |
| Postgres (Marquez) | **external** | `>=12`; bundled image `postgres:14` | Prod reuses Lakekeeper/Polaris-managed Postgres. OSS Compose ships `postgres:14`. |
| Java | **Marquez container only** | Java 17 per Marquez README | Outside Nucleus core path per §2.3. |

**Major-version watch**: Marquez `0.50.0 → 0.51.x` is unreleased; `1.0` is hypothetical. `0.x` versioning is itself a risk signal — see §9.

---

## §7. Swap-target analysis (v4.1 §9.3)

All three are wrapped behind **standards** (OTLP, OpenLineage). The "interface" is the wire protocol — swap is a Helm value / env-var flip, not a code rewrite.

| Component | Swap target | Trigger | Cost |
|---|---|---|---|
| **VictoriaMetrics** | Prometheus+Thanos, Mimir, Cortex, Datadog, Grafana Cloud, AWS Managed Prometheus | org standardizes; managed-cloud cost beats self-host at scale | **Trivial.** All accept OTLP natively or via Collector. Change `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`. PromQL ⊂ MetricsQL — dashboards port. |
| **VictoriaLogs** | Loki, Elasticsearch/OpenSearch, Splunk, Datadog Logs | org standardizes; existing JVM-ES deployed | **Trivial.** All accept OTLP/HTTP logs (Loki via Collector `lokiexporter`; ES native OTLP 8.x; Splunk via Collector). LogsQL doesn't port — but no **user code** uses it. |
| **Marquez** | DataHub, OpenMetadata, Apache Atlas, Amundsen, Unity Catalog lineage, Atlan | (a) Marquez release cadence stays stalled (§9); (b) Mesh narrative push to DataHub; (c) user already deploys DataHub | **Medium.** All accept OL events (DataHub since 0.10, OpenMetadata since 1.1, Unity Catalog since 2024). Switch is `transport.url` + auth header. Marquez-specific UI features don't port. |

Maintain **interface health** (smoke tests round-tripping OTEL through VM/VL receivers; OL through a Marquez container in CI) as **always-on** per v4.1 §9.3; build the full DataHub adapter only if trigger fires. `/docs/swap/{victoriametrics,victorialogs,marquez}.md` stubs deferred to the v0.5 ADR.

---

## §8. Hallucination risks

Log every catch in [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md) per AGENTS.md §11.12.

### Likely AI hallucinations (verify before merge)

- ❌ "VM is just a Prometheus skin." VM has its own ingestion engine, on-disk format, and query language (MetricsQL ⊃ PromQL).
- ❌ Confusing **VM open-source** with **VM Enterprise** (source-available, NOT Apache-2.0) or **VM Cloud**. Cluster Enterprise / Anomaly Detection / Operator Enterprise are **paid**.
- ❌ `/api/v1/import/prometheus` as the OTLP endpoint — that's the **Prom exposition-format** endpoint. OTLP is `/opentelemetry/v1/metrics`.
- ❌ "VL lives in the VictoriaMetrics monorepo." Outdated — VL has its own repo (`github.com/VictoriaMetrics/VictoriaLogs`) since 2025.
- ❌ Marquez `POST /lineage` or `POST /events` — wrong. Correct: `POST /api/v1/lineage`.
- ❌ "Marquez has a Python client." `marquez-python` on PyPI is community-maintained, sparsely updated. Nucleus does **not** import it; we POST OL events via `openlineage-python.HttpTransport`.
- ❌ "Marquez is *the* official OpenLineage backend." **Reference implementation** per README. DataHub, OpenMetadata, Unity Catalog, Atlan, Astronomer also consume OL events.
- ❌ `AsyncHttpTransport` is GA — false at OL `1.47.1` (experimental); v0.7+ decision.
- ❌ VictoriaTraces is GA — false; Preview at 2026-05-13. Traces backend = v0.7+.
- ❌ Marquez API port `:8080` — source-build default. **Docker default is `:5000`** (admin `:5001`).
- ❌ Citing release notes for `0.51.x` features — tags only, no published Release.

### Real gotchas from official docs

- **Marquez release cadence is the elephant.** Last Release `0.50.0` 2024-10-24. Repo still active, but **users today adopt an 18-month-old image**. Re-verify before each Nucleus release.
- **Marquez requires JVM + Postgres** — two operational domains.
- **VM + VL have separate LTS lines** (`v1.122.x`, `v1.136.x` for VM). v0.5 ADR should pin the **LTS line** if available.
- **VM OTLP stores delta temporality as-is** but must be queried with `sum_over_time`/`rate_over_sum` — surprises Datadog/NewRelic users. Cumulative is default + recommended.
- **VM does NOT sanitize OTEL label characters by default** — `service.name` stored literally with the dot. `-usePromCompatibleNaming` / `-opentelemetry.usePrometheusNaming` is the supported translation.
- **Marquez UI is unauthenticated by default** (README). Per Constraint #6, v0.5 Cloud MUST front Marquez with an OIDC-aware reverse proxy (Authentik/Authelia/oauth2-proxy); never expose directly.
- **VL default retention is 7 days** (`[now-7d, now]`). Configure `-retentionPeriod` for longer; default fails Cloud SLAs.
- **Marquez `docker-compose.yml`** ships `postgres:14` with hardcoded passwords — dev only.
- **Marquez "integrations module removed in 0.21.0"** — Airflow/Spark/dbt integrations are now OL-side. `marquez-airflow` / `marquez-dbt` packages are dead.
- **VL OTEL severity-field rename in `v1.50.0`**: custom `severity` → `severity_number` + `severity_text`. Verify `structlog` bridge writes the new names.

---

## §9. Decision log

**Why these three for v0.5+:** **VM + VL** — cost-efficient single-binary Go services, Prometheus-compatible (PromQL ⊂ MetricsQL), Apache-2.0 with a sponsor (VictoriaMetrics, Inc.) shipping continuously since 2018, active monthly cadence (`v1.143.0` 8 days before research). Beats Datadog/New Relic on cost for OSS-first audience; beats Prom+Thanos on operational complexity. Pillar #5 compatible — VM emits Prom wire, Grafana/Datadog can scrape. **Marquez** — reference implementation of OpenLineage; LF AI & Data **Graduated**; Apache-2.0; data model matches OL nouns 1:1; UI good enough for v0.5 Workbench-Cloud-preview. **Adopting Marquez doesn't lock us in** — OL wire format is the abstraction; DataHub/OpenMetadata/Unity Catalog all consume it.

**Why deferred to v0.5 (not v0.1):**

- **v0.1 beachhead doesn't need observability infra.** v4.1 §1.5: 5-eng team gets to first BI-ready Iceberg table in <30 min. They haven't *generated* enough lineage events to need a graph UI. JSONL + `jq` is fine for 4 months.
- **Boot budget can't fit 4 more containers.** v4.1 §11.2: cold boot <10 s, idle <500 MB. Per §4.1, obs stack adds ~750 MB-1.2 GB idle + 4 containers — 3× the v0.1 budget. Default `nucleus up` becomes "why is this thing so heavy".
- **Until paying customers exist, observability is over-engineering.** Trigger is empirical: **first paying customer requesting SLA dashboards** (or first OSS user filing "where did my lineage event go?" when JSONL gets too big to grep). Until then: defer.

**Marquez health caveat — the founder needs to know.** Marquez has not cut a Release in **18 months** (`0.50.0` 2024-10-24 → 2026-05-13). Commits continue (`2026-04-12`, query-perf fixes); tags `0.51.0`/`0.51.1` exist; LF AI & Data Graduated status unchanged. Two reads: (1) **benign** — project mature, OL spec stable at `2-0-2`, maintainers upstreamed integrations into OpenLineage itself ("integrations module removed in 0.21.0" supports this); (2) **concerning** — vendor energy (Astronomer was largest contributor) shifted to commercial catalog offerings; may be "soft maintenance" — bug fixes only. Reality probably both. **Action for the v0.5 ADR**: re-check (a) last Release date, (b) commit cadence on `main`, (c) whether Astronomer has decoupled. If health drops further by v0.5 launch, **swap to DataHub as default** and keep Marquez as migration-from-Airflow user opt-in via `nucleus enable marquez`. OL wire format means swap is days, not weeks.

**Why NOT vendor lock-ins** (Datadog/NewRelic/Honeycomb/Splunk): Pillar #5 violation; per-host/per-metric pricing our audience can't absorb; some vendor agents ship JVM (Constraint #1). Vendor backends remain user opt-in via OTEL Collector. **Why NOT custom-built lineage UI**: Constraint #4 + Pillar #2. 6-12 months frontend work for zero pillar gain.

---

## §10. Next reads when v0.5 observability work starts

- [ ] **Re-fetch Marquez release health.** Has `0.51.x`+ Release been cut? Commit cadence held? **If 0 commits in trailing 60 days at v0.5 launch, default to DataHub.**
- [ ] **VictoriaTraces GA status.** GA → traces join the stack; Preview → defer to v0.8.
- [ ] **`opentelemetry-collector-contrib`** bridging OTEL → VM + OTEL → VL. Ship default `otel-collector.yaml`; pin Collector separately from SDK.
- [ ] **Marquez Helm chart** (`chart/` in repo) — for v0.5 Cloud deploy ADR. Verify external Postgres wiring + HA story.
- [ ] **OL `AsyncHttpTransport` GA status** at v0.5 launch. Still experimental → default `HttpTransport` + separate timeout/queue in AMA.
- [ ] **VM OTLP delta-to-cumulative decision** — Collector between us and VM, or Nucleus emits cumulative-only?
- [ ] **VL severity-field migration** — verify `structlog` bridge writes `severity_number`/`severity_text` (renamed in `v1.50.0`).
- [ ] **DataHub vs Marquez decision matrix** — if user feedback or `docs/internal/research/strategic/solo_oss_patterns_and_iceberg_2026.md` pushes Mesh, DataHub is the natural beachhead.
- [ ] **Marquez Postgres tuning** — query-perf PRs in 2026-04 suggest large lineage graphs need index/pool tuning.
- [ ] **Cross-reference with `oidc_providers.md`** (Worker W) — obs and OIDC share the v0.5+ optional-infra gating model.

---

*Last verified 2026-05-13 against VictoriaMetrics `v1.143.0`, VictoriaLogs `v1.50.0`, Marquez `0.50.0`. Re-verify when opening the v0.5 observability ADR; when pinning any of the three in `nucleus enable obs`; on any major bump; or before the Marquez-vs-DataHub decision gate. Log AI-fabricated APIs caught in PR review to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*
