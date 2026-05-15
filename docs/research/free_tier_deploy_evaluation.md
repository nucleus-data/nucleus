# Free-Tier Deploy Stack — Evaluation vs Nucleus Architecture

> **Last verified**: 2026-05-15 against Cloudflare R2, Oracle Always Free, Supabase, Vercel, MongoDB Atlas, Render, Koyeb, MotherDuck official pricing/docs. AI training cutoff may be stale; this doc reflects docs fetched 2026-05-15.
> **Tier per AGENTS.md §1**: N/A — this is a *deployment topology* evaluation, not a wrap-target study. The proposal targets infrastructure (compute hosts, object storage, managed Postgres, CDN), not wrapped engines.
> **Status**: Research only — no code, ADR, deploy plan, or architecture file modified. Recommendations in §6 are founder-gated.
> **Scope**: The founder shared a $0/mo "Permanent Free" proposal (Oracle Always Free + Supabase + Vercel + Cloudflare Tunnel + DuckDB + JupyterLab + R2 + MotherDuck) ~30 min after `docs/release/public_demo_deploy_plan.md` shipped. This doc evaluates the proposal against Nucleus architecture and the existing deploy plan.

---

## 1. TL;DR verdict

- **Framing A — Replace Nucleus? → NO.** JupyterLab, Supabase-Postgres-as-warehouse, MotherDuck as v0.1 critical-path, Apache Zeppelin, and RabbitMQ-as-orchestration violate `AGENTS.md §3` Hard Constraints or `§20` Non-Goals. The proposal describes a DIY analytics stack, not a Nucleus deployment.
- **Framing B — Host the public demo? → YES IN PART.** Four elements (**Cloudflare R2** + **Cloudflare Tunnel** + **Vercel Hobby static frontend** + **Oracle Always Free Ampere A1**) are concretely adoptable for `demo.nucleus-data.dev`, future `try.nucleus.dev`, or Cloud-tier preview v0.4+. The existing `public_demo_deploy_plan.md` already adopts Vercel and Cloudflare; R2, CF Tunnel, Oracle Ampere are NEW substrate worth documenting.
- **Existing plan stays.** Plan §3 (Fly.io + Vercel split-frontend) is not invalidated — the proposal surfaces alternates worth documenting as Plan B/C.
- **One NEEDS VERIFICATION**: "Koyeb Micro-VMs (no sleep)" not on current pricing page (Pro starts $29/mo; only Postgres "Free 5h" is permanent).
- **Two services overstate "permanent free"**: Supabase pauses after **7 days inactivity**; Render Free sleeps after **15 min idle** (~30 s cold start). Both in plan §2.

---

## 2. The two framings (do not conflate)

### Framing A — "This stack replaces Nucleus" → REJECT

Adopting the proposal *as Nucleus architecture* violates locked constraints:

| Element | Violates | Citation |
|---|---|---|
| JupyterLab as notebook | `nucleus.mdc` Tier picks Marimo; Jupyter is swap target | `AGENTS.md §4`, `nucleus.mdc` line 30, `docs/research/marimo.md` |
| Apache Zeppelin | §3 HC#1 (no JVM in core path) | `AGENTS.md §3`, `§4.2` |
| Supabase Postgres as **warehouse** | `§5.7` + `§10.1`: Iceberg-on-S3 is the warehouse; Postgres is **source asset** | `§5.5.1`, `§5.7`, `§10.1` |
| MotherDuck as v0.1 critical-path | `§18.1` v0.1 = DuckDB+Polars only; MotherDuck = Mode 2 v1.5+ per ADR-035 | ADR-035 Decision |
| RabbitMQ/Kafka as orchestration | §3 HC#3 (no custom scheduler — Dagster wrapped) | `AGENTS.md §3`, `§6.1` |
| MongoDB Atlas as "centralized database" | No "centralized database" primitive — asset graph + Iceberg catalog is central | `AGENTS.md §0`, `§12.1` |

The proposal frames as **"build a DIY analytics platform on free tiers."** Nucleus per `AGENTS.md §0` is **"a local-first Python SDK + CLI that ships data products from a laptop."** Different products. The proposal could host *a Nucleus deployment*; it cannot *be* Nucleus.

### Framing B — "This stack hosts the public demo of Nucleus" → ACCEPT IN PART

Four elements concretely adoptable for `demo.nucleus-data.dev`, `try.nucleus.dev`, or v0.4+ Cloud preview:

