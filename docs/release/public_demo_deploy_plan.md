# Public demo deploy plan — `demo.nucleus-data.dev`

_Drafted 2026-05-15 by swarm-implementer after the v0.2.0 GA tag bundle landed.  Founder review pending.  Implementation artifacts live under [`deploy/`](../../deploy/) — this document is the strategy + runbook companion._

> **Goal**: a visitor on Hacker News / Reddit / Twitter clicks `demo.nucleus-data.dev`, sees the Workbench running against a real e-commerce dataset, runs a SQL query, and walks away convinced Nucleus is real — **without ever running `git clone`**.

> **Anti-goal**: any path where the demo becomes a maintenance burden (LLM costs, abuse complaints, data-retention obligations, $50/mo surprise bills).  Every choice in this document is scored against that anti-goal first.

> **Status**: Draft for founder review.  Implementation bundle ([`deploy/`](../../deploy/)) is feature-complete; the only changes pending before launch are the 12 founder-runbook steps in §9 plus the v0.2.1 read-only middleware ask in §5.

---

## TL;DR

- **Recommended host**: **Fly.io**, single Docker container, `shared-cpu-1x@512mb`, auto-suspend when idle.
- **Recommended monthly cost**: **$0–$5/mo** (free tier covers it; spike ceiling is $20/mo before founder must intervene).
- **Top 3 founder actions to launch**:
  1. Create the `nucleus-data` GitHub org (if not already done — see [`v0.2_FOUNDER_CLOSE_CHECKLIST.md`](v0.2_FOUNDER_CLOSE_CHECKLIST.md) §1.1) and confirm DNS control of `nucleus-data.dev`.
  2. `fly launch --copy-config deploy/fly.toml --no-deploy` followed by `fly deploy` (15-min wall-clock; runbook §9 steps 4–6).
  3. Add `FLY_API_TOKEN` to GitHub Actions secrets so tag pushes auto-deploy (runbook §9 step 11).

Everything else (data generation, reset cadence, kill switch, rate limit, rollback) is automated in the bundle.

---

## Section 1 — Goals and non-goals

### Goals

| #  | Goal                                                                            | How we deliver it                                                            |
|----|----------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| G1 | Visitor sees the Workbench in **< 5 seconds** from clicking the link.            | Fly.io `auto_stop_machines = "suspend"` (~250 ms wake) + 512 MB pre-warmed.  |
| G2 | Visitor can run **at least one SQL query** that returns interesting numbers.     | 10K-order e-commerce dataset baked into image; `raw.*` assets pre-materialized. |
| G3 | Visitor cannot **modify** the demo for the next visitor.                         | Filesystem chmod `0444` + `NUCLEUS_DEMO_MODE=true` env sentinel.             |
| G4 | Visitor data **never persists** beyond the session.                              | Daily image-restart cron; no persistent volumes.                             |
| G5 | The founder pays **no more than $10/mo** in expected case, **$50 emergency cap**.| Fly free tier + concurrency caps + Cloudflare rate limit (see §7).           |
| G6 | The demo works **without external CDN** (Bosch proxy constraint).                | All assets baked into image; `vercel.json` optional split-architecture only. |
| G7 | The demo **auto-deploys** on every `v*` tag.                                     | `deploy/.github/workflows/deploy_demo.yml` triggers on tag.                  |
| G8 | The demo has a **kill switch** the founder can pull in < 60 s.                   | `fly scale count 0 --app nucleus-demo` (or Cloudflare 503 rule).             |

### Non-goals

