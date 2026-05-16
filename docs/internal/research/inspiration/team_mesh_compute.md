# Team Mesh Compute — Feasibility, Prior Art, and Nucleus Fit (2026)

> **Last verified**: 2026-05-15 against official docs, PyPI, and 2024–2026 case studies  
> **Research tier**: AGENTS.md §11.14 — Research tier (model: Claude Sonnet 4.6, fallback per availability)  
> **Audience**: Nucleus founder — strategic exploration; input to ADR-track or shelf decision  
> **Related docs**: `distributed_compute_2026.md` (R6, DO NOT REPEAT — Ray/Modal/Dask landscape); `docs/specs/nucleus_architecture_v4.1.md` §10 (Yield-to-Giants Modes 1/2/3); AGENTS.md §3 (Hard Constraints), §6 (Five Pillars)

---

## Executive Summary

**Verdict: DEFER-TO-v1.5 — conditional on ≥3 explicit customer interviews requesting it.**

The "team mesh compute" concept — pooling 5-engineer team laptops (80–160 GB aggregate RAM, 40–80 cores) into a shared compute tier between single-laptop v0.1 and cloud-giant Mode 2 — is technically feasible via existing OSS (Ray + Tailscale + Daft). It should NOT be built in v0.1–v1.0. Three reasons:

1. **The dominant failure mode is unsolvable today**: laptop sleep/wake causes Ray/Dask worker death (~25 s detection) with no automatic resume, making in-flight Iceberg materializations fail mid-commit.
2. **Home internet is the bottleneck, not compute**: Median US upload speed is **12–47 Mbps** real-world, meaning a 10 GB Parquet shuffle across home-network laptops takes 27–133 minutes — slower than reading from MinIO.
3. **The alternative is obviously better**: A Hetzner EX44 dedicated server (64 GB RAM, Intel i5-13500) costs **~€44/month** with 99.9% uptime. Accounting for maintenance burden, the laptop mesh has **negative ROI** vs this alternative for most startup teams.

No 2024–2026 data engineering tool — Databricks, Snowflake, MotherDuck, dbt Cloud, Coiled, Anyscale — has shipped a team mesh mode. This is strong signal that demand has not crystallized.

### Top-3 Actions

1. **Add to `docs/FOUNDER_ACTION_QUEUE.md`**: "Team Mesh Compute — revisit at v1.0 if ≥3 customer interviews request laptop-pooling AND they're explicitly frustrated by Mode 2 cost AND unwilling to buy a shared server."
2. **Reserve `compute="mesh"` as a keyword stub** in `docs/specs/nucleus_cli_spec.md` — return a `NucleusError` with a roadmap link. 0 LOC implementation cost; keeps API surface open.
3. **Watch MotherDuck multi-player roadmap** — if they ship peer-to-peer DuckDB collaboration, that validates demand. Set 6-month review.

---

## § 1. Prior Art Deep Dive

### 1.1 Summary Table

