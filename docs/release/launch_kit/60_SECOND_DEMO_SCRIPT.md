# 60-Second Demo Script — Nucleus v0.2.0

*Shot-by-shot screencast. Total runtime 60 s. Expected total recording time ~10 min after retakes. Source of truth for stats: `docs/internal/benchmarks/2026-05-15_baseline.md`, `docs/release/launch_kit/press_kit.md` §key stats.*

---

## TL;DR for the recorder

> One terminal. One browser tab. Six scenes. No edits except trim-cut between scenes. Voiceover recorded separately, mixed in post. Shoot in 1080p60. Subtitles burned in.

---

## Pre-flight (run BEFORE you hit record)

```bash
# 1) Fresh venv with the lean core install (so Scene 1's `pip install` is honest about cold install time).
python3.11 -m venv ~/scratch/nucleus-demo && source ~/scratch/nucleus-demo/bin/activate
mkdir -p ~/scratch/demo-recording && cd ~/scratch/demo-recording

# 2) Pre-warm the pip cache for `nucleus[core]` (so the on-camera install is fast, not a Wi-Fi gamble).
pip download nucleus -d /tmp/nucleus-pip-cache && pip install --no-index --find-links /tmp/nucleus-pip-cache nucleus
pip uninstall -y nucleus   # remove so Scene 1 reinstalls; cache stays warm

# 3) Make a tiny SQLite source so Scene 4 has real rows + a real snapshot ID to display.
mkdir -p ./data
python3 -c "import sqlite3; c=sqlite3.connect('./data/orders.db'); c.executescript('CREATE TABLE orders(id INT, amount REAL, customer_id INT); INSERT INTO orders VALUES (1,42.50,7),(2,19.00,3),(3,128.75,7),(4,8.40,11),(5,77.00,3),(6,250.00,7),(7,15.50,11),(8,99.99,3),(9,33.33,7),(10,61.20,11);'); c.commit()"

# 4) Pre-start the Workbench in a SECOND terminal you won't film, so Scene 6 only switches tab.
#    (Workbench cold-start takes 3-5 s; we don't want that on camera.)
nucleus workbench up   # listens on http://localhost:8765 — leave running

# 5) Terminal cosmetics: 18 pt monospace font, dark theme, hide bookmark bar in browser,
#    close all unrelated tabs, set your shell prompt to `$ ` (one char + space), no fancy oh-my-zsh git status.

# 6) Resolution: 1920x1080 capture window. Browser zoom 110% so the editorial hero reads cleanly.
```

---

## Scene 1 — Install (0:00 → 0:05, **5 s**)

**Terminal action:**

```
$ pip install nucleus
```

**Voiceover:** *"Nucleus is a local-first Python SDK and CLI for Iceberg-native pipelines. Watch a five-engineer team go from `git clone` to a production-shaped table in under a minute."*

**On-screen subtitle:** `pip install nucleus  →  ~7 s on a warm cache`

**What viewers should see:** the install completing (warm cache means the download bar zips by; verify the elapsed time stays under 10 s after the green checkmark). If your network is slow on the day, fall back to `pip install --no-index --find-links /tmp/nucleus-pip-cache nucleus` for the take.

---

## Scene 2 — Init (0:05 → 0:15, **10 s**)

**Terminal action:**

```
$ nucleus init my-warehouse && cd my-warehouse
$ ls
```

**Voiceover:** *"`nucleus init` scaffolds a project: assets, checks, a project manifest, and a docker-compose for the local stack. No build step. No JVM."*

**On-screen subtitle:** `Scaffold an asset project — Apache 2.0, no JVM, no cluster.`

**What viewers should see:** the init command emit `Project 'my-warehouse' initialized` (or the v0.2 equivalent), then the `ls` reveals `assets/`, `checks/`, `nucleus_project.yaml`, `docker-compose.yaml`, `.nucleus/`, `data/`. Hold for ~2 s on the listing so the structure reads.

---

## Scene 3 — Up (0:15 → 0:30, **15 s**)

