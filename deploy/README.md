# `deploy/` — Public demo bundle

This directory ships everything required to launch the public Nucleus demo
at **`demo.nucleus-data.dev`**.  It is a *deployment bundle*, not part of the
core `src/nucleus/` runtime — nothing here is imported by the library.

For the full strategy + cost analysis + 12-step founder runbook, read
[`docs/release/public_demo_deploy_plan.md`](../docs/release/public_demo_deploy_plan.md).

This README is the **operator quick-reference** — how to run, debug, and
iterate on the demo locally.

## File map

| File                                        | Purpose                                                      |
|---------------------------------------------|--------------------------------------------------------------|
| `seed_demo_data.py`                         | Deterministic e-commerce data generator (stdlib only).       |
| `nucleus_project.demo.yaml`                 | Project config baked into the image (filesystem catalog).    |
| `Dockerfile.demo`                           | Multi-stage build → 512 MB image with seed warehouse baked.  |
| `docker-compose.demo.yml`                   | Local equivalent of the production deploy.                   |
| `fly.toml`                                  | Fly.io app config (**recommended host**).                    |
| `render.yaml`                               | Render.com blueprint (alternative host).                     |
| `vercel.json`                               | Static-frontend-only Vercel config (pair with Fly backend).  |
| `.github/workflows/deploy_demo.yml`         | Tag-triggered CI deploy (Fly + Render).                      |
| `RESET_POLICY.md`                           | Why we reset daily; visitor opt-out for query logs.          |
| `README.md`                                 | This file.                                                   |

## Quickstart — run the demo locally

Prerequisites: Docker Desktop or Docker Engine ≥ 24, ~1.5 GB free disk.

```bash
docker compose -f deploy/docker-compose.demo.yml up --build
```

Open **http://127.0.0.1:8080**.  You should see the Workbench loaded with
three assets: `raw.products`, `raw.customers`, `raw.orders`.

To stop:

```bash
docker compose -f deploy/docker-compose.demo.yml down
```

## Quickstart — regenerate seed data

```bash
python deploy/seed_demo_data.py --output-dir ./demo-data/raw
```

Outputs three CSVs (`products.csv`, `customers.csv`, `orders.csv`) under
`demo-data/raw/`.  The Dockerfile copies these into the image and runs
`nucleus ingest` to convert them to Iceberg.

To tweak row counts (must rebuild image after):

```bash
python deploy/seed_demo_data.py \
    --output-dir ./demo-data/raw \
    --products 200 \
    --customers 500 \
    --orders 5000
```

Sticking to `42` as the random seed means two runs of `seed_demo_data.py`
with identical args produce **byte-identical** CSVs — Docker layer cache
reuses the `COPY` layer, so iteration is fast.

## Read-only mode (v0.2.1 ask)

The image exports `NUCLEUS_DEMO_MODE=true` (see `Dockerfile.demo` line 99).
Today, this env var is **advisory** — the Workbench (v0.2.0 GA) does not yet
read it.  Safety is enforced via two complementary layers:

1. **Filesystem permissions**: `Dockerfile.demo` chmods the seeded warehouse
   to `0444` (files) / `0555` (directories) **before** dropping to the
   non-root `nucleus` user.  Even if a write endpoint slipped through, the
   OS denies the I/O.
2. **No LLM key shipped**: the image does not include `OPENAI_API_KEY` /
   `ANTHROPIC_API_KEY`, so `/api/chat` returns an `NE6001` error (graceful
   per `src/nucleus/intelligence/copilot.py`) rather than burning tokens.

**Recommended for v0.2.1** (flagged in `docs/release/public_demo_deploy_plan.md`
§5): the Workbench should read `NUCLEUS_DEMO_MODE` at startup and:
- Return **HTTP 403** on `POST /api/runs/trigger`, `POST /api/chat`, and
  any mutating SQL submitted to `POST /api/query`.
- Show a banner in the UI: *"This is a read-only demo — try Nucleus
  locally with `pip install nucleus-data`."*

Until the read-only middleware ships, deploys MUST keep the filesystem
chmod layer.  Do not change `Dockerfile.demo` lines 86-88 without first
landing the Workbench middleware.

## Deploy targets — when to use which

| Target  | When                                                      | Cost            |
|---------|-----------------------------------------------------------|-----------------|
| Fly.io  | Default — single Docker, fast cold-wake, custom domain.   | **~$0-5/mo**    |
| Render  | Prefer Render's PR-preview UX or already on Render.       | $0 (cold) / $7  |
| Vercel  | Static frontend + Fly/Render backend (split deploy).      | $0              |

Full comparison + recommendation in `public_demo_deploy_plan.md` §2-3.

