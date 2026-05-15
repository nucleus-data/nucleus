# Nucleus v0.2.0 — WOW Moments Inventory

> *The 5-7 most compelling demos / numbers / artifacts that should be front-and-center on launch day. For each: what it is, where it lives, why it lands. Numbers are empirical (cited paths); claims that are aspirational are explicitly marked. Vocabulary per [`AGENTS.md`](../../../AGENTS.md) §7; forbidden framings per §8. Last updated 2026-05-15.*
>
> **Honesty contract** ([`AGENTS.md`](../../../AGENTS.md) §10.8): every number here is reproducible from a path on disk. No marketing-massaged figures. When a number disagrees with an aspirational target in [`docs/research/performance_reliability_targets.md`](../../research/performance_reliability_targets.md), the **measured number wins** and the target is documented as "v0.3 goal" rather than "v0.2 claim".

---

## Top 7 wow moments (priority-ordered)

### 1. The 30-minute beachhead claim — empirically validated

**What**: A 5-engineer team goes from `git clone` to a **BI-ready Iceberg table** in **<30 minutes**, on a laptop, no cluster, no JVM. Validated by the WSL beachhead E2E.

**Why it lands**: This is the entire product thesis in one number. Every competing tool requires either (a) a cluster, (b) a hosted account, or (c) a configured warehouse before minute zero. Nucleus's <30 min is a step-function delta — and we ship the script that proves it.

**Backing artifact**:

- [`scripts/beachhead_e2e.py`](../../../scripts/beachhead_e2e.py) — the 8-gate script. 8/8 PASS on WSL Linux 2026-05-14.
- [`docs/release/e2e_results_20260514T190132.md`](../e2e_results_20260514T190132.md) — last full E2E run output.
- [`docs/benchmarks/2026-05-15_baseline.md`](../../benchmarks/2026-05-15_baseline.md) §B5 — boot time **2.06s** warm-median console invocation (measured on a 4-core Windows host with 1 GB free RAM — the worst-case for boot, and still under 10 s).
- [`nucleus_architecture_v4.1.md`](../../../nucleus_architecture_v4.1.md) §1.5 — the beachhead persona definition.

**Asset gap**: a 1-screenshot timer overlay showing E2E elapsed time would help on HN comment threads. **Surface to parent**: should we record a screenshot of the E2E script's final summary line for the launch-kit `assets/` folder? (~5 min effort.)

---

### 2. 60-second screencast (script + recording)

**What**: One terminal, one browser tab, **six scenes**: `install → init → up → ingest → query → Workbench`. Total runtime 60 s, no jump cuts, voiceover separate-track. Embeds the "see for yourself" wow into the first paragraph of the README + the docs landing page.

**Why it lands**: Hacker News skims first, reads second, plays video third. The video answers "is this real?" before the skeptic reads the first sentence of the comparison table.

**Backing artifact**:

- Script: [`docs/release/launch_kit/60_SECOND_DEMO_SCRIPT.md`](60_SECOND_DEMO_SCRIPT.md) (shot-by-shot, 11.3 KB, retake checklist included).
- Distribution targets per §Distribution of the script: README hero, docs site index, LinkedIn post, Twitter thread tweet 1, dev.to article opening.

**Asset gap**: the **recording itself** is not yet produced. Path target: `assets/demos/v0.2/launch_60s.mp4` + `assets/demos/v0.2/launch_60s.srt` (per script §Distribution). **Surface to parent**: founder gates this; ~10 min recording + retakes per [`docs/release/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md`](../FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md) Phase 0.

---

### 3. Wrapped-engines architecture diagram

**What**: Five-layer architecture (Physics → Engines → Coordination → Intelligence → Experience) with explicit boxes for **wrapped** OSS components (DuckDB, Polars, pyiceberg, Dagster, OpenLineage, Arrow). The diagram visually proves the "wrap, not build" principle that frames our 30K LOC ceiling.