- **Cloudflare R2 (10 GB free + zero egress)** — already a documented swap target per `§5.7` v0.5+. Near-perfect fit for read-only public demo.
- **Cloudflare Tunnel (`cloudflared`)** — replaces nginx+letsencrypt at demo edge with zero-config HTTPS and no public IP. Stronger kill-switch.
- **Vercel Hobby (already in plan)** — `deploy/vercel.json` exists; plan §3 Option B. ToS caveat — §5.4.
- **Oracle Always Free Ampere A1 (4 OCPU / 24 GB Arm)** — substrate for future heavier-demo or Fly fallback. NOT v0.2 priority.

---

## 3. Per-element verdict table

Verdicts: `ADOPT-FOR-DEMO`, `DEFER-TO-vX.Y`, `REJECT-IDENTITY-CONFLICT`, `REJECT-CONSTRAINT-VIOLATION`, `ALREADY-IN-DEPLOY-PLAN`.

| Component | Founder proposal | Verdict | Reason + citation |
|---|---|---|---|
| **Compute heavy** | Oracle Ampere A1 4 OCPU / 24 GB | **ADOPT-FOR-DEMO (Plan B)** | 47× RAM headroom vs Fly `shared-cpu-1x@512mb` (plan §3). Valuable for future heavier-demo / Fly fallback. NOT v0.2 priority. See `§11.2` (local-first targets). |
| **Compute light cron/API** | Render Free / Koyeb Micro | **ALREADY-IN-DEPLOY-PLAN + NEEDS VERIFICATION (Koyeb)** | Plan §2 analyzed Render's 30 s cold start. Koyeb "no-sleep Micro" not visible on current pricing — §7. |
| **Frontend** | Vercel / Cloudflare Pages | **ALREADY-IN-DEPLOY-PLAN** | `deploy/vercel.json` + plan §3 Option B + §8 CF Pages. ToS caveat — §5.4. |
| **Database (centralized)** | Supabase Postgres / MongoDB Atlas | **REJECT-IDENTITY-CONFLICT** | No "centralized database" primitive. Postgres is **source asset** per `§5.5.1`. `AGENTS.md §0`: "It is **not** a database." |
| **Notebook / Compute UI** | JupyterLab / Zeppelin | **REJECT-IDENTITY-CONFLICT** | `nucleus.mdc` Tier picks Marimo (v0.3+); v0.1 has NO notebook (`§18.1`). Zeppelin also violates `§3` HC#1 no-JVM. |
| **Data lake** | Oracle Obj 20 GB / R2 10 GB | **ADOPT-FOR-DEMO (R2)** + **DEFER-TO-v0.4 (Oracle Obj)** | `§4.1` Tier 0 S3 API universal. `§5.7` v0.5+: "Cloudflare R2 Data Catalog (swap interface)". Zero egress ideal for demo. |
| **Query engine** | DuckDB / MotherDuck | **ADOPT (DuckDB — already)** + **DEFER-TO-v1.5 (MotherDuck)** | DuckDB pinned `1.1.3` (ADR-012). MotherDuck v1.5+ per ADR-035; Iceberg/DuckLake NV-6 unresolved. |
| **Data warehouse (processed)** | Supabase Postgres 500 MB | **REJECT-IDENTITY-CONFLICT** | Breaks Mode 1 graduation (`§10.1`) — giants consume Iceberg, not Postgres. Caps at 500 MB << beachhead 100 GB-5 TB target (`§1.5`). |
| **Networking / edge** | Cloudflare Tunnel | **ADOPT-FOR-DEMO** | Replaces public IP with outbound-only `cloudflared`. Stronger DDoS posture than DNS proxy alone. |
| **Async queue** | CloudAMQP / Upstash | **REJECT-CONSTRAINT-VIOLATION** | Adding RabbitMQ/Kafka = two scheduler-shaped surfaces. Anti-Over-Engineering Discipline (`nucleus.mdc` line 169) forbids. Dagster run coordinator already handles queueing (`§6.1`). |
| **Identity / auth** | (Implied none) | **ALREADY-IN-DEPLOY-PLAN** | HC#6 OIDC delegation; demo anonymous (plan NG4). Production: `nucleus enable polaris`/`lakekeeper` per ADR-004. |

---

## 4. Identity conflicts (with citations)