**Terminal action:**

```
$ nucleus up
```

**Voiceover:** *"`nucleus up` boots the local stack — object storage, an Iceberg catalog, the run ledger, the scheduling daemon. Cold boot lands at six seconds in our PoC #4 measurements; idle RAM sits at one hundred seventeen megabytes."*

**On-screen subtitle:** `Boot SeaweedFS + filesystem catalog + run ledger + scheduling daemon  →  ~6 s cold boot`

**What viewers should see:** the colored progress lines for each component (`storage ✓`, `catalog ✓`, `orchestration ✓`, `ledger ✓`). The whole sequence is ~6 s on a fresh laptop per `docs/internal/benchmarks/2026-05-15_baseline.md` §B5 (PoC #4 measured 5.82 s). If it overruns 15 s on the recording host, retry on a freshly-booted laptop — the measured number is what we cite.

---

## Scene 4 — Materialize (0:30 → 0:45, **15 s**)

**Terminal action:**

```
$ nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders
```

**Voiceover:** *"`nucleus ingest` is the one-liner that makes the thirty-minute beachhead metric possible. Auto-infer schema. Auto-create the Iceberg target. Atomic commit. Real snapshot ID."*

**On-screen subtitle:** `One-liner ingest  →  Iceberg snapshot, atomic commit, typed errors`

**What viewers should see:** the ingest emits the row count (`Wrote 10 rows to raw.orders`), the materialization ID, and the Iceberg snapshot ID (a long integer like `7070059669214185406`). Hold for ~2 s on the snapshot line so the audience reads it. The point is not "ten rows is impressive"; the point is "it really wrote a real Iceberg snapshot, and the user knows the ID."

> **Optional take with Postgres** (use only if you have a Postgres container ready and the `[postgres]` extra installed): `nucleus ingest postgres://localhost/app --table public.orders --as raw.orders`. Looks identical from the user's side because the dispatcher hides the source-driver differences.

---

## Scene 5 — Query (0:45 → 0:55, **10 s**)

**Terminal action:**

```
$ nucleus query "SELECT customer_id, count(*) AS orders, sum(amount) AS revenue FROM {{ ref('raw.orders') }} GROUP BY 1 ORDER BY revenue DESC LIMIT 5"
```

**Voiceover:** *"`nucleus query` runs Jinja-templated SQL through DuckDB against the Iceberg snapshot you just wrote. The reference resolver uses dbt-style `{{ ref() }}` so the SQL stays portable when you graduate to Databricks or Snowflake."*

**On-screen subtitle:** `Jinja {{ ref() }} → DuckDB → rendered Rich table`

**What viewers should see:** the Rich table renders five rows of customer rollup with the box-drawing borders. Hold ~2 s on the rendered output. Three customer IDs is enough to read; the table itself is the wow shot.

---

## Scene 6 — Workbench (0:55 → 1:00, **5 s**)

**Browser action:** alt-tab to the second monitor (or alt-tab to the browser window) at `http://localhost:8765`. The Workbench Editorial Hero is already live (it was started during pre-flight).

**Voiceover:** *"And the Workbench, on the same machine, gives you the asset graph, recent runs, and a Copilot — local-first, AI-ready, ready to graduate to giants when you outgrow your laptop."*

**On-screen subtitle:** `Workbench v0.3 — http://localhost:8765 — asset graph + run ledger + AI Copilot`

**What viewers should see:**
1. The blue-gradient hero at the top of the dashboard ("Today's pipeline" with four stat chips).
2. The "Recent runs" card with a fresh entry for `raw.orders` (you just materialized it in Scene 4 — its `last materialized` should read "a few seconds ago").
3. The pipeline DAG with `raw.orders` highlighted.

End frame on the dashboard. Logo overlay in the bottom-right with the URL `github.com/nucleus-data/nucleus`. License + Apache 2.0 text in the corner.

---

## Voiceover full script (subtitles version, ~120 words, ~50 s spoken pace)

> Nucleus is a local-first Python SDK and CLI for Iceberg-native pipelines. Watch a five-engineer team go from git clone to a production-shaped table in under a minute. `nucleus init` scaffolds a project — assets, checks, a project manifest, no build step, no JVM. `nucleus up` boots the local stack — object storage, an Iceberg catalog, the run ledger, the scheduling daemon. Cold boot is six seconds; idle RAM is one hundred seventeen megabytes. `nucleus ingest` is the one-liner that makes the thirty-minute beachhead metric possible — auto-infer schema, auto-create the Iceberg target, atomic commit. `nucleus query` runs Jinja-templated SQL through DuckDB against the Iceberg snapshot you just wrote. And the Workbench gives you the asset graph, recent runs, and a Copilot. Local-first. AI-ready. Apache 2.0.

---

## Recording tips

- **Terminal**: 1Password / Cursor / iTerm2 / Windows Terminal — pick whatever your audience expects. **Font 18 pt monospace** (JetBrains Mono / Fira Code). **Dark theme**. Foreground white, background `#0d1117` or similar. No transparency.
- **Browser**: hide the bookmark bar (`Ctrl+Shift+B` to toggle). Clear the address bar to `localhost:8765` before the take. Browser zoom `110%`.
- **Cursor**: hide it during voiceover scenes. Show it only when typing.
- **Typing speed**: do NOT auto-type. Real human typing reads honest. ~80-100 WPM is fine.
- **Voiceover**: record dry, not live. Re-record the script in a quiet room, mix at -3 dB, normalize. The screen capture is silent; voice and subtitles overlay in post.
- **Subtitles**: burn in (do NOT use platform auto-CC). Font: bold sans-serif, white text on a 50%-opacity black bar, bottom-third position, line-height 1.2.
- **Cuts**: only between scenes. No mid-scene jump cuts. No zoom/pan effects. The whole point is "look how fast this is in real time."
- **Music**: optional, royalty-free, instrumental, ducked under voiceover at -18 dB. If unsure, ship without music — silence is honest.
- **Export**: 1080p60, H.264, MP4 container, ~12 Mbps bitrate. Target file size <50 MB so it loads inline on Twitter/LinkedIn/HN comments.
- **Captions file**: also export an `.srt` so the docs site + dev.to article can embed the same video with accessibility intact.
- **Length budget**: total runtime **must** stay ≤ 60 s. If you overshoot, cut Scene 5 query complexity (use `LIMIT 5` not `LIMIT 10`) or trim Scene 3 boot if the recording host happens to boot under 5 s.

---

## Retake checklist (do another take if any of these are true)

- [ ] Total runtime > 60 s
- [ ] Any forbidden framing in the voiceover ("Data OS", "AI-first", "Spark killer", "Databricks killer") <!-- banned-term: multiple -->
- [ ] An external classname leaked into a CLI error (would be a release-blocking bug per `scripts/dagster_leak_check.py`)
- [ ] Boot took > 10 s in Scene 3 (we cite < 10 s; recording must support the claim)
- [ ] Workbench tab in Scene 6 doesn't show the just-materialized `raw.orders` (means the materialization didn't actually commit)
- [ ] Voice clipped or noisy
- [ ] Subtitle wraps onto 3 lines (revise wording to fit 2)
- [ ] Cursor visible during a static frame
- [ ] Browser bookmark bar visible
- [ ] Any window decoration (close button, dock, taskbar) shows OS-personal info

---

## Distribution

- Primary: embed in `README.md` hero section + `docs/site/index.md` + LinkedIn post + Twitter thread (Tweet 1) + dev.to article opening
- Secondary: pin on the GitHub repo's "About" sidebar
- Tertiary: auto-play on the docs site landing page (muted by default, with a play-with-sound button)
- Asset path: `assets/demos/v0.2/launch_60s.mp4` + `assets/demos/v0.2/launch_60s.srt`

---

*This script supports the v0.2.0 launch kit. If a scene rewrite is needed, update this file before re-recording so the next take is reproducible. Last updated 2026-05-15.*
