# Production Deployment — Single-Node Self-Hosted Nucleus

> **Scope**: v0.2 single-node deployment for teams of 5–20 engineers, roughly 100 GB–5 TB total data, per `nucleus_architecture_v4.1.md` beachhead persona and yield-to-giants strategy.
> **Not in scope**: multi-node HA, fleet orchestration, or managed control planes — defer to Mode 2 (`compute=` dispatch) and cloud catalogs (see v0.3+ roadmap and architecture section 10).

Nucleus v0.2 is intentionally **single-node**: you run one well-provisioned Linux host (VM or bare metal), attach fast local or block storage for the warehouse, optionally front the Workbench with a reverse proxy and TLS, and back object storage with **SeaweedFS** (documentation default per [ADR-008](../decisions/ADR-008-storage-substrate-v01.md)) or any S3-compatible endpoint. This is suitable for a shared “team laptop in the closet” topology — not for exabyte-scale or multi-region SLAs.

---

## Hardware sizing

Empirical anchors: PoC #4 (`AGENTS.md` status block, summarized in [`docs/internal/research/performance_reliability_targets.md`](../research/performance_reliability_targets.md)) measured **`nucleus up` cold boot ≈ 5.82 s** and **idle RSS ≈ 117 MB** for the CLI plus sidecar profile — far below typical VM headroom. Production sizing is dominated by **DuckDB + Polars peak RAM during materialization** (see §Performance tuning), not idle footprint.

| Data volume | RAM | CPU | SSD / NVMe | Notes |
|-------------|-----|-----|------------|-------|
| < 100 GB | 16 GB | 4 cores | 500 GB+ | Fits small VM or staging; aligns with laptop-class beachhead hardware |
| 100 GB – 1 TB | 32 GB | 8 cores | 2 TB | Comfortable default for 5–10 engineers intermittently overlapping |
| 1–5 TB | 64 GB | 16 cores | 8 TB NVMe | Largest single-node target before Iceberg metadata / concurrency stress dominates |
| > 5 TB | — | — | — | **Yield to giants** — partition workloads or dispatch heavy assets via Mode 2 (`compute=`); keep catalog portable Iceberg |

Reserve **≥ 15% free disk** at all times: Iceberg commits, DuckDB spills (when configured), and SeaweedFS growth need headroom.

---

## Reference deployment (Docker Compose)

Authoritative file (pinned images, networks, resource limits): **`docker-compose.production.yaml`** at the repository root.

### Topology

| Service | Role | Image pin |
|---------|------|-----------|
| `storage` | S3-compatible object store | `chrislusf/seaweedfs:4.23` ([ADR-008](../decisions/ADR-008-storage-substrate-v01.md), [`docs/compatibility.md`](../compatibility.md)) |
| `nucleus` | CLI + Workbench (FastAPI) | Built from `docker/Dockerfile.production` → tag `nucleus:production-local` |
| `caddy` | TLS + reverse proxy | `caddy:2.8.4-alpine` |

**Networks**

- `nucleus_backend` — **internal** (no outbound route). Only `storage` and `nucleus` attach; S3 endpoint `http://storage:9000` is not published to the host.
- `nucleus_edge` — `caddy` + `nucleus`. The Workbench listens on **8765** inside the edge network; operators expose **80/443** through Caddy only.

**Volumes (bind-backed locals)**

Bind mounts default under `./var/lib/…` relative to the compose file so `docker compose … config` works on developer machines; on a Linux VM set absolute paths via:

- `SEAWEEDFS_DATA_ROOT`
- `CADDY_DATA_ROOT`
- `CADDY_CONFIG_ROOT`

### Bootstrap (Linux VM)

```bash
mkdir -p var/lib/seaweedfs var/lib/caddy/data var/lib/caddy/config
export NUCLEUS_PROJECT_HOST_PATH=/srv/nucleus/myproject   # directory containing nucleus_project.yaml
export CADDY_SITE_ADDRESS=nucleus.example.com           # hostname for ACME
docker compose -f docker-compose.production.yaml build nucleus
docker compose -f docker-compose.production.yaml up -d
```

**Validate compose only**

```bash
docker compose -f docker-compose.production.yaml config
```

### Health checks (as implemented)