**Why it lands**: It answers "what are you NOT building?" before a reader asks. Most data-platform pitches obscure dependencies; we showcase them. The diagram also serves as proof of the **Composability by Constitution** (`AGENTS.md` §3 Constraint #9) — every wrapped Tier 1/2 dep has a swap interface stub committed.

**Backing artifact**:

- Architecture spec: [`nucleus_architecture_v4.1.md`](../../../nucleus_architecture_v4.1.md) §3 (the 5-layer model) + §4 (wrap table) + §9 (composability constitution).
- Existing diagrams (text-form): [`docs/site/concepts/`](../../site/concepts/) and the layer enumeration in [`docs/roadmap/HANDOVER.md`](../../roadmap/HANDOVER.md) §"Five-Layer Architecture at a Glance".

**Asset gap**: no **rendered SVG/PNG diagram** of the 5-layer model with wrapped engines highlighted lives in `assets/`. **Surface to parent**: a mermaid or excalidraw diagram saved to `assets/architecture/v4.1_five_layers.svg` + `_dark.svg` would let the README + docs site + press kit all reference one source. ~30 min effort with mermaid.

---

### 4. Honest performance numbers — empirical, not marketing

**What**: The empirical benchmark baseline shows **11 measured failures vs aspirational targets** — and we publish all 11 in the launch material **before** anyone asks. Specifically:

- Boot: **2.06 s warm** median console invocation (target was <500 ms — target demoted to v0.3 goal).
- Materialize 1 GB / 10M rows: **38.77 s** wall-clock.
- Concurrent run safety on Windows: **B4 FAILS** (NTFS `msvcrt.locking` semantics differ from POSIX `fcntl.flock`); **Linux / WSL PASS**.
- Idle RAM: ~117 MB (`nucleus up` resident).

**Why it lands**: Skeptical readers (especially senior engineers on HN) reject "blazing fast" marketing on sight. Publishing the **measured** numbers with the **measurement script** is the trust play. It also makes the v0.3 roadmap concrete: we know exactly which 11 things to fix.

**Backing artifact**:

- [`docs/benchmarks/2026-05-15_baseline.md`](../../benchmarks/2026-05-15_baseline.md) — full empirical baseline.
- [`scripts/benchmarks/run_all.py`](../../../scripts/benchmarks/) — re-runnable.
- [`docs/release/v0.2.0_RELEASE_NOTES.md`](../v0.2.0_RELEASE_NOTES.md) §"Known issues" — the same disclosure in release-notes form.

**Honest disclaimer (per `AGENTS.md` §10.8)**: numbers were measured on a 4-core Windows host with 1 GB free RAM at run start, which is below the beachhead-persona target (8-12 cores, 16-32 GB RAM). Re-measurement on beachhead-spec hardware is queued for v0.2.1 — but we publish the worst-case numbers first rather than the best-case.

---

### 5. "Graduate to Databricks with zero migration" — Mode 1 Iceberg portability

**What**: Nucleus writes **plain Apache Iceberg snapshots** to user-owned S3 (or local filesystem). When a team outgrows a laptop, they point Databricks Unity Catalog (or Snowflake Iceberg, or Apache Polaris, or Lakekeeper, or Cloudflare R2) at the **same bucket** with **zero migration** — same Parquet files, same Iceberg manifests, same snapshot IDs.

**Why it lands**: It directly addresses the #1 anxiety of any startup-team data engineer evaluating an OSS tool — "what's my exit if this project dies / I outgrow it / my CTO demands Databricks?" Most tools require export/import. Nucleus's exit is **a config-file edit**.

**Backing artifact**:

- [`nucleus_architecture_v4.1.md`](../../../nucleus_architecture_v4.1.md) §10.1 — Mode 1 graduation strategy.
- [`docs/site/guides/graduate-to-databricks.md`](../../site/guides/graduate-to-databricks.md) — user-facing recipe.
- [`docs/research/parity_vs_databricks_snowflake.md`](../../research/parity_vs_databricks_snowflake.md) — capability matrix (proves Nucleus does NOT compete on breadth).
- [`docs/release/launch_kit/comparison_vs_databricks_snowflake.md`](comparison_vs_databricks_snowflake.md) — the launch-kit comparison piece.

**Asset gap**: a short "graduate in 5 commands" sequence-diagram would be a strong sub-asset for LinkedIn / Twitter. **Surface to parent**: defer to post-launch — not blocking for v0.2.0.

---

### 6. "5 commands to first BI-ready Iceberg table" demo flow

**What**: The literal copy-paste sequence from a fresh shell to a queried Iceberg snapshot:

```bash
pip install nucleus
nucleus init my-stack && cd my-stack
nucleus up
nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders
nucleus query "SELECT count(*) FROM {{ ref('raw.orders') }}"
```

5 commands. ~7 s boot. Real Iceberg snapshot. Real DuckDB query against the snapshot via `{{ ref() }}` resolution. No setup wizard, no account creation, no API key.

**Why it lands**: It's the "you can paste this into your terminal **right now** and have a real Iceberg table in under a minute" headline that anchors every social post. It compresses the 30-minute claim into a 30-second demonstration.

**Backing artifact**:

- [`README.md`](../../../README.md) §30-second demo (current state — predates v0.2.0 launch; will be patched per [`README_HERO_PATCH.md`](README_HERO_PATCH.md)).
- [`docs/onboarding/quickstart.md`](../../onboarding/quickstart.md) — full 30-min walkthrough.
- [`docs/release/launch_kit/60_SECOND_DEMO_SCRIPT.md`](60_SECOND_DEMO_SCRIPT.md) §Scene 4 — the same flow as the video.

---

### 7. AI-Copilot-by-design, NOT AI-first — concrete NucleusError example <!-- banned-term: AI-first -->

**What**: Every external library exception (Dagster, DuckDB, Polars, pyiceberg, dlt, SQLAlchemy) is translated to a `NucleusError` subclass with a stable `NE####` code, a `docs_url`, and zero wrapped-library classnames in the user-facing string. CI enforces this via [`scripts/dagster_leak_check.py`](../../../scripts/dagster_leak_check.py). This is what "AI-ready by design" actually means — structured errors that **LLMs can parse**.

**Example**:

```
$ nucleus ingest sqlite:///./missing.db --table orders --as raw.orders
NE2003: source asset not reachable

  Catalog: filesystem (./data/warehouse)
  Source:  sqlite:///./missing.db
  Cause:   file does not exist at path ./missing.db

  Fix hint: verify the file path or use an absolute path.
  Docs:    https://nucleus.dev/errors/NE2003
```

vs. what an unwrapped tool would surface:

```
$ ...
Traceback (most recent call last):
  File ".../sqlalchemy/engine/create.py", line 524, in create_engine
    ...
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
```

**Why it lands**: Differentiates Nucleus from "AI-first" framings (which are forbidden per [`AGENTS.md`](../../../AGENTS.md) §8). The Copilot is a feature; the **error translation discipline** is the substrate that makes AI-assisted debugging actually useful. <!-- banned-term: AI-first -->

**Backing artifact**:

- [`docs/errors/`](../../errors/) — 16 NE-code reference pages.
- [`src/nucleus/coordination/error_translation.py`](../../../src/nucleus/coordination/error_translation.py) — the translator implementation.
- [`scripts/dagster_leak_check.py`](../../../scripts/dagster_leak_check.py) — CI enforcement (release-blocking).
- [`docs/decisions/ADR-006-nucleus-error-code-numbering.md`](../../decisions/ADR-006-nucleus-error-code-numbering.md) — the numbering scheme decision.

---

## Asset summary — what exists, what's a gap

| WOW | Backing artifacts present? | Asset gap | Priority |
|---|---|---|---|
| 1. 30-min beachhead claim | YES — E2E script + benchmark baseline + architecture §1.5 | Optional screenshot of E2E timer | LOW |
| 2. 60-sec screencast | YES — script (11.3 KB) | **MP4 recording + SRT** — founder-only, ~10 min | HIGH |
| 3. Wrapped-engines diagram | TEXT-only (architecture §3) | **Rendered SVG/PNG** for README + docs + press kit | MEDIUM |
| 4. Honest performance numbers | YES — full empirical baseline | (none) | — |
| 5. Graduate-to-Databricks story | YES — architecture §10.1 + comparison doc + recipe | Optional sequence diagram | LOW |
| 6. 5-command demo flow | YES — in README + quickstart + script | (none) | — |
| 7. NucleusError example | YES — error registry + ADR-006 + translator code | Optional GIF of the side-by-side | LOW |

**Critical-path gaps for launch day**: only WOW #2 (60-sec MP4 recording) is a real blocker — it's referenced from the README hero patch, LinkedIn post, Twitter thread tweet 1, and docs site landing. WOW #3 (rendered architecture diagram) is a strong "should ship" but the README + docs can launch with the text-form layer enumeration and add the SVG in v0.2.1.

---

## Five proposed README.md improvements (DO NOT modify README — surface to parent)

Subagent E already shipped [`README_HERO_PATCH.md`](README_HERO_PATCH.md) — a complete, founder-reviewable rewrite of README lines 10-80. The patch and the following audit notes are **complementary**: the patch is the proposed change, the audit is the reviewer's checklist.

### Improvement 1 — Above-the-fold WOW selection (HIGH priority)

**Current state**: the README hero opens with a 3-row "v0.1 beta — what works vs. what waits" comparison table on lines 24-32 — useful for honesty, but it signals "still cooking" before signaling "what this is for."

**Proposal**: per `README_HERO_PATCH.md` §1 ("Lead with the differentiator, not the disclaimer"), the **first scrolled view** should show the value-prop sentence + the 60-sec demo embed, **then** the install snippet, **then** the "what's not yet" block. Current order is inverted. The patch fixes this.

**Verification after patch lands**: scroll to the GitHub repo page on a 1080p monitor; the demo poster image should be visible without scrolling.

### Improvement 2 — Comparison table positioning (MEDIUM priority)

**Current state**: README §"Comparison (startup team lens — honest)" lives at lines 75-85, **after** the install snippet, **before** the long-form "What is Nucleus" section.

**Proposal**: replace the current 5-row dimension matrix with the **1-row persona matrix** from `README_HERO_PATCH.md` §"Honest 1-row comparison". The 5-row matrix invites the response "but you forgot column X"; the 1-row persona matrix is harder to argue with because it claims **persona fit**, not feature parity. Keep the full 5-row matrix in [`docs/release/launch_kit/comparison_vs_databricks_snowflake.md`](comparison_vs_databricks_snowflake.md).

**Verification**: after patch, the README has at most ONE comparison table; the long comparison is one click away via link.

### Improvement 3 — Install snippet clarity (HIGH priority)

**Current state**: lines 41-46 show `git clone https://github.com/nucleus-data/nucleus.git ... pip install -e ".[dev]"` as the **primary** install path, with a parenthetical "When publishing completes, `pip install nucleus` becomes the default path".

**Proposal**: invert the priority once the release workflow publishes v0.2.0 to PyPI — the README should lead with `pip install nucleus` (or `pip install "nucleus[postgres,workbench]"` for the full beachhead path). Before PyPI is green, the editable-dev workflow stays in [`CONTRIBUTING.md`](../../../CONTRIBUTING.md). **Per [`docs/decisions/ADR-039-install-size-split-extras.md`](../../decisions/ADR-039-install-size-split-extras.md)**, the lean core install is `pip install nucleus` (~16 deps); extras are opt-in.

**Verification**: after patch, the first `bash` block in the README contains `pip install nucleus`, not `git clone`.

### Improvement 4 — Badge selection (LOW priority)

**Current state**: lines 10-12 show 3 badges: status (yellow "v0.1 beta"), license, Python version.

**Proposal**: per `README_HERO_PATCH.md` §badges block — add **PyPI version badge** (auto-updates on each release; the single highest-signal "this is real software" indicator), **Docs badge** (links to the published docs site), update status to **"v0.2 beta"**. Optional: CI status badge (`.github/workflows/ci.yml`) if it doesn't add visual clutter. **Do not** add a Discord badge until the Discord server has at least 50 members (cold-room signals damage credibility).

**Verification**: after patch, badge row reads `PyPI | status | license | Python | docs` in that order.

### Improvement 5 — Call-to-action clarity (MEDIUM priority)

**Current state**: the README has two install blocks (lines 41-46 and 56-62) and a Postgres example (lines 65-69). It's clear what the commands are, but not what the **single happy-path sequence** is for a first-time reader.

**Proposal**: per `README_HERO_PATCH.md` §"3-command quickstart", surface a single 3-command sequence at the top:

```bash
pip install nucleus
nucleus init my-stack && cd my-stack && nucleus up
nucleus run example.greeting
```

Then a second optional block for Postgres + Workbench. This compresses the "5 commands to first BI-ready Iceberg table" demo flow into the most-scanned area of the README. Anyone curious about the full path follows the link to [`docs/onboarding/quickstart.md`](../../onboarding/quickstart.md).

**Verification**: after patch, the very first `bash` block has exactly 3 commands and contains no flags requiring explanation.

---

## What this file is NOT

- **Not the launch-kit ToC.** That's the directory listing of [`docs/release/launch_kit/`](.).
- **Not the comparison piece.** That's [`comparison_vs_databricks_snowflake.md`](comparison_vs_databricks_snowflake.md).
- **Not the FAQ.** That's [`HN_REDDIT_FAQ.md`](HN_REDDIT_FAQ.md) and [`faq_launch.md`](faq_launch.md).
- **Not the launch-day timeline.** That's [`LAUNCH_DAY_TIMELINE.md`](LAUNCH_DAY_TIMELINE.md).
- **Not a substitute for the README hero patch.** That's [`README_HERO_PATCH.md`](README_HERO_PATCH.md) — this file's §"Five proposed README improvements" is the **reviewer's audit**, not a competing proposal.

---

*Last updated 2026-05-15. If a wow moment becomes stale or a new artifact ships that beats one of these seven, update this file and reference the change in [`docs/release/v0.2.0_POST_LAUNCH_NOTES.md`](../v0.2.0_POST_LAUNCH_NOTES.md) (when that file is written T+24 h after tag push).*