**4.1 JupyterLab vs Marimo** — `AGENTS.md §4`: "Custom notebook runtime → use Marimo". `nucleus.mdc` Tier line 30: "Notebooks | Marimo | Jupyter (swap target)". `docs/research/marimo.md` §2: Marimo cells form a reactive DAG via reference analysis — the property that lets cells promote cleanly to `@nucleus.asset` decorators. Jupyter has hidden cell-order state; adopting it as core would break the v0.3+ "notebook ↔ asset" promotion story.

**4.2 Apache Zeppelin** — `AGENTS.md §3` HC#1: "No JVM in core path." Zeppelin runs on the JVM and ties to Spark/Hive. Polaris (JVM-in-own-process, ADR-002 §6) is the *one* documented exception, gated behind `nucleus enable polaris` as alternate catalog. No equivalent justification for Zeppelin.

**4.3 Supabase Postgres as data warehouse** — `§5.7`: "v0.1 catalog: filesystem via `pyiceberg.SqlCatalog`. v0.3+: Lakekeeper / Polaris." `§10.1` Mode 1: "user graduates with zero migration because Iceberg-on-S3 is the destination." `§1.5` beachhead: "5-engineer team builds **Postgres → Iceberg** first table in <30 min." Postgres is the SOURCE; Iceberg is the destination. Treating Postgres as warehouse (a) breaks Mode 1 graduation — Databricks/Snowflake/Polaris/R2 all consume Iceberg, not Postgres — (b) caps scale at 500 MB << 100 GB-5 TB persona target, (c) re-introduces `table` as primitive (banned per `AGENTS.md §7`).

**4.4 MotherDuck as v0.1 critical-path** — ADR-035 Decision: "Watch-list; plan at v0.3; integrate at v1.5+." NV-6: "Are Nucleus's Iceberg files directly attachable to MotherDuck? MotherDuck uses DuckLake as native lakehouse format. **Must resolve before integration**." Canonical Mode 2 reference (`§10.2`) but for v1.5+, NOT v0.1.

**4.5 RabbitMQ / Kafka as orchestration** — `AGENTS.md §3` HC#3: "No custom scheduler — Dagster wrapped." Dagster's run coordinator already handles queueing. Adding RabbitMQ = two scheduler-shaped surfaces. Anti-Over-Engineering Discipline (`nucleus.mdc` line 169) bans directly.

**4.6 "DIY platform" vs "coherent product" framing (most important)** — `AGENTS.md §0`: "We own three things, forever: the asset graph, the `ctx` SDK, the **unified developer-first experience**." The proposal stitches **9 vendors**; Nucleus's value prop per ADR-002 §8.1 is replacing "15 disjoint tools" with one coherent UX. The Felt Moat (`§2.1` friction-elimination) evaporates if Nucleus IS 9 vendors. **This is the central conflict**: the proposal works for the founder's weekend project. It does not work as the product Nucleus has decided to be.

---

## 5. Adoptable substrate (for the demo plan or v0.4+ Cloud preview)

### 5.1 Oracle Always Free Ampere A1 — for `try.nucleus.dev` heavier demo (deferred)