| Service | Check | Notes |
|---------|-------|-------|
| `nucleus` | `GET http://127.0.0.1:8765/api/health` | Implemented in `src/nucleus/workbench/app.py` — returns JSON `{"status":"ok","version":…}` |
| `storage` | `pgrep -x weed` | SeaweedFS **HTTP-API wiki** mixes master/filer/S3 topology-specific paths (`/cluster/status` applies to cluster masters — see [SeaweedFS HTTP API wiki](https://github.com/seaweedfs/seaweedfs/wiki/HTTP-API)); this compose runs **`weed server -s3`** only, so the reference stack uses **process liveness** instead of asserting a particular `/healthz` URL on port 9000 |
| `caddy` | `pgrep -x caddy` | `caddy reverse-proxy` disables the admin API (`:2019`); process probe matches [Caddy CLI reverse-proxy](https://caddyserver.com/docs/command-line#caddy-reverse-proxy) constraints |

---

## Persistent volume layout

Align paths with your `nucleus_project.yaml` **warehouse** setting. Typical self-hosted layout on a single node:

```text
/var/lib/nucleus/
  ├── warehouse/         # Iceberg metadata + Parquet — primary durable data (back up)
  ├── catalog.db         # SQLite Iceberg catalog file (often under warehouse; back up with warehouse)
  ├── .nucleus/
  │     └── runs/
  │           └── runs.ndjson   # Run ledger (back up if audit trail matters)
  ├── secrets/.env       # Optional env overrides — never commit (see Secret rotation)
  └── logs/              # Host-collected container logs or bind-mounted app logs

/var/lib/seaweedfs/      # SeaweedFS `-dir` data (when using bundled storage container)

/var/lib/caddy/          # ACME certs + renewal metadata (Caddy `:data` volume)
```

If you embed DuckDB BI artifacts beside the warehouse (team-dependent), treat them as **rebuildable cache** unless your DR policy says otherwise — clarify in runbooks.

---

## Backup strategy

### Iceberg snapshots (built-in immutability)

Iceberg retains snapshot history until expiration policies run. Inspect refs:

```bash
nucleus snapshot list raw.orders
```

Pin a tag for rollback / compliance (exact Typer surface: `src/nucleus/cli/commands/snapshot.py` — **ADR-028**):

```bash
nucleus snapshot tag create raw.orders v2026-05-15 --snapshot-id 8823671234
```

Asset keys must be **`namespace.name`** (two segments), not a bare name.

### Warehouse directory backup

- **Daily incremental**: `rclone sync /var/lib/nucleus/warehouse/ remote:nucleus/$(date +%F)/`
- **Retention**: common pattern 30 days hot object storage, ≥ 1 year Glacier/archive class — tune to regulatory needs.
- **Restore drill**: quarterly restore into an isolated prefix + `nucleus query` smoke query against one canonical asset.

### External Postgres catalog (v0.3+)

When Lakekeeper / REST catalog lands for shared teams, add **`pg_dump` + WAL archiving** per your DBA standards — out of scope for v0.2 filesystem catalog defaults.

---

## Health monitoring

### CLI health status

There is **no `nucleus health` Typer command wired yet** in `src/nucleus/cli/main.py` (confirmed 2026-05-15). The capability is specified illustratively in [`docs/internal/research/performance_reliability_targets.md`](../research/performance_reliability_targets.md) §7.3 (“Health check command (v0.2)”) as a future consolidation of probes.

**v0.2 operational probes**

| Layer | Probe |
|-------|-------|
| CLI / import sanity | `nucleus version` — exits **0** on success (`src/nucleus/cli/main.py`) |
| Workbench | `curl -fsS http://127.0.0.1:8765/api/health` — JSON status |

Example cron (host-side, hitting published port or loopback):

```cron
*/5 * * * * curl -fsS http://127.0.0.1:8765/api/health >/dev/null || logger "nucleus workbench health failed"
```

Docker deployments should call the **same** `/api/health` path inside the container (as in `docker-compose.production.yaml`).

### Prometheus metrics (v0.5+)

Planned exemplar series (documented here for SLO design only — **not exported in v0.2**):

- `nucleus_materialize_duration_seconds`
- `nucleus_run_total{status="success|failure"}`
- `nucleus_iceberg_snapshot_age_seconds`

Wire these when OpenTelemetry + VictoriaMetrics land per architecture observability stance.

### Alerts (pragmatic)

| Signal | Action |
|--------|--------|
| `/api/health` non-200 / timeout | Page whoever owns data uptime |
| Disk **> 85%** | Warn + throttle schedules |
| No successful materialization in **24 h** for business-critical scheduled asset | Page — likely upstream breakage |

---

## Log aggregation

v0.2 recommendation: **`journalctl -u docker`** (systemd) or Docker logging driver → **Vector / Fluent Bit → Loki**. Native OpenTelemetry log correlation is deferred (architecture observability tier).

---

## HTTPS / reverse proxy

Two layers:

1. **Inbound TLS + routing** — `caddy reverse-proxy --from "$CADDY_SITE_ADDRESS" --to http://nucleus:8765 --change-host-header` (pinned image in compose). Hostname `--from` triggers automatic HTTPS via ACME per [Caddy reverse-proxy CLI](https://caddyserver.com/docs/command-line#caddy-reverse-proxy).

2. **Authentication at the edge** — see next section.

---

## Authentication (pre-v0.3 caveat)

**Nucleus v0.2 does not implement OIDC inside the Workbench.** Hard Constraint #6 (`AGENTS.md` §3) requires **delegating identity** — today that means **your reverse proxy or SSO wedge**, not first-party user tables.

Options:

| Approach | Fit |
|----------|-----|
| **Caddy `basic_auth`** | Quick team gate — passwords must be **pre-hashed**; plaintext disallowed ([Caddy `basic_auth` directive](https://caddyserver.com/docs/caddyfile/directives/basicauth) — renamed from `basicauth` before v2.8). Syntax:`basic_auth { user bcrypt-hash … }`. |

Example **Caddyfile** fragment (adjust site block — **do not** reuse demo hashes):

```caddyfile
nucleus.example.com {
	basic_auth {
		Alice $2a$14$Zkx19XLiW6VYouLHR5NmfOFU0z2GTNmpkT/5qqR7hx4IjWJPDhjvG
	}
	reverse_proxy nucleus:8765
}
```

Generate hashes: `caddy hash-password` ([docs](https://caddyserver.com/docs/command-line#caddy-hash-password)).

| **Authelia / Authentik / OAuth2-proxy** | Preferred when you already run an IdP — aligns with future native OIDC (`docs/internal/research/oidc_providers.md`). |

## Secret rotation

Follow [`docs/patterns/secret_management.md`](../patterns/secret_management.md) — env precedence, never commit `.env`, rotate on leak.

Planned cookbook **[`docs/cookbook/cloud-credentials.md`](cloud-credentials.md)** (Wave v0.2) will consolidate cloud STS patterns; until merged, rotate **S3 keys**, **database passwords**, and **LLM provider keys** via your vault procedure whenever staff churn.

---

## Update procedure

Per `AGENTS.md` §11.13 — **one dependency upgrade per PR** in development; on the VM translate to **one controlled change at a time**.

**Bare-metal / venv install**

1. Read pins in [`docs/compatibility.md`](../compatibility.md).
2. `pip install nucleus==<new-version>` inside the activated environment.
3. `nucleus version` → exit code **0**.
4. Canary: `nucleus run <your_smoke_asset_key>`.
5. Append notes to `/var/lib/nucleus/upgrade-log.md` (timestamp, from→to, operator).
6. Rollback: `pip install nucleus==<previous>` plus documented dependency pins.

**Docker Compose reference stack**

Rebuild `nucleus:production-local` from the tagged Git revision matching the PyPI release you intend to ship; redeploy stack; verify `/api/health`.

Release automation expectations: [ADR-022](../decisions/ADR-022-cicd-release-automation.md).

---

## Disaster recovery

| Failure mode | Detection | Recovery | RTO target |
|--------------|-----------|----------|------------|
| Disk full | Metrics / `df` / materialize errors | Expand volume + `expire_snapshots` maintenance / cold tier offload | ~30 min |
| Container crash | Docker `restart: always` | Auto-restart | < 1 min |
| Host loss | External health probe failure | Provision new VM + restore warehouse + SeaweedFS volume from backup | ~30 min (storage-bound) |
| Catalog metadata corrupt | `NE4001` path / parse errors ([`performance_reliability_targets` §8](../research/performance_reliability_targets.md)) | Restore `metadata/` prefix from backup; `nucleus repair` when shipped (v0.3+) | ~1 h |
| Bad Iceberg commit | User / QA signal | Roll forward new snapshot **or** tag prior snapshot (`nucleus snapshot tag create … --snapshot-id …`) | ~5 min |

---

## Performance tuning

Primary levers (single-node):

- **DuckDB** — `memory_limit` + `threads` set during materialization ([DuckDB tuning](https://duckdb.org/docs/guides/performance/how_to_tune_workloads.html)); AMA sets a safe default — override via `nucleus_project.yaml` per [`nucleus_project_anatomy.md`](../../nucleus_project_anatomy.md) examples.
- **Polars** — limit thread pool on shared hosts (`POLARS_MAX_THREADS` env) to cap CPU contention.
- **Dagster** — reduce concurrent heavy runs on one box (future tunable; see parity research rows for `max_concurrent_runs` in `docs/internal/research/parity_vs_bosch_ely_adb_batch.md`).

Full numeric budgets: [`docs/internal/research/performance_reliability_targets.md`](../research/performance_reliability_targets.md).

---

## Cost estimate (self-hosted vs cloud — illustrative only)

| Pattern | Order of magnitude (2026 USD, region-dependent) | When it wins |
|---------|-----------------------------------------------|--------------|
| Single m6i.4xlarge-class VM + NVMe + egress | High hundreds / month infra | Steady moderate data, predictable concurrency, in-house ops |
| Databricks / Snowflake consumption | Dollars per DBU / per TB scanned — dominant at exploratory ad-hoc usage | Burst analytics, elastic teams, governance already centralized |

Treat public cloud list price + **support comp** as your comparison baseline; this is **not financial advice** — refresh quotes before gate reviews.

---

## Anti-patterns (do not do)

1. **Co-locate the Nucleus runtime and your production *source-of-truth* OLTP database on the same disk/VM without isolation** — noisy neighbor I/O stalls both workloads.
2. **Skip warehouse backups because “Iceberg keeps snapshots”** — snapshots reference files; if the backing store is gone, history is useless.
3. **Publish Workbench (:8765) directly to the Internet without TLS + SSO or at least basic auth** — v0.2 has no native OIDC; you own the perimeter.
4. **Oversubscribe concurrent `nucleus run` on a filesystem catalog** — advisory locking is still hardening (`performance_reliability_targets` §5–6); treat shared single-node writes as **sequential by policy** until locks are universal.
5. **Run containers as root “for convenience”** — bind mounts become host-RW foot-guns; the reference `Dockerfile.production` uses the `nucleus` non-root user.
6. **Pin `:latest` on Caddy or SeaweedFS in real environments** — breaks `AGENTS.md` §11.13 traceability; always use digest or semver tag (compose file demonstrates pins).
7. **Ignore disk headroom < 15%** — commit + spill failures are expensive to unwind.

---

## See also

- [ADR-008 — SeaweedFS default storage substrate](../decisions/ADR-008-storage-substrate-v01.md) — object store choice (**not** ADR-014, which covers dlt Postgres source)
- [ADR-022 — CI/CD + release automation](../decisions/ADR-022-cicd-release-automation.md)
- [`docs/patterns/secret_management.md`](../patterns/secret_management.md)
- [`docs/cookbook/cloud-credentials.md`](cloud-credentials.md) — *link target for Wave cookbook; create when file lands*
- [`docs/cookbook/ai-copilot-setup.md`](ai-copilot-setup.md) — *forthcoming — until published, configure LLM keys per `secret_management` + [ADR-015](../decisions/ADR-015-ai-chat-mvp.md)*
- [`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md) section 10 — yield to giants
- [`docs/internal/research/performance_reliability_targets.md`](../research/performance_reliability_targets.md) — perf + reliability budgets
- Local dev MinIO alternate (archived upstream note): [`docker-compose.demo.yml`](../../docker-compose.demo.yml) — **do not edit** per policy; contrast with SeaweedFS default in [`docker-compose.yml`](../../docker-compose.yml)