| # | Project | Category | Mesh relevance | Production-ready for laptop mesh? | Source |
|---|---|---|---|---|---|
| 1 | **Ray 2.55.x** | Distributed Python runtime | Head+worker pattern; ~25 s node death detection; 2–3 GB/s object store bottleneck on 10 Gbps NICs | **NO** — not designed for ephemeral workers | [docs.ray.io/en/latest/ray-core/fault-tolerance](https://docs.ray.io/en/latest/ray-core/fault-tolerance.html) |
| 2 | **Dask Distributed 2026.x** | Parallel Pandas/NumPy | Scheduler+worker; disconnect = worker death (no reconnect); no scheduler state persistence | **NO** — sleep triggers worker close | [distributed.dask.org/en/latest/resilience](https://distributed.dask.org/en/latest/resilience.html) |
| 3 | **Apache Beam portable runner** | Unified batch/stream | gRPC portable; Flink embedded runner works locally | **REJECTED** — Flink embedded needs JVM; violates HC#1 | [beam.apache.org/roadmap/portability](https://beam.apache.org/roadmap/portability/) |
| 4 | **BOINC / Folding@home** | Volunteer computing | Job replication, quorum validation, heartbeats, work stealing — canonical patterns for unreliable workers | **YES** (patterns only, not a data tool) | [boinc.berkeley.edu/boinc_papers/hicss_08](https://boinc.berkeley.edu/boinc_papers/hicss_08/hicss_08.pdf) |
| 5 | **MotherDuck dual execution** | Hybrid local/cloud DuckDB | Routes queries between local DuckDB and cloud "Ducklings" based on data location; `MD_RUN=LOCAL/REMOTE/AUTO` | **YES** — but local↔cloud only, NOT laptop↔laptop | [motherduck.com/docs/architecture-and-capabilities](https://motherduck.com/docs/architecture-and-capabilities) |
| 6 | **Tailscale Tailnet** | Mesh VPN (WireGuard) | Direct encrypted tunnels; ~800–860 Mbps direct; MagicDNS for discovery; OIDC device enrollment | **YES** (network layer) | [tailscale.com/kb/1320/performance-best-practices](https://tailscale.com/kb/1320/performance-best-practices) |
| 7 | **Modal** | Serverless ephemeral compute | <4 s cold start; per-second billing; NOT laptop-based — alternative "escape hatch" pattern | **N/A** — different category | [modal.com/docs](https://modal.com/docs/) |
| 8 | **Anyscale (managed Ray)** | Managed Ray clusters | Cloud-only; autoscaling by instance type groups; no BYO-laptop story | **NO** — cloud VMs only | [docs.anyscale.com/configuration/compute](https://docs.anyscale.com/configuration/compute/) |
| 9 | **NATS JetStream** | Message queue | Persistent work queue, at-least-once delivery, dead-letter queues; Go-native, <40 MB binary | **YES** (coordination backbone candidate if mesh is ever built) | [docs.nats.io/nats-concepts/jetstream](https://docs.nats.io/nats-concepts/jetstream) |
| 10 | **Automerge 3.0 / Yjs** | CRDT offline sync | Merge-without-conflict; offline-first; production at Evernote, GitBook | **PARTIAL** — relevant for mesh coordinator metadata only | [automerge.org](https://automerge.org/) / [docs.yjs.dev](https://docs.yjs.dev/) |
| 11 | **Daft + Ray runner** | Distributed DataFrame | `daft.set_runner_ray(...)` — one-line switch; Flotilla engine 18× faster than Spark on multimodal | **YES** (but Ray overhead ~200–400 MB idle RAM) | [docs.daft.ai/en/stable/distributed](https://docs.daft.ai/en/stable/distributed) |
| 12 | **llama.cpp RPC** | LLM inference splitting | Splits model across 2 MacBooks over LAN; 2025 community pattern | **NO** — inference only, not ETL | [sharedllm.org/blog/llama-cpp-rpc-two-macs](https://sharedllm.org/blog/llama-cpp-rpc-two-macs.html) |

### 1.2 Ray on Heterogeneous Laptops

**Head node = single point of failure**: Ray's GCS runs on the head node. If the head laptop sleeps, the entire cluster dies. Worker node death is detected after **~25 seconds** (5 health checks × 3 s + 10 s timeout) [docs.ray.io/en/latest/ray-core/fault_tolerance/nodes.html]. In-flight objects on the dead worker are lost — no automatic reconstruction without explicit configuration.

**Production workaround** (multi-Mac cluster operators): periodic dummy traffic every 10 minutes prevents GCS channel timeouts causing HTTP 408 errors after >3 hours idle [github.com/ray-project/ray/issues/59327]. This is ongoing maintenance Nucleus should not own.

**Data transfer bottleneck**: Ray's object store achieves only **2–3 GB/s aggregate on 10 Gbps NICs** [github.com/ray-project/ray/issues/42632]. Over home internet (12–47 Mbps upload), any dataset >1 GB is slower to shuffle than to re-read from S3/MinIO on a single laptop.

**Locality scheduling** was disabled by default in early 2024 [issue #40607] — CPU nodes idled while GPU nodes overloaded on heterogeneous clusters, which is exactly the pattern a mixed MacBook Pro/Air team would exhibit.

**Issues to watch**: #54332 (transient network tolerance) and #59327 (long idle recovery). PoC gated on both being RESOLVED.

### 1.3 Dask Distributed on Laptops

A 2025 blog post demonstrates a working Dask laptop cluster [thejeshgn.com, 2025-12-25] but requires Docker for dependency consistency, manual scheduler IP config, and strict version pinning — fragile across 5 laptops with different OS update cadences.

**Disconnect behavior**: `distributed.comm.timeouts.tcp` (default 30 s) determines whether a disconnect is "noticed." Laptop sleep causes an extended hard disconnect — Dask marks the worker dead and **reroutes pending computations** to surviving workers. Critical caveat: `scatter()`-ed data is **unrecoverable** from a dead worker [distributed.dask.org/en/latest/resilience.html]. There is **no scheduler state persistence** — if the scheduler laptop sleeps, all ongoing work is lost [github.com/dask/distributed/issues/6386].

### 1.4 BOINC Patterns — Relevant Design References

BOINC (Berkeley Open Infrastructure for Network Computing) is the canonical production system for unreliable, heterogeneous volunteer workers since 1999 [boinc.berkeley.edu/boinc_papers/hicss_08/hicss_08.pdf]. Patterns worth extracting (not copying — BOINC is not a data tool):

1. **Job replication**: N-way redundant task submission; quorum determines canonical result. Works for deterministic SQL transforms; fails for non-deterministic Python assets (randomness, timestamps).
2. **Heartbeats every 60–300 s**: Missing 5 consecutive → task reassigned to another worker.
3. **Checkpoint/resume**: Implementing for arbitrary Python asset functions requires either pure/deterministic functions or a custom serialization framework (~2,000+ LOC).
4. **Work stealing**: Tasks split into checkpoint-able units; preempted workers' units redistributed.

### 1.5 MotherDuck — Closest Commercial Analog

MotherDuck's dual execution model [cidrdb.org/cidr2024/papers/p46-atwal.pdf] routes SQL operators between local DuckDB and cloud-managed "Ducklings" based on data location. `MD_RUN=AUTO` sends remote S3/GCS data to cloud; local file data stays local. "Bridge" operators handle cross-environment data movement.

**What MotherDuck does NOT do**: route queries to a peer engineer's laptop. The cloud side is MotherDuck's managed fleet — not peer-to-peer. As of 2026-05-15, no multi-player laptop-to-laptop mode has shipped or been announced. If MotherDuck ships this, it validates the demand signal for Nucleus.

### 1.6 Tailscale as Network Backbone

Tailscale creates WireGuard-based encrypted tunnels between devices using a coordination server for key exchange (OIDC/OAuth2 enrollment, satisfies HC#6) with peer-to-peer data paths.

**Performance** [tailscale.com/kb/1320/performance-best-practices + tailscale.com/blog/more-throughput]:
- Direct connection (same LAN): ~800–860 Mbps; up to 10+ Gbps on bare-metal Linux
- Cross-ISP (home internet): limited by the **slowest upload link in the chain** — median US upload 12–47 Mbps. Tailscale is NOT the bottleneck; home ISP upload is.
- DERP relay fallback (when direct tunnel fails): ~10–50 Mbps with latency increase

MagicDNS provides stable hostnames (`alice-mbp.tailnet.ts.net`) — the service discovery layer that would let Ray/Dask workers find each other without static IPs.

**Limitation**: Kubernetes Operator (GA April 2025) does not support headless services [github.com/tailscale/tailscale/issues/14587] — relevant if mesh is orchestrated via K8s.

### 1.7 Have Any 2024–2026 Data Tools Shipped "Team Mesh"?

**No.** Comprehensive search across DuckDB, Polars, dlt, Dagster, dbt, Prefect, Bauplan, MotherDuck, Rill, Evidence.dev, Hex, Coiled, Anyscale found **zero products** shipping a "team mesh compute" mode where individual engineer laptops contribute to a shared data compute pool.

Adjacent 2025 patterns found:
- 200 Mac mini LLM inference cluster (purpose-built, always-on, $200k) — not "use your existing laptop"
- Dell XPS laptop hobby cluster — acknowledged "not cost-competitive with cloud" [olliefritz.com]
- llama.cpp RPC two-MacBook model splitting — inference only, not ETL

**Signal interpretation**: Either demand hasn't crystallized (likely), or engineering challenges are understood to be severe enough that no product team has committed (also likely). Both interpretations support DEFER.

---

## § 2. Failure Modes — Risk Matrix

P = Probability, I = Impact; scale: LOW / MED / HIGH / CRITICAL

| # | Failure Mode | P | I | Nucleus impact | Mitigation | Residual |
|---|---|---|---|---|---|---|
| **2.1** | Laptop sleep kills in-flight materialization | HIGH | HIGH | Dagster job fails mid-run; partial Iceberg snapshot, no commit | Checkpoint-able assets; task requeue on node death | HIGH |
| **2.2** | Head node (scheduler laptop) sleeps | HIGH | CRITICAL | Entire mesh cluster dies; no state persistence | Dedicate always-on node — defeats "zero extra HW" premise | CRITICAL |
| **2.3** | Home internet upload bottleneck | HIGH | HIGH | 10 GB Parquet shuffle at 12–47 Mbps = 27–133 min transfer | Same-LAN office requirement — breaks remote-first teams | HIGH |
| **2.4** | Tailscale DERP relay fallback | MED | HIGH | Throughput drops 10–50 Mbps; tasks 10–50× slower | Tailscale Peer Relay servers; pre-check direct tunnel | MED |
| **2.5** | 5 attack surfaces vs 1 cloud cluster | MED | CRITICAL | Lateral movement risk; corp IT blocks peer-to-peer | mTLS between nodes + Tailscale ACLs + device attestation | MED–HIGH |
| **2.6** | Data residency / inter-engineer ACLs | MED | HIGH | Laptop A reads Engineer B's in-progress Iceberg data | Route all data through shared S3/MinIO; laptops never cache sensitive data | MED |
| **2.7** | OS + Python version heterogeneity | HIGH | MED | Binary incompatibility across macOS + Windows | Docker or uv venvs with pinned versions (+5 min/worker setup) | MED |
| **2.8** | Corp IT blocks WireGuard UDP | HIGH | HIGH | Tailscale falls back to DERP; throughput makes mesh useless | No mitigation if corp blocks DERP too | HIGH |
| **2.9** | Concurrent Iceberg commits from two laptops | LOW | CRITICAL | Snapshot conflict; catalog corruption if no atomic commit | Filesystem catalog is single-writer; Lakekeeper (v0.3+) adds OCC | LOW |
| **2.10** | Uneven compute (fan-less laptop throttles) | MED | MED | M1 MacBook Air throttles under load; tasks 3× slower | Resource-aware scheduling (Ray CPU/memory requirements) | LOW–MED |

**The critical path problem (2.1 + 2.2)**: In practice, team members close laptops constantly. A mesh with N=5 workers where each has a 20% chance of sleeping at any moment means the scheduler cannot guarantee task completion within any bounded time window without duplicate execution and quorum (BOINC-style). Implementing that for Nucleus assets is a custom distributed systems project — not a wrap.

---

## § 3. Architectural Fit Analysis

### 3.1 Where Mesh Sits in v4.1

Current v4.1 (per `docs/specs/nucleus_architecture_v4.1.md` §10) defines 3 yield-to-giants modes:

```
Proposed extension to the compute tier (v4.1 §10, NOT today):

  compute=local      →  single-laptop DuckDB/Polars (v0.1 default)
  compute=mesh       →  [PROPOSED] team laptop Ray+Tailscale cluster
  compute=databricks →  Mode 2: Databricks cluster (yield to giants, v1.5+)
  compute=snowflake  →  Mode 2: Snowflake (yield to giants, v1.5+)
```

This adds a 4th tier: `local-first → team-mesh → yield-to-giants`. It does NOT contradict v4.1 §10 — it extends it. The question is whether this tier earns its LOC cost.

### 3.2 Pure-Wrap Feasibility

**Theoretical thin wrapper** (no new Nucleus scheduling logic):

```python
# nucleus.toml
[mesh]
tailscale_tailnet = "my-team.ts.net"
ray_head = "alice-mbp.tail.ts.net:6379"

@nucleus.asset(compute="mesh")
def fct_monthly_sales(ctx):
    return ctx.sql("SELECT month, SUM(amount) FROM raw_events GROUP BY 1")

# Internal dispatch (simplified)
def _dispatch_mesh(asset_fn, ctx):
    import daft
    daft.set_runner_ray(address="ray://alice-mbp.tail.ts.net:10001")
    return asset_fn(ctx)
```

**What this thin wrap CANNOT solve**: cluster provisioning (users must manually run `ray start --head`); worker registration (each engineer runs `ray start --address=...`); Tailscale node auto-discovery; head node HA without Redis; mTLS between Ray nodes [NEEDS VERIFICATION — docs.ray.io/en/latest/ray-core/configure.html]. Each gap requires new Nucleus coordinator code.

### 3.3 LOC Estimate

| Implementation scope | LOC | Notes |
|---|---|---|
| Thin PoC (manual user setup, no auto-discovery, no fault handling) | 300–500 | Just `compute="mesh"` → Ray+Daft dispatch |
| Semi-automated (`nucleus mesh join` + `nucleus mesh status` CLI) | 1,000–1,500 | Tailscale discovery, health check, retry |
| Production-grade (cluster lifecycle, checkpoint/resume, security, ACLs) | 3,000–5,000 | Essentially a custom distributed job coordinator |

**LOC budget check** (AGENTS.md §11.6): v0.1 target ~8,000 LOC total. Even the thin PoC (300–500 LOC) consumes 4–6% of v0.1 budget on zero-demand features. Production-grade (5,000 LOC) = 17% of the v1.0 LOC ceiling — an unreasonable spend on unvalidated demand.

### 3.4 Constraint Scorecard

| Constraint | Status | Notes |
|---|---|---|
| HC#1: No JVM | ✅ PASS | Ray/Tailscale/Daft = Python/Go only — as long as Beam is excluded |
| HC#3: No custom scheduler | ⚠️ BORDERLINE | Ray IS the scheduler; cluster lifecycle = new scheduling logic |
| HC#4: No custom compute engine | ✅ PASS | We wrap Ray/Daft |
| HC#8: ≤30K LOC by v1.0 | ⚠️ PRESSURED | 17% of ceiling on production impl |
| HC#9: Composability by constitution | ⚠️ REQUIRES DESIGN | Ray swap interface (Dask backend?) needed |
| Pillar #1: High perf on minimal resources | ✅ PASS | More resources when available |
| Pillar #2: Composable | ⚠️ DESIGN REQUIRED | Ray is Tier 1 |
| Pillar #5: Friendly to giants | ✅ PASS | Mesh is pre-yield, not instead-of-yield |
| Beachhead: <30 min to first Iceberg table | ❌ NOT SERVED | Serves post-productivity workloads |

---

## § 4. Competitive Positioning

### 4.1 Competitor BYO-Laptop Story

| Platform | BYO laptop compute? | Closest analog | Notes |
|---|---|---|---|
| **Databricks** | NO | Databricks Connect: laptop → Databricks cluster, not laptop → laptop | Community question about laptop integration went unanswered [community.databricks.com #95172] |
| **Snowflake** | NO | Snowpark Container Services (your VPC, not your laptop) | |
| **MotherDuck** | NO | Local DuckDB ↔ MotherDuck cloud; peer-to-peer not implemented | [motherduck.com/docs/architecture-and-capabilities] |
| **dbt Cloud** | NO | No compute layer; orchestration only | |
| **Coiled** | NO | Managed Dask on your cloud account (BYOC ≠ BYO laptop) | |
| **Anyscale** | NO | Managed Ray on cloud VMs only | |
| **Prefect** | NO | Hybrid worker runs anywhere, but "anywhere" = always-on server | |

**Conclusion**: Zero competitors have shipped team mesh. Two interpretations: (A) untapped opportunity, or (B) demand doesn't exist at scale. §4.2 makes the case for B.

### 4.2 Why Has Nobody Done It?

The HN thread on dev environments [#42042999]: "I have seen several attempts to move dev environments to a remote host. They invariably suck." The same dynamic applies to shared laptop compute. HN discussions on Databricks costs [#43899252] show teams either accepting cloud costs or not needing distributed compute at all ("Databricks is great if your data is actually big"). The "team mesh" sweet spot — data too big for one laptop, team too cash-strapped for cloud — is genuinely narrow.

### 4.3 Could "Nucleus Pod" Be Newsworthy?

"5 engineers, 5 MacBooks, one `nucleus pod start`, run a 1 TB job that no single laptop could handle" is a compelling HN headline. However, HN-ability ≠ PMF. Build this only after the demo works reliably in daily use by at least one paying team — not before.

---

## § 5. Cost / Value Math

### 5.1 The Sunk Hardware

| Config | Total hardware cost |
|---|---|
| 5 × MacBook Pro M3 Pro (18 GB, 12-core) | ~$15,000 — already paid |
| 5 × MacBook Pro M3 Max (36 GB, 16-core) | ~$20,000 — already paid |
| Aggregate (all awake, same LAN) | 90–180 GB RAM; 60–80 cores |
| Aggregate (remote, home internet) | Same compute; **12–47 Mbps upload bottleneck** is the binding constraint |

### 5.2 Equivalent Cloud Compute Cost

**Databricks SQL Serverless** [NEEDS VERIFICATION: current DBU price — check databricks.com/product/pricing/product-pricing/instance-types]:
- Small SQL Warehouse: 12 DBU/hour at ~$0.22/DBU (standard tier) = ~$2.64/hour
- 5-engineer team, 2 hr/day × 22 workdays: **~$116/month**
- 4 hr/day active development: **~$232/month**

**Modal serverless** [modal.com/pricing, current 2026]:
- $0.0000131/core/sec = ~$0.047/core-hour; $0.00000222/GiB/sec
- 10 cores × 2 hr/day × 22 days = 220 core-hours/month → **~$10–20/month** for typical batch escapes

**Hetzner dedicated server** [radar.iodev.org, hetzner.com, 2025]:
- EX44 (Intel i5-13500, 64 GB RAM, 2×512 GB NVMe): **~€44/month** (~$47/month)
- CCX43 cloud (16 vCPU, 64 GB RAM, dedicated vCPU): **~€96.49/month** (~$103/month)

### 5.3 ROI Calculation for Laptop Mesh

Assuming mesh runs ~30% of cluster workload (the "team productivity" portion):

| Option | Monthly operational cost | Maintenance burden | Net |
|---|---|---|---|
| Databricks SQL (2 hr/day baseline) | $116 | LOW | $116 |
| **Laptop mesh** | **$0 operational** | ~5 engineer-hr/month × $100/hr = **$500** | **-$384 vs baseline** |
| **Hetzner EX44** | **$47** | ~0.5 hr/month | **$69 saved vs Databricks** |
| Modal (escape hatch per heavy job) | $15–20 | ~0.5 hr/month | **~$96 saved vs Databricks** |

**The laptop mesh has negative ROI vs the Hetzner alternative for most startup data teams.** The maintenance burden — Ray version pinning across 5 laptops with different OS update cadences, debugging sleep/wake failures, managing Tailscale ACL changes, troubleshooting Daft/Ray compatibility — easily consumes 5+ engineer-hours/month.

### 5.4 When Laptop Mesh Wins

The narrow edge case where mesh is genuinely better than Hetzner:
- Team is **co-located in the same office on a gigabit LAN** (eliminates upload bottleneck)
- **Laptops are plugged in and always-on** during work hours (eliminates sleep problem)
- Team **explicitly does NOT want a shared server** for policy/compliance reasons
- Workloads are **embarrassingly parallel** without cross-partition shuffle (avoids data transfer bottleneck)

This configuration describes a well-funded, office-first team — the exact team that can also afford a $47/month server. The corner case collapses under scrutiny.

### 5.5 Marketing vs Real Cost Win

**Marketing win: YES** — the demo is compelling. **Real cost win: NO** for most teams — negative ROI when maintenance is factored in. A feature that demos well but fails in daily use due to sleeping laptops generates negative word-of-mouth that is harder to recover from than a missing feature.

---

## § 6. Recommendation

### Verdict: **DEFER-TO-v1.5 — conditional on ≥3 explicit customer requests**

### 6.1 The 8-Question Gate Result

| # | Question | BUILD-NOW | DEFER-TO-v1.5 |
|---|---|---|---|
| Q1 | Maps to one of five architectural layers? | ✅ Layer 3 | ✅ Layer 3 |
| Q2 | Serves <30-min beachhead metric? | ❌ NO | ✅ Deferred to post-v1.0 |
| Q3 | Wrap possible instead of build? | ⚠️ PARTIAL | ✅ Monitor first |
| Q4 | Preserves no-JVM constraint? | ✅ YES (avoid Beam) | ✅ YES |
| Q5 | Preserves local-identical-to-prod? | ❌ NO — new runtime | ✅ Deferred |
| Q6 | Stays within 30K LOC budget? | ⚠️ PRESSURED | ✅ 0 LOC now |
| Q7 | Triggered by empirical telemetry? | ❌ NO customer requests | ✅ Monitor for 3+ requests |
| Q8 | Required for v0.1 Hello World? | ❌ NO — clearly v1.5+ | ✅ Correctly deferred |

**BUILD-NOW gate: 2/8 pass.** REJECTED by the gate.  
**DEFER-TO-v1.5 gate: 7/8 pass** (Q3 partial — no cost today). PASSES.

### 6.2 Phased Monitoring Plan

**Now (0 LOC)**:
- Reserve `compute="mesh"` keyword in `docs/specs/nucleus_cli_spec.md` — returns `NucleusError` with roadmap link
- Add to `docs/FOUNDER_ACTION_QUEUE.md`

**v1.0 trigger gate** — begin design ONLY when:
- [ ] 3+ distinct customer teams ask for team mesh by name in interviews or GitHub issues
- [ ] OR MotherDuck ships laptop-to-laptop multi-player mode
- [ ] OR Nucleus has >500 active users and >20% hit single-laptop memory limits

**v1.5 PoC** (if triggered) — build in `/poc/p6_team_mesh/`:
- Ray + Tailscale + Daft Ray backend; thin wrapper ~500 LOC
- Test ONLY: same-office LAN scenario
- Success criteria: 5-node cluster; 50 GB partition job; graceful fail when 1 worker sleeps
- Block: Ray issues #54332 and #59327 must be RESOLVED first

**v2.0 production** (if PoC validates) — promote; target ≤2,000 LOC total.

### 6.3 What Would Change the Verdict to REJECT

- 3+ enterprise security teams explicitly prohibit peer-to-peer laptop traffic in security policy
- MotherDuck validates this and shows < 5% adoption even among their co-located-office users
- Ray's Tailscale integration remains brittle through 2026

### 6.4 Anti-Pattern Call-Out

Per AGENTS.md §10.8 and the Anti-Over-Engineering directive: "Speculative code. 'v0.5 might need X' is not a justification; it is anxiety."

As of 2026-05-15, team mesh compute has: zero documented customer requests, negative ROI vs Hetzner alternative, severe unmitigated failure modes (sleep, network, security), and zero competitor validation. Building it now is the definition of an anxiety feature.

---

## § 7. Adjacent Design Notes (for future PoC team)

**NATS JetStream as coordinator** [docs.nats.io/nats-concepts/jetstream]: If mesh is ever built, NATS JetStream (Go-native, <40 MB binary, sub-ms pub/sub) is a better coordination backbone than extending Dagster for the mesh tier. NATS Work Queues with heartbeat pattern directly mirrors the BOINC architecture — a proven model for unreliable workers.

**CRDTs for mesh availability metadata** [automerge.org/blog/automerge-3]: Automerge 3.0 (10× memory reduction via runtime compression) could sync "which laptop has which Iceberg partition cached" without a central coordinator. NOTE: this is for coordination metadata ONLY — Iceberg itself already handles data catalog via S3/MinIO listing.

**Ray issue watch list**: Issue #54332 (transient network tolerance) and #59327 (long idle recovery) are the two issues whose RESOLVED status gates v1.5 PoC consideration.

**Apache Beam note**: Never use Beam for this use case — Flink embedded runner requires JVM (HC#1). This door is permanently closed.

---

## § 8. NEEDS VERIFICATION

1. **Ray mTLS current config** — Ray supports TLS between nodes; exact current API for laptop clusters unconfirmed. Check: https://docs.ray.io/en/latest/ray-core/configure.html#tls-authentication
2. **Databricks SQL DBU price (2026)** — $0.22/DBU estimate from 2024; verify current rate at https://www.databricks.com/product/pricing/product-pricing/instance-types
3. **MotherDuck multi-player roadmap** — No public roadmap document found confirming or denying. Check: https://motherduck.com/blog for 2026 posts.
4. **Daft Ray runner idle RAM overhead** — Separate from Ray's ~200–400 MB; Daft-specific overhead not measured. Check: https://docs.daft.ai/en/stable/distributed
5. **Tailscale Team plan device limit** — 100 devices on Personal/free; Team plan limits for 5-engineer startup unconfirmed. Check: https://tailscale.com/pricing

---

## § 9. References

**Ray**: [1] fault-tolerance.html [2] fault_tolerance/nodes.html [3] issue #59327 (long idle) [4] issue #42632 (object store) [5] issue #40607 (locality scheduling) [6] issue #54332 (transient network) — all at `docs.ray.io/en/latest/ray-core/` or `github.com/ray-project/ray/issues/`

**Dask**: [7] distributed.dask.org/en/latest/resilience.html [8] github.com/dask/distributed/issues/6386 [9] thejeshgn.com/2025/12/25/turning-my-laptops-into-a-dask-distributed-cluster/

**Beam**: [10] beam.apache.org/roadmap/portability/

**BOINC**: [11] boinc.berkeley.edu/boinc_papers/hicss_08/hicss_08.pdf [12] github.com/BOINC/boinc/wiki/JobReplication

**MotherDuck**: [13] motherduck.com/docs/sql-reference/motherduck-sql-reference/md-run-parameter/ [14] motherduck.com/docs/architecture-and-capabilities [15] cidrdb.org/cidr2024/papers/p46-atwal.pdf

**Tailscale**: [16] tailscale.com/kb/1320/performance-best-practices [17] tailscale.com/blog/more-throughput [18] github.com/tailscale/tailscale/issues/14587

**Modal**: [19] modal.com/docs/ + modal.com/pricing — **Anyscale**: [20] docs.anyscale.com/configuration/compute/ — **NATS**: [21] docs.nats.io/nats-concepts/jetstream

**CRDTs**: [22] automerge.org/blog/automerge-3 [23] docs.yjs.dev/

**Daft**: [24] docs.daft.ai/en/stable/distributed [25] daft.ai/blog/introducing-flotilla-simplifying-multimodal-data-processing-at-scale

**Cost sources**: [26] radar.iodev.org/ + hetzner.com/cloud/general-purpose [27] databricks.com/product/pricing/databricks-sql [28] statista.com/statistics/1488725/fixed-internet-upload-speeds-by-provider-united-states/ [29] leandataengineer.com/blog/stop-paying-for-distributed-frameworks-you-don-t-need/

**Community signals**: [30] HN #42042999 (dev environments) [31] HN #43899252 (Databricks cost) [32] community.databricks.com #95172 (laptop + Databricks question) [33] contracollective.com/blog/apple-silicon-local-ai-server-engineering-team [34] sharedllm.org/blog/llama-cpp-rpc-two-macs/ [35] olliefritz.com/writing/xps-laptop-cluster.html

**Internal**: [36] docs/specs/nucleus_architecture_v4.1.md §10 [37] AGENTS.md §3/§5/§6/§10/§11

---

*Research model: Claude Sonnet 4.6 (fallback per AGENTS.md §11.14; Gemini 3.1 Pro preferred, unavailable in current runtime).*  
*Verified: 2026-05-15. Re-verify before acting if reading after 2026-11-15.*