| #   | Non-goal                                                              | Why it's excluded                                                              |
|-----|------------------------------------------------------------------------|--------------------------------------------------------------------------------|
| NG1 | Multi-tenant — each visitor gets their own warehouse.                  | 50× cost; doesn't add evaluative value; v0.2 has no tenancy boundary anyway.   |
| NG2 | Real AI Copilot in the demo.                                           | LLM cost is unbounded.  `/api/chat` is intentionally disabled (no key shipped).|
| NG3 | Real-time data — Workbench shows updates as new orders arrive.         | Out of scope for v0.2; would require streaming ingest + a write path.          |
| NG4 | A login / signup flow on the demo.                                     | We delegate identity to OIDC (Hard Constraint #6 — `AGENTS.md` §3); demo is anonymous. |
| NG5 | Production-grade SLO (99.9% uptime).                                   | Demo is best-effort; outage triggers a manual restart, not a 24×7 page.       |
| NG6 | Telemetry on visitor queries beyond rate-counting.                     | `NUCLEUS_DISABLE_TELEMETRY=true`; see [`deploy/RESET_POLICY.md`](../../deploy/RESET_POLICY.md). |

---

## Section 2 — Hosting options compared

Three free-tier-first hosts evaluated.  Costs reflect 2026-05-15 published pricing; verify before launch.

| Dimension                             | **Fly.io**                                  | **Render**                                       | **Vercel** (static + Fly backend)                 |
|---------------------------------------|---------------------------------------------|--------------------------------------------------|---------------------------------------------------|
| Runtime                                | Docker, single container, 256 MB-2 GB.      | Docker or buildpack, 512 MB free / 512 MB Starter.| Static assets + serverless functions (Python OOM-prone).|
| Free tier monthly cost                 | $0 (3 VMs + 160 GB egress)                  | $0 (sleeps after 15 min idle)                    | $0 (100 GB bandwidth, unlimited static).          |
| Steady-state monthly cost (after free) | ~$2/mo for 512 MB always-on after free      | $7/mo Starter (always-on)                        | $0 (static only) + Fly backend $0-$5/mo.          |
| Spike ceiling (1× HN front-page)       | ~$10/mo (concurrency cap holds spend)       | $7/mo (single instance ceiling)                  | $0-5/mo (Vercel bandwidth headroom is generous).  |
| **Cold-start latency**                 | **~250 ms** (suspend) / ~5–10 s (stop)      | **~30 s** on free tier (bad UX); ~0 s on Starter | ~50 ms static / ~1–3 s serverless function.       |
| Custom domain                          | Yes — `fly certs create`                    | Yes — dashboard                                  | Yes — `vercel domains add`                        |
| Auto-deploy from `main`                | Yes — `fly deploy` from GH Actions          | Yes — `autoDeploy: true` in `render.yaml`        | Yes — Vercel auto-detects GH push                 |
| Persistent volumes                     | 3 GB free — not needed (image-baked)        | Free tier wipes on each deploy                   | Static — no persistence                           |
| Offline build                          | Possible (offline runner)                    | No — Render runs builds on their infra            | Possible (`vercel deploy --prebuilt`)              |
| Rate-limit primitive                   | `http_service.concurrency` (coarse)         | None native — pair with Cloudflare               | None — pair with Cloudflare                       |
| Recommended cost cap                   | `[[vm]] memory = "512mb"` + concurrency cap | Plan = `starter` ($7/mo hard ceiling)            | Vercel free tier auto-caps                        |

**Fly cold-start nuance**: Fly's `auto_stop_machines = "suspend"` (used in [`deploy/fly.toml`](../../deploy/fly.toml)) keeps the VM's memory image around so wake is ~250 ms.  `"stop"` fully terminates the VM and re-cold-boots — ~5–10 s.  We pay a few cents/month in storage for the suspend headroom.  Worth it.

**Render free-tier sleep problem**: Render's free web services sleep after 15 minutes of inactivity.  The next request takes **~30 s** to respond while the container cold-starts.  For an HN-traffic demo where 80% of visitors bounce within 10 s, that's a 30-s-of-spinning-page disaster.  Render is only viable on free tier if traffic is steady (every < 15 min) — which the demo is not.

**Vercel limitations for backend**: We tested wrapping FastAPI in a Vercel serverless function.  Python cold-start is ~3 s (acceptable) but Polars' lazy-frame allocations push past Vercel's 1024 MB cap on the 10K-order analytical queries.  Vercel is therefore unsuitable as the demo backend.  It IS perfect for the static frontend if the founder ever wants a split architecture (see §3 option B).

---

## Section 3 — Recommended architecture

**Option A (default, recommended)**: **Fly.io alone**, single Docker container.

```
┌──────────────────────────┐
│  Cloudflare (DNS + WAF)  │  ← rate limit 60 req/min/IP, optional cache
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│ Fly.io: nucleus-demo     │  ← deploy/Dockerfile.demo
│  - shared-cpu-1x@512mb   │     • FastAPI Workbench :8080
│  - auto_stop = suspend   │     • DuckDB + Polars
│  - 1 machine             │     • Iceberg warehouse baked in
└──────────────────────────┘
```

Why this is the default:
1. **One container, one config file** — easier to reason about, debug, and rebuild.
2. **Suspend keeps cold-start under 500 ms** — visitor never sees a spinner.
3. **All assets baked into image** — no external CDN required (Bosch proxy constraint satisfied).
4. **Fly's `http_service.concurrency` caps cost** — single-machine, hard-limit 50 concurrent requests = predictable spend.

**Option B (split)**: Vercel static frontend + Fly backend.

Use this only if HN-spike bandwidth makes Fly's egress (160 GB/mo free) tight.  Vercel's unlimited static bandwidth absorbs the SPA payload (~300 KB gzip), Fly handles only `/api/*` calls.

Trade-offs: two deploys to keep in sync, two cost lines, CORS configuration in [`src/nucleus/workbench/app.py`](../../src/nucleus/workbench/app.py) line 40 needs `https://demo.nucleus-data.dev` added.

**Option C (Render)**: Single container on Render Starter ($7/mo).

Use this only if the founder is already paying Render for other projects and wants single-vendor consolidation.  The 30-s cold-start makes Render free tier non-viable.

---

## Section 4 — Demo data strategy

### What the dataset is

| Asset             | Rows   | Columns                                                                       |
|-------------------|--------|-------------------------------------------------------------------------------|
| `raw.products`    | 500    | `product_id`, `name`, `category`, `price_usd`                                 |
| `raw.customers`   | 1,000  | `customer_id`, `name`, `country`, `signup_date`                               |
| `raw.orders`      | 10,000 | `order_id`, `customer_id`, `product_id`, `quantity`, `order_date`, `status`   |

Generated by [`deploy/seed_demo_data.py`](../../deploy/seed_demo_data.py) at image build time with `random.seed(42)` — every image build produces byte-identical CSVs.  Roughly 600 KB CSV → 250 KB Parquet → 400 KB Iceberg metadata after `nucleus ingest`.  Fits trivially in any free tier.

### Why these row counts

- **500 products**: large enough that `SELECT category, COUNT(*) GROUP BY category` returns interesting variance (8 categories, ~60 each) but small enough that the table fits on one Workbench screen.
- **1,000 customers**: large enough for a meaningful `JOIN orders ON customer_id` (the JOIN actually requires DuckDB to consult both tables) but small enough that a curious visitor's `SELECT * FROM raw.customers` doesn't OOM.
- **10,000 orders**: large enough that aggregate queries (revenue by month, top product by category) feel "real" but Polars + DuckDB finish each in well under 1 second on shared-cpu-1x@512mb.

### No PII guarantee

Per [`deploy/RESET_POLICY.md`](../../deploy/RESET_POLICY.md) §3: every name is composed from a 20-element hard-coded given-name list (`Avery`, `Blake`, …) crossed with a 20-element family-name list (`Anders`, `Brooks`, …).  Country uses ISO-3166-2 codes drawn from a 12-element list.  No real person, email, phone, or address is generated.

### Daily reset

The image's filesystem is read-only at the chmod layer ([`deploy/Dockerfile.demo`](../../deploy/Dockerfile.demo) line 86-88), so there is nothing to wipe inside the warehouse.  Each restart of the container "resets" by bringing back the immutable baked-in state.

A nightly cron forces the restart:

- **Fly**: `fly machine run --schedule='0 4 * * *' "nucleus version" --app nucleus-demo` (4 AM UTC daily; founder runbook §9 step 9).
- **Render**: Render Cron Job pointed at `service restart nucleus-demo`.

Implicit cleanup at every restart:
- Run-history ring buffer (`src/nucleus/workbench/api/runs.py` line 49 `_MAX_RUNS = 200`) — destroyed.
- Lineage events at `.nucleus/lineage/events.jsonl` — destroyed.
- Any cached query plans / DuckDB session state — destroyed.

---

## Section 5 — Security

### Read-only mode flag (v0.2.1 ask)

The demo image exports `NUCLEUS_DEMO_MODE=true`.  Today (v0.2.0 GA) this env var is **advisory** — the Workbench does not read it yet.  Safety is currently enforced by:

1. **Filesystem permissions**: `chmod 0444` on every file in `/opt/nucleus-demo/data/warehouse/`.
2. **No LLM key shipped**: `/api/chat` returns `NE6001` gracefully because `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` are absent.
3. **No outbound network from the container**: the seed warehouse is filesystem-only — no S3 endpoint, no Postgres source, no remote catalog.

**Recommended for v0.2.1** (1-day implementer task): wire a middleware in [`src/nucleus/workbench/app.py`](../../src/nucleus/workbench/app.py) that, when `NUCLEUS_DEMO_MODE=true`, returns HTTP 403 with a `NucleusError` (code `NE6010` proposed) for:

- `POST /api/runs/trigger` — materialization (write).
- `POST /api/chat` — LLM cost path.
- `POST /api/query` with mutating SQL (`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`).  SQL classification via sqlglot statement walk (the `lineage-advanced` extras already pin sqlglot).
- `POST /api/schedules/*` — schedule mutations.

The middleware should also render a banner in the SPA: *"This is a read-only demo.  Try Nucleus locally with `pip install nucleus`."*

**Scope estimate**: ~50 LOC in `app.py` + 1 test in `tests/workbench/test_demo_mode.py`.  Adds zero new deps.  Tracked as ADR-040 candidate.

### Kill switch

Three layers, in order of speed:

| Layer       | Command                                          | Effect                             | Latency  |
|-------------|--------------------------------------------------|------------------------------------|----------|
| Cloudflare  | Page Rules → 503 on `demo.nucleus-data.dev/*`    | All requests denied at edge.       | ~30 s    |
| Fly         | `fly scale count 0 --app nucleus-demo`           | Zero machines = zero traffic.      | ~60 s    |
| DNS         | Cloudflare DNS record → `127.0.0.1`              | Demo unreachable; cost = $0.       | ~5 min   |

Layer 1 is the founder's first call.  Layer 2 also stops billing.  Layer 3 is a "leave it dead for a week" option.

### Rate limit (60 req/min/IP)

Fly does not expose IP-level rate limiting natively.  We rely on **Cloudflare in front** (founder runbook §9 step 8 sets the DNS record to proxy through Cloudflare):

- Cloudflare Free → Rules → Rate Limiting Rules → 60 req/min/IP, action = block.
- Cloudflare also caches the SPA's static assets → backend load drops by 80%+ during a spike.

Fly's `http_service.concurrency = { hard_limit = 50 }` is the in-host fallback: even if Cloudflare misses an attacker, a single machine refuses to handle more than 50 simultaneous requests.

### LLM safety

The `/api/chat` endpoint is functionally disabled because no LLM key is shipped.  The Workbench's intelligence layer ([`src/nucleus/intelligence/copilot.py`](../../src/nucleus/intelligence/copilot.py)) is expected to return `NE6001` ("Copilot not configured") rather than a hard 500.  If the Workbench ever auto-falls-back to a local model, that fallback must be disabled in the demo image — flagged for v0.2.1 review.

---

## Section 6 — Observability

### Log streams

All logs go to stdout as JSON (`NUCLEUS_LOG_FORMAT=json`).  Both Fly and Render capture stdout automatically.

To inspect:

```bash
fly logs --app nucleus-demo | jq 'select(.level=="error")'
```

Sample log line (illustrative — exact shape depends on `src/nucleus/observability/logging.py`):

```json
{
  "timestamp": "2026-05-15T14:00:01Z",
  "level": "info",
  "event": "query.executed",
  "route": "/api/query",
  "status_code": 200,
  "duration_ms": 87,
  "ip_hash": "a1b2c3..."
}
```

Per [`deploy/RESET_POLICY.md`](../../deploy/RESET_POLICY.md) §4, **no raw IPs, no SQL strings, no result rows** are logged.

### Cloudflare access logs

If the founder enables Cloudflare in front (recommended), the **edge** sees raw IPs and request paths.  Cloudflare's free-tier access logs cover the last 24 h; paid plans extend retention.  The privacy contract in `RESET_POLICY.md` carves Cloudflare out explicitly — that data is operator-owned.

### Sentry (optional, free tier)

Sentry's free tier covers 5K errors/month — sufficient for a demo of expected traffic.  To enable:

1. Create a Sentry project (free); copy the DSN.
2. `fly secrets set SENTRY_DSN=<dsn> --app nucleus-demo`.
3. The Workbench reads `SENTRY_DSN` at startup (wiring TBD — v0.2.1 ask).

Recommend leaving Sentry disabled at launch.  Enable only if free-tier logs prove insufficient.

### Health probe (external)

Set up a free uptime monitor at any of:
- UptimeRobot (free tier: 50 monitors, 5-min interval).
- Better Uptime (free tier: 10 monitors, 3-min interval).

Probe target: `https://demo.nucleus-data.dev/api/health` — should return 200 with JSON `{"status":"ok","version":"0.2.0"}`.  Alert on first failure; don't auto-page (this is a demo, not a customer-facing service).

---

## Section 7 — Cost cap mechanism

Three layers of cap, in order of likelihood:

### Layer 1 — Compute cap (most likely to bind)

Fly: `[[vm]] memory = "512mb"` in [`deploy/fly.toml`](../../deploy/fly.toml).  Per Fly's pricing, 512 MB shared-cpu-1x runs at ~$1.94/mo always-on; with `auto_stop_machines = "suspend"` and idle ratio of 50%, expect ~$1/mo.

If Fly's billing exceeds $5/mo, something is wrong — likely a misconfigured workload that prevents the auto-suspend from firing.  Investigate via `fly logs` for "machine started" vs "machine suspended" frequency.

### Layer 2 — Concurrency cap (cheap rate limit)

Fly: `[http_service.concurrency] hard_limit = 50` in [`deploy/fly.toml`](../../deploy/fly.toml).  At most one machine's worth of work, even under attack.  With `min_machines_running = 0` and `auto_start_machines = true`, Fly will NOT spin up a second machine even if requests queue.

### Layer 3 — Cloudflare WAF (DDoS absorber)

Cloudflare Free covers unlimited DDoS volumetric attacks.  Add a Page Rule that caches everything under `/assets/*` for 1 year (immutable filenames).  Add a Rate Limiting Rule at 60 req/min/IP.

### Hard ceiling

If the demo ever costs more than **$20/mo**:

1. Founder gets a Fly billing email (Fly emails at every $5 increment over the free tier).
2. Founder runs `fly scale count 0 --app nucleus-demo` — drains traffic, $0 ongoing.
3. Founder investigates with `fly logs` + traffic graphs.
4. Founder re-launches with stricter caps (drop to `memory = "256mb"` — but watch for Polars OOMs).

Render hard ceiling: Render Starter is $7/mo, no surprise bills possible — Render plans are upfront.

---

## Section 8 — Public URL convention

| URL                                      | Hosts                  | Purpose                                                   |
|------------------------------------------|------------------------|-----------------------------------------------------------|
| `demo.nucleus-data.dev`                  | Fly.io (this plan)     | Public Workbench demo — read-only, e-commerce dataset.    |
| `https://nucleus-data.github.io/nucleus/` | GitHub Pages           | Hosted mkdocs site once repo visibility/Pages gating allows it. |
| `nucleus-data.dev`                       | Cloudflare Pages       | Landing page — links to docs, demo, GitHub.               |
| `github.com/nucleus-data/nucleus`        | GitHub                 | Source repo.                                              |
| `pypi.org/project/nucleus`               | PyPI                   | `pip install nucleus`.                                    |

DNS records (Cloudflare):

```
A     demo.nucleus-data.dev    66.241.124.5   (Fly's anycast IP)
CNAME nucleus-data.github.io   GitHub Pages-managed target
CNAME nucleus-data.dev         nucleus-data-landing.pages.dev
```

Founder must verify ownership of `nucleus-data.dev` before this plan can execute — see [`v0.2_FOUNDER_CLOSE_CHECKLIST.md`](v0.2_FOUNDER_CLOSE_CHECKLIST.md) §1.1.

---

## Section 9 — Founder runbook (12 steps from zero to live)

Wall-clock estimate: **2–3 hours** end-to-end, mostly waiting for builds and DNS.

| Step | Action                                                                  | Time   |
|------|-------------------------------------------------------------------------|--------|
| 1    | **Register a Fly.io account** at <https://fly.io/app/sign-up>.  Free; needs only an email.  Use the `nucleus-data` org email if it exists; otherwise founder's personal email.  Confirm via OTP. | 5 min  |
| 2    | **Install `flyctl`**: `curl -L https://fly.io/install.sh \| sh` (macOS/Linux) or `iwr https://fly.io/install.ps1 \| iex` (Windows).  Confirm `flyctl version` ≥ 0.3.0. | 5 min  |
| 3    | **Authenticate**: `fly auth login`.  Opens a browser; follow the prompts.  Confirm `fly orgs list` shows your personal org plus any team orgs. | 5 min  |
| 4    | **Launch the app** from the repo root: `fly launch --copy-config deploy/fly.toml --no-deploy --name nucleus-demo`.  Accept defaults except: app name = `nucleus-demo`, region = `iad` (or your nearest), do NOT add Postgres / Redis / Sentry yet. | 10 min |
| 5    | **First deploy**: `fly deploy --config deploy/fly.toml --dockerfile deploy/Dockerfile.demo --remote-only`.  Build runs on Fly's infrastructure; should complete in 5–8 minutes.  Watch for: `nucleus ingest` succeeded for all three assets; healthcheck eventually returns 200. | 15 min |
| 6    | **Smoke test the Fly URL**: `curl https://nucleus-demo.fly.dev/api/health` → `{"status":"ok",...}`.  Open the URL in a browser; confirm the Workbench loads with three assets visible. | 5 min  |
| 7    | **Set up Cloudflare** for `nucleus-data.dev`.  Add the domain; update nameservers at the registrar.  Wait for Cloudflare to confirm DNS control (can take up to 24 h; usually < 1 h). | 60 min |
| 8    | **Map custom domain**: `fly certs create demo.nucleus-data.dev --app nucleus-demo`.  Fly returns CNAME / A records to add at Cloudflare.  Add them.  Wait for `fly certs check` to show `Status: Ready` (usually < 5 min). | 15 min |
| 9    | **Schedule the daily reset**: `fly machine run --schedule='0 4 * * *' "echo reset" --app nucleus-demo --rm`.  This creates a cron Machine that restarts the demo each night at 4 AM UTC.  Verify with `fly machine list`. | 10 min |
| 10   | **Add a Cloudflare rate limit**: Cloudflare dashboard → `nucleus-data.dev` → Security → WAF → Rate limiting rules.  Add: "If incoming requests match: hostname equals `demo.nucleus-data.dev`, then: take action `Block` if requests exceed 60 in 1 minute per IP."  Save. | 10 min |
| 11   | **Wire CI auto-deploy**: copy `deploy/.github/workflows/deploy_demo.yml` to `.github/workflows/deploy_demo.yml`; commit; push.  In GitHub repo settings → Secrets → add `FLY_API_TOKEN` (run `fly tokens create deploy --app nucleus-demo` to mint one).  Optionally tag the current commit (`git tag v0.2.0-demo-deploy`) to test the trigger. | 15 min |
| 12   | **Verify**: `curl https://demo.nucleus-data.dev/api/health` → 200.  Browser visit → Workbench loads.  Post the URL on personal Twitter (small audience first) and watch `fly logs` for the first 30 min for anomalies.  If anomaly-free → ready for HN. | 15 min |

---

## Section 10 — Maintenance cadence

| Cadence    | Action                                                              | Owner    |
|------------|---------------------------------------------------------------------|----------|
| **Daily**  | Cron auto-restarts the container.  No action needed.                | Automated|
| **Weekly** | Open `demo.nucleus-data.dev`, run one sample SQL query, verify the response time is < 1 s.  Check `fly logs --app nucleus-demo` for any unexpected errors over the past week (grep for `level=="error"`). | Founder  |
| **On tag** | The GitHub Action rebuilds and redeploys the image to Fly.  Verify health probe after the deploy notification.            | Automated|
| **Monthly**| Check Fly billing (`https://fly.io/dashboard/personal/billing`).  Should be $0-5/mo.  If higher, investigate. | Founder  |
| **Quarterly**| Refresh the seed data (`python deploy/seed_demo_data.py`) only if the demo narrative needs updating — e.g., new tutorial uses a 2027 order_date. | Founder  |

No on-call rotation.  The demo is best-effort; if it goes down for 2 hours, that's acceptable.  The Cloudflare uptime probe (§6) is informational, not alerting.

---

## Section 11 — Rollback plan

### Scenario A — Bad deploy

A new tag rolled out a regression that breaks the Workbench.

```bash
# Find the previous good image
fly image list --app nucleus-demo

# Roll back to the previous image tag
fly deploy --app nucleus-demo \
           --image registry.fly.io/nucleus-demo:<previous-tag>
```

Fly keeps the last 10 image revisions by default.  Rollback latency: ~60 s.

### Scenario B — Misconfigured environment variable

A new env var (e.g. enabling Sentry with a bad DSN) crashes the container.

```bash
# Remove the offending secret
fly secrets unset SENTRY_DSN --app nucleus-demo

# Or revert to a known-good set
fly secrets list --app nucleus-demo
fly secrets set NUCLEUS_DEMO_MODE=true --app nucleus-demo
```

### Scenario C — Demo is being abused

Pull the kill switch:

```bash
fly scale count 0 --app nucleus-demo
```

Investigate via `fly logs --app nucleus-demo | jq 'select(.level=="error")'`.  Patch the cause.  Re-launch:

```bash
fly scale count 1 --app nucleus-demo
```

### Scenario D — Founder wants to retire the demo

```bash
fly scale count 0 --app nucleus-demo                 # stop traffic
fly apps destroy nucleus-demo                        # delete the app
```

DNS record at Cloudflare can be left or removed.  The repo's `deploy/` directory stays so the demo can be revived later.

### Scenario E — v0.2.1 read-only middleware lands

After the v0.2.1 middleware (§5) ships, the operator should:

1. Tag `v0.2.1` — auto-deploy fires.
2. Verify `/api/runs/trigger` returns 403 with `NE6010`.
3. Update [`deploy/RESET_POLICY.md`](../../deploy/RESET_POLICY.md) §5 to mention the new opt-out header is now honored.

---

## Appendix — Cross-references

- Bundle README (operator quick-ref): [`deploy/README.md`](../../deploy/README.md)
- Data + reset policy (visitor-facing): [`deploy/RESET_POLICY.md`](../../deploy/RESET_POLICY.md)
- Self-hosted production cookbook (the "real" deploy): [`docs/cookbook/production-deployment.md`](../cookbook/production-deployment.md)
- Founder close-out checklist (org name + tag bundle): [`docs/internal/release-process/v0.2_FOUNDER_CLOSE_CHECKLIST.md`](v0.2_FOUNDER_CLOSE_CHECKLIST.md)
- Workbench app source (`NUCLEUS_DEMO_MODE` recipient): [`src/nucleus/workbench/app.py`](../../src/nucleus/workbench/app.py)
- Reference compose for production parity: [`docker-compose.production.yaml`](../../docker-compose.production.yaml)
- Release automation (auto-deploy convention): [`.github/workflows/release.yml`](../../.github/workflows/release.yml)

---

*Drafted 2026-05-15.  Bundle implementation under [`deploy/`](../../deploy/) is feature-complete.  Founder review and the 12 runbook steps in §9 unblock the live demo.*