## Manual deploy commands

### Fly.io (recommended)

```bash
fly launch --copy-config deploy/fly.toml --no-deploy   # first time
fly deploy --config deploy/fly.toml \
           --dockerfile deploy/Dockerfile.demo \
           --remote-only
fly certs create demo.nucleus-data.dev --app nucleus-demo
```

### Render

Trigger via the deploy hook (founder copies the URL from the Render
dashboard after creating the service):

```bash
curl -X POST "$RENDER_DEPLOY_HOOK_URL"
```

Or rely on `autoDeploy: true` in `render.yaml` — any push to `main`
auto-deploys.

### Vercel (frontend-only)

```bash
vercel deploy --prod --config deploy/vercel.json
vercel domains add demo.nucleus-data.dev
```

## CI deploy — `.github/workflows/deploy_demo.yml`

This bundle ships a template workflow at `deploy/.github/workflows/deploy_demo.yml`.
**It is not active until the founder copies it to the repo's real workflow
directory**:

```bash
cp deploy/.github/workflows/deploy_demo.yml \
   .github/workflows/deploy_demo.yml
```

Then set the secret(s) corresponding to the chosen host:

| Secret                  | Required for | Where to get it                                        |
|-------------------------|--------------|--------------------------------------------------------|
| `FLY_API_TOKEN`         | Fly.io       | `fly tokens create deploy` → store in repo secrets.    |
| `RENDER_DEPLOY_HOOK_URL`| Render       | Render dashboard → service → Settings → Deploy Hook.   |

If a secret is missing the corresponding job no-ops (`if env.... != ''`).

## Debugging the live demo

### Logs

```bash
fly logs --app nucleus-demo
# OR
render logs --service nucleus-demo   # via Render CLI
```

Logs are JSON-formatted (`NUCLEUS_LOG_FORMAT=json`) — pipe to `jq` for
filtering:

```bash
fly logs --app nucleus-demo | jq 'select(.level=="error")'
```

### Health probe

```bash
curl https://demo.nucleus-data.dev/api/health
# {"status":"ok","version":"0.2.0"}
```

### Drain traffic immediately (kill switch)

If the demo is being abused or producing bad behavior:

**Fly.io**:
```bash
fly scale count 0 --app nucleus-demo
```
Zero machines = zero traffic + zero cost.  To restore:
```bash
fly scale count 1 --app nucleus-demo
```

**Render**:  Dashboard → service → Settings → Suspend.

**Cloudflare** (if it fronts the demo): Rules → Page Rules → add a 503
rule for the entire domain.  Survives a host outage; survives the host
not honoring the kill switch.

## Maintenance cadence

- **Weekly** (Monday): visit https://demo.nucleus-data.dev/api/health
  manually.  Plan §10 covers the full checklist.
- **On tag** (e.g., v0.2.1): the GitHub Action rebuilds + redeploys.
- **Daily**: the reset cron (see `RESET_POLICY.md`) rebuilds the warehouse
  from the baked Iceberg state.

## Anti-patterns

1. **Do not commit `.fly/`, `.vercel/`, `.env`, or any host-generated dir**.
   These contain auth tokens (Fly/Vercel) and runtime state.  `.gitignore`
   should already exclude them; verify before adding files here.
2. **Do not bake real PII or customer data into `seed_demo_data.py`**.
   Even if a user demo'd Nucleus on real data, the public demo MUST stay
   synthetic.  `RESET_POLICY.md` makes this contract explicit.
3. **Do not skip the smoke test** in the deploy workflow.  The `Dockerfile.demo`
   `nucleus ingest` step is the most fragile part of the bundle — break it
   and the demo serves an empty warehouse.
4. **Do not enable Workbench `/api/chat`** in the demo without first wiring
   an LLM-cost budget (Hard Constraint #7 — `AGENTS.md` §3).  The image
   intentionally omits any LLM key.
5. **Do not point the demo at a real S3 bucket**.  The seed warehouse is
   filesystem-only by design; pointing at S3 introduces a write surface
   even with read-only IAM.

## Cross-references

- Strategy + cost analysis: [`docs/release/public_demo_deploy_plan.md`](../docs/release/public_demo_deploy_plan.md)
- Reset cadence + data policy: [`RESET_POLICY.md`](RESET_POLICY.md)
- Production-equivalent compose: [`docker-compose.production.yaml`](../docker-compose.production.yaml)
- Production cookbook: [`docs/cookbook/production-deployment.md`](../docs/cookbook/production-deployment.md)
- Founder close-out: [`docs/internal/release-process/v0.2_FOUNDER_CLOSE_CHECKLIST.md`](v0.2_FOUNDER_CLOSE_CHECKLIST.md)