**Verified specs** (https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm#compute):

- 3,000 OCPU-hours + 18,000 GB-hours/month on `VM.Standard.A1.Flex` (Arm) = **4 OCPUs + 24 GB RAM total**, up to 4 instances (47 GB min boot vol each)
- 200 GB block volume (boot + data combined); 20 GB Object Storage (S3-compatible); **10 TB outbound/month**
- "For the life of the account" in the home region

**Catch** (same URL): "Idle Always Free instances may be reclaimed… during a 7-day period: CPU < 20%, Network < 20%, Memory < 20% (A1 only)." **Mitigation**: a 5-min uptime probe (already in `public_demo_deploy_plan.md §6`) keeps utilization above 20%.

**When to fold in**: NOT v0.2. Plan B for `try.nucleus.dev` heavier demo, Fly.io fallback, or CI runners for `pyiceberg-0.11.x` migration smoke tests (ADR-003).

### 5.2 Cloudflare R2 — `demo.nucleus-data.dev` warehouse + future Cloud preview

**Verified specs** (https://developers.cloudflare.com/r2/pricing/):

- Free: **10 GB-month** (Standard storage only), **1M Class A ops/month**, **10M Class B ops/month**
- **Zero egress fees** via S3 API, Workers API, or `r2.dev` domains
- R2 Data Catalog (Iceberg REST API on top of R2) in public beta — free outside storage/op charges

**Fit**: baked seed warehouse (~400 KB Iceberg metadata + Parquet) fits 25,000× over. Class B reads dominate read-only demo; 10M/mo cap = ~333,333 reads/day pre-charge. Zero egress kills the S3-on-AWS HN-spike failure mode. Iceberg files written by `pyiceberg==0.8.1` work against R2 with no code change (`s3fs` + `pyiceberg.SqlCatalog` + DuckDB `httpfs` per `§5.8` + ADR-008 + `docs/research/s3_duckdb.md`).

**When to fold in**: demo upgrade — `demo.nucleus-data.dev` reads warehouse from a public-read R2 bucket instead of in-image filesystem. Decouples demo data from Docker image. **Effort: ~2 hours**.

### 5.3 Cloudflare Tunnel — replaces nginx/letsencrypt at the demo edge

**Verified specs** (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):

- `cloudflared` daemon: **outbound-only** connections origin→Cloudflare; no publicly routable IP needed; HTTPS auto
- Verbatim: "configure your firewall to allow only these outbound connections and block all inbound traffic"
- Free tier — no Zero Trust paid subscription required

**Fit**: today `public_demo_deploy_plan.md §8` maps `demo.nucleus-data.dev` to Fly anycast IP (publicly addressable). With CF Tunnel, the Fly machine closes port 8080 and accepts only `cloudflared` outbound — closes the "DDoS bypasses CF" vector.

**Caveat**: `cloudflared` adds RAM (~50-100 MB estimate, NEEDS VERIFICATION). At 512 MB Fly memory, budget is tight. **When to fold in**: v0.2.1+ hardening, lower priority than the read-only middleware (`public_demo_deploy_plan.md §5`).

### 5.4 Vercel Hobby — already in deploy plan, with ToS caveat

**Verified specs** (https://vercel.com/pricing + https://vercel.com/legal/terms §4):

- Hobby: 100 GB bandwidth/mo, 1M Edge Requests, 1M Function Invocations, 100 GB Fluid Compute hours
- **Critical ToS §4** (verbatim): *"You shall only use the Services under a Hobby plan for your **personal or non-commercial use**. We may change the features, limitations, or other conditions applicable to the Hobby plan or discontinue offering the Hobby plan at any time."*

**Fit**: `deploy/vercel.json` already configured for the static SPA; FastAPI backend correctly excluded (Python serverless cold-start + Polars memory caps make Vercel unsuitable as backend per `public_demo_deploy_plan.md §2`).

**Commercial-use concern**: `demo.nucleus-data.dev` markets a planned commercial Cloud tier (`§17.1`). Vercel could argue commercial use. Options: (a) document as non-commercial pre-revenue in `deploy/README.md`; (b) pre-upgrade Vercel Pro $20/mo before any Cloud announcement; (c) move static hosting to Cloudflare Pages (NEEDS VERIFICATION on Pages ToS clause). **Recommendation**: surface as pre-Cloud-launch gate in `v0.2_FOUNDER_CLOSE_CHECKLIST.md` (RECOMMENDATION 5).

---

## 6. Concrete recommendations

Format: **RECOMMENDATION N — Owner — Target — 8-question gate — Effort**.

**REC-1 — R2-backed `demo.nucleus-data.dev` warehouse (optional Plan B)**
- Owner: founder ratifies → builder swarm wires env vars
- Target: amend `public_demo_deploy_plan.md` §4; new `deploy/Dockerfile.demo.r2` variant
- 8-Q gate: Q1 YES (L0), Q2 NEUTRAL (demo not beachhead), Q3 YES (s3fs+pyiceberg already wrapped), Q4 YES (opaque S3), Q5 YES (local MinIO/SeaweedFS preserved), Q6 YES (~10 LOC config), Q7 NEUTRAL (founder-driven), Q8 NO (defer to v0.2.x)
- Effort: 2-4 hours

**REC-2 — Hold MotherDuck for v1.5+ (preserve ADR-035)**
- Owner: founder (no action — ADR-035 holds). 8-Q gate Q8 fails: MotherDuck is v1.5+. Effort: 0.

**REC-3 — Reject JupyterLab and Zeppelin from demo plan**
- Owner: founder (no action). `nucleus.mdc` Tier line 30 + `docs/research/marimo.md` remain canonical. 8-Q gate Q4 (no-JVM) fails for Zeppelin; Q8 fails for both. Effort: 0.

**REC-4 — Document Cloudflare Tunnel as v0.2.1 demo-edge hardening**
- Owner: builder swarm (after v0.2.0 tag pushed)
- Target: amend `public_demo_deploy_plan.md` §5; optional `deploy/cloudflared.yml`
- 8-Q gate: Q3 wrap YES, Q4 no-JVM YES (Go binary), Q7 empirical MED (strengthens kill switch), Q8 NO (v0.2.1 hardening)
- Effort: 4 hours

**REC-5 — Add Vercel ToS §4 gate before Cloud commercial launch**
- Owner: founder
- Target: new Section in `v0.2_FOUNDER_CLOSE_CHECKLIST.md` ("Vercel ToS §4 acknowledgment"); warn in `public_demo_deploy_plan.md §8`
- 8-Q gate: Q8 YES if Cloud SKU announced; else NO
- Effort: 15 min read + 5 min checklist edit

**REC-6 — Verify Koyeb claim before any future deploy plan reference**
- Owner: researcher (next pass against https://www.koyeb.com/pricing). Effort: 30 min.

**REC-7 — Defer ADR-040 (Cloud-tier free-tier substrate matrix)**
- Owner: founder draft after PoC #5 signal. Target: `docs/decisions/ADR-040-cloud-preview-free-tier-substrate.md` (NOT opened today). Trigger: 3+ external testers + Cloud Preview SKU decision per `§17.1` v0.4+. Effort: defer; 4-6 hours.

**REC-8 — DO NOT amend `nucleus_architecture_v4.1.md` §13 from this proposal**
- Owner: founder (preserve architect-only edit boundary per AGENTS §11.12). Proposal is operational, not architectural. Effort: 0 (guardrail reminder).

---

## 7. Cost-bill traps (verified docs URLs)

The founder's instinct ("absolutely no AWS/GCP/Azure") is correct — AWS Always Free → pay-as-you-go conversion is a known trap. Other free tiers have their own. Each row verified 2026-05-15.

| Service | Verified status + URL | Trap |
|---|---|---|
| **Oracle Always Free** | TRUE for home-region Always-Free-eligible resources. https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm | Resources OUTSIDE home region incur charges. Free Trial auto-converts to PAYG at trial end (but Always-Free resources remain free). **Idle A1 reclaimed after 7 days < 20% CPU+net+mem.** Mitigation: home region only, 5-min uptime probe. |
| **Cloudflare R2** | TRUE: 10 GB-month Standard, 1M Class A, 10M Class B, zero egress. https://developers.cloudflare.com/r2/pricing/ | Free tier applies only to Standard storage (not Infrequent Access). Above 10 GB-month: $0.015/GB-month. Rounding: 1.1 GB bills as 2 GB. No card at signup. |
| **Cloudflare Tunnel** | TRUE. https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/ | Cloudflare account required (no card). `cloudflared` is OSS (Apache-2.0). No trap. |
| **Supabase Free** | TRUE: 500 MB, 5 GB egress, 50K MAU. https://supabase.com/pricing | **Projects pause after 1 week inactivity. Limit of 2 active projects.** Pause = Postgres offline. Unpausing is manual. **Trap for a demo**: 7 days zero traffic → demo dies. No auto-bill. |
| **Vercel Hobby** | TRUE limits per §5.4. https://vercel.com/pricing | **Non-commercial use only per ToS §4** (verbatim in §5.4). `demo.nucleus-data.dev` markets a planned commercial Cloud → grey zone. Hobby does NOT auto-upgrade; overage forces upgrade prompt. |
| **MongoDB Atlas M0** | TRUE: 512 MB, shared. https://www.mongodb.com/pricing | Idle M0 auto-pauses (window NEEDS VERIFICATION at https://www.mongodb.com/docs/atlas/billing/free-shared-clusters/). No card. Not adopted by Nucleus regardless (§4). |
| **Render Free Web** | TRUE: 512 MB, 0.1 CPU. https://render.com/pricing | Sleeps after 15 min idle, ~30 s cold start (already in `public_demo_deploy_plan.md §2`). Wipes scratch on every deploy. Mitigated by preferring Fly. |
| **Koyeb "Micro-VM no sleep"** | **NEEDS VERIFICATION** — not visible on current pricing. https://www.koyeb.com/pricing | Pro starts at $29/mo + compute; only Postgres "Free 5h" permanent. Founder may reference deprecated tier. Verify before any deploy plan mention. |
| **MotherDuck Lite** | TRUE: 10 GB storage + 10 hr Pulse compute/mo, up to 3 users. https://motherduck.com/pricing/ | Pulse-only ($0.60/hr after cap). Storage $0.04/GB-month after 10 GB. Card-required-at-signup NEEDS VERIFICATION. Not adopted for v0.1 regardless (ADR-035). |

**General rule**: for the demo, prefer providers that DO NOT require a credit card AND auto-cap at zero overage. R2, Vercel Hobby, CF Tunnel, Fly.io, and Render Free all satisfy this. Oracle Always Free requires a card at signup but explicitly does not charge Always-Free resources.

---

## 8. The 8-question gate, applied to the proposal as a whole

Verbatim 8 questions from `.cursor/rules/nucleus.mdc` lines 104-115. "A 'no' or 'unclear' anywhere → reject or defer."

| # | Question | Verdict | Reasoning + citation |
|---|---|---|---|
| 1 | Maps to one of five layers (`§3`)? | **FAIL** as architecture / **N/A** as demo deployment | A 9-vendor stitched stack is not architecture — it's deployment. As architecture, conflicts with L1/L2/L4. As demo deployment, only L0 Physics is touched. |
| 2 | Serves <30 min beachhead (`§1.5`)? | **FAIL** | Beachhead is CLI-only `git clone → first Iceberg table`. No proposal element affects that local-laptop path. Demo hosting is downstream of the beachhead. |
| 3 | Wrap possible instead of build? | **PASS** (adoptable items) | Oracle Ampere/R2/CF Tunnel = wrap. No new Nucleus code. |
| 4 | Preserves no-JVM (`§3` HC#1)? | **FAIL** (Zeppelin) / **PASS** (others) | Zeppelin runs on JVM. Oracle VM runs our Python image. R2 opaque S3. CF Tunnel is Go. |
| 5 | Local-identical-to-prod (`§11.3`)? | **PARTIAL** | R2 adoption preserves parity (local SeaweedFS/MinIO same code path). Supabase-as-warehouse breaks parity (no filesystem equivalent). |
| 6 | Stays in 30K LOC budget? | **PASS** | No new proprietary code. Config-only. |
| 7 | Triggered by empirical telemetry? | **UNCLEAR** | Predates PoC #5 external-tester signal. Adoption should wait for empirical demo-cost telemetry. Fly free tier has not been measured under load. |
| 8 | Required for v0.1 (`§18.1`)? | **FAIL** | v0.1 is `git clone → CLI → first Iceberg table`. Public demo is v0.2 marketing surface, not v0.1 critical path. |

**Aggregate**: 3 PASS / 3 FAIL / 2 UNCLEAR. **The proposal as a whole fails the gate.** Specific adoptable substrate (R2, CF Tunnel, optional Oracle Ampere) passes individually when scoped to the demo, not as v0.1 architecture — see §6.

---

## 9. Gap analysis vs `docs/release/public_demo_deploy_plan.md`

The existing plan (shipped 2026-05-15) is broadly aligned with the founder's intent. Reconciliation:

| Topic | Founder proposal | Deploy plan status | Action |
|---|---|---|---|
| Compute host | Oracle Ampere A1 | Fly `shared-cpu-1x@512mb` (§3) | REC-1: Document Oracle as Plan B in §3 |
| Frontend | Vercel / CF Pages | `deploy/vercel.json` + §3 Option B + §8 CF Pages | REC-5 (ToS gate) only |
| CDN/DNS/WAF | Cloudflare | §5/§6/§8 already use Cloudflare | NO divergence |
| Storage | R2 / Oracle Obj | Seed warehouse baked into image | REC-1: R2 variant |
| HTTPS edge | Cloudflare Tunnel | Fly anycast IP + CF DNS proxy | REC-4: Tunnel as hardening |
| Notebook surface | JupyterLab / Zeppelin | v0.1 has no notebook; v0.3+ Marimo | Reject (§4) |
| Identity/auth | (Implied none) | NG4 anonymous + HC#6 OIDC for prod | NO divergence |
| Cost cap | "no AWS/GCP/Azure" | §7 layered Fly caps | NO divergence |
| Vendor count | 9 vendors | 3 (Fly + CF + Vercel) + optional Sentry/UptimeRobot | Deploy plan = lower operational cost, faster launch |

**Single most material divergence**: founder proposal uses **9 vendors**; deploy plan uses **3**. Each additional vendor = one more dashboard, credential, ToS to re-read on any pivot. Anti-Over-Engineering Discipline (`nucleus.mdc` line 169) sides with the deploy plan.

---

## 10. Cross-reference cleanup (files to update IF founder ratifies)

NO files touched by this pass. The list below fires only on ratification.

- `public_demo_deploy_plan.md` — §3 Option D (Oracle Ampere Plan B) + §4 R2-backed variant + §5 CF Tunnel hardening + §8 Vercel ToS note (RECs 1, 4, 5)
- `v0.2_FOUNDER_CLOSE_CHECKLIST.md` — ToS-read item under Section 4 (REC 5)
- `docs/FOUNDER_ACTION_QUEUE.md` — informational link to this doc (end-of-day batch)
- `nucleus_architecture_v4.1.md` — **NO change** (REC 8 — operational, not architectural)
- `docs/decisions/ADR-040-cloud-preview-free-tier-substrate.md` — NEW (deferred per REC 7, after PoC #5 signal)
- `docs/compatibility.md` — NO change (no new pin)

---

## 11. NEEDS VERIFICATION (per AGENTS.md §11.12)

Count: 5.

1. **Koyeb permanent always-on free Micro VM tier** — "Koyeb Micro-VMs (no sleep)" not visible on https://www.koyeb.com/pricing on 2026-05-15. Pro starts at $29/mo + compute. Founder may reference deprecated tier OR a separate signup flow not on pricing page. Verify in dashboard before any deploy plan mentions Koyeb.
2. **MongoDB Atlas M0 inactivity pause window** — pricing page does not state. Check https://www.mongodb.com/docs/atlas/billing/free-shared-clusters/. Not adopted (§4).
3. **MotherDuck Lite credit-card-required-at-signup** — pricing page silent. Verify by inspecting https://app.motherduck.com/ signup flow. Affects auto-bill assessment in §7.
4. **`cloudflared` daemon RAM footprint** — used ~50-100 MB estimate without citation. Verify at https://github.com/cloudflare/cloudflared/releases. Affects 512 MB Fly machine budget.
5. **Fly.io `http_service` disabling when CF Tunnel adopted** — does `cloudflared` egress conflict with Fly auto-proxy on port 8080? Verify at https://fly.io/docs/networking/services/. Affects RECOMMENDATION 4 feasibility.

---

## 12. References (verified 2026-05-15)

**External (founder's proposed services)**:
- Oracle Always Free: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/
- Supabase pricing: https://supabase.com/pricing
- Vercel pricing + ToS: https://vercel.com/pricing  ·  https://vercel.com/legal/terms
- MongoDB Atlas pricing: https://www.mongodb.com/pricing
- Render pricing: https://render.com/pricing
- Koyeb pricing: https://www.koyeb.com/pricing
- MotherDuck pricing: https://motherduck.com/pricing/

**Internal Nucleus documents**:
- `AGENTS.md` §0, §3, §4, §7, §8, §11.12
- `.cursor/rules/nucleus.mdc` Tier table; 8-Question Gate; Anti-Over-Engineering
- `nucleus_architecture_v4.1.md` §1.5, §1.6, §2.1, §3, §4.1, §4.2, §5.5.1, §5.7, §5.8, §6.1, §10, §11.2, §11.3, §17.1, §18.1, §20.1
- ADRs: 002 §8.1, 004, 007, 008, 035
- `docs/research/marimo.md`, `docs/research/s3_duckdb.md`
- `docs/release/public_demo_deploy_plan.md`, `docs/release/v0.2_FOUNDER_CLOSE_CHECKLIST.md`
- `deploy/fly.toml`, `deploy/vercel.json`, `deploy/render.yaml`

---

## 13. Methodology

**Model**: Claude Opus 4.7 (research-tier fallback per AGENTS.md §11.14; Gemini 3.1 Pro unavailable in runtime). **Tool calls**: 11 WebFetch operations 2026-05-15. **Logged hallucinations**: none caught (no code-level APIs proposed).

---

*End of evaluation. No file modified by this pass. Founder ratifies recommendations 1-8 individually.*
