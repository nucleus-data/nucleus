# 60-Second Demo - Video Production Plan

*Companion to `60_SECOND_DEMO_SCRIPT.md` (shot-by-shot script) and `DEMO_RECORDING_CHECKLIST.md` (pre-record founder check). This file is the **production handbook**: timestamped shot list, exact terminal commands, expected on-screen output, voiceover script aligned to the timing, and the post-production checklist. The script file is authoritative for the editorial decisions; this file is authoritative for the production execution. Last updated 2026-05-15. ASCII-only.*

> **One-line scope**: produce a 60-second screencast that proves the 30-minute beachhead claim (PoC #5 / WSL E2E 8/8 PASS) is real, in a way an HN skeptic can verify by running the same commands.

---

## 1. Timing budget (top-level)

| Time | Scene | Duration | What viewer sees | What viewer hears |
|---|---|---|---|---|
| 0:00 - 0:05 | Title card | 5 s | Nucleus logo on blue gradient; tagline "Ship data products from a laptop"; v0.2.0 sub-title | Hook line (15 words) |
| 0:05 - 0:15 | Install | 10 s | `pip install nucleus` running and completing | "Nucleus is a local-first Python SDK and CLI for Iceberg pipelines..." |
| 0:15 - 0:25 | Init + Up | 10 s | `nucleus init my-stack && cd my-stack && nucleus up` | "`nucleus init` scaffolds; `nucleus up` boots the stack." |
| 0:25 - 0:40 | Ingest | 15 s | `nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders` | "One-liner ingest. Auto-infer schema. Atomic Iceberg commit." |
| 0:40 - 0:52 | Query | 12 s | `nucleus query "SELECT ... FROM {{ ref('raw.orders') }} ..."` Rich table | "Jinja-templated SQL through DuckDB against the snapshot." |
| 0:52 - 0:58 | Workbench | 6 s | Browser tab on `localhost:8765` Editorial Hero dashboard | "Workbench - asset graph, run ledger, AI Copilot." |
| 0:58 - 1:00 | Close card | 2 s | Logo + URL `github.com/nucleus-data/nucleus` + Apache 2.0 | "Apache 2.0. Local-first. AI-ready." |

**Total**: 60 s. Hard limit per the script's retake checklist.

---

## 2. Pre-flight (before you hit record)

These steps run in a SECOND terminal you do NOT film. Burn 5 minutes here to save 30 minutes of retakes.

```bash
# 1) Fresh venv with the lean core install (Scene 1 reinstalls; cache stays warm)
python3.11 -m venv ~/scratch/nucleus-demo
source ~/scratch/nucleus-demo/bin/activate
mkdir -p ~/scratch/demo-recording && cd ~/scratch/demo-recording

# 2) Pre-warm the pip cache so Scene 1 install runs in ~7 s, not 30 s
pip download nucleus -d /tmp/nucleus-pip-cache
pip install --no-index --find-links /tmp/nucleus-pip-cache nucleus
pip uninstall -y nucleus

# 3) Seed a tiny SQLite source so Scene 4 has real rows + a real snapshot ID
mkdir -p ./data
python3 - <<'PY'
import sqlite3
c = sqlite3.connect("./data/orders.db")
c.executescript("""
CREATE TABLE orders(id INT, amount REAL, customer_id INT);
INSERT INTO orders VALUES
  (1,42.50,7),(2,19.00,3),(3,128.75,7),(4,8.40,11),(5,77.00,3),
  (6,250.00,7),(7,15.50,11),(8,99.99,3),(9,33.33,7),(10,61.20,11);
""")
c.commit()
PY

# 4) Pre-start the Workbench in a SECOND, UNFILMED terminal
nucleus workbench up   # listens on http://localhost:8765 - leave running
```

After pre-flight, your two terminals are:

- **Terminal A** (FILMED): empty cwd, fresh shell, ready for Scene 1.
- **Terminal B** (NOT FILMED): runs `nucleus workbench up`, stays open.

---

## 3. Shot list (timestamped)

### Shot 1 - Title card (0:00 - 0:05, 5 s)

- **Visual**: full-screen title card. Blue gradient background (matches Workbench Editorial Hero). Centered text:
  - Line 1 (large): "Nucleus"
  - Line 2 (medium): "Ship data products from a laptop."
  - Line 3 (small): "v0.2.0  -  Apache 2.0  -  No JVM"
- **No terminal action.**
- **Voiceover (15 words, ~5 s at 180 WPM)**:
  > "Nucleus - a local-first Python SDK and CLI for Iceberg-native pipelines. Watch the 30-minute beachhead in 60 seconds."

### Shot 2 - Install (0:05 - 0:15, 10 s)

- **Terminal A**:

  ```
  $ pip install nucleus
  ```

- **Expected output (last 6 lines)**:

  ```
  Collecting nucleus
    Using cached nucleus-0.2.0-py3-none-any.whl
  Collecting duckdb==1.1.3
    Using cached duckdb-1.1.3-cp311-cp311-...whl
  ...
  Successfully installed nucleus-0.2.0 duckdb-1.1.3 polars-1.18.0 ...
  ```

- **On-screen subtitle**: `pip install nucleus  ->  ~7 s on a warm cache`
- **Voiceover (~10 s)**:
  > "Nucleus is a local-first Python SDK and CLI for Iceberg-native pipelines. One `pip install`. No JVM. No cluster."

### Shot 3 - Init + Up (0:15 - 0:25, 10 s)

- **Terminal A**:

  ```
  $ nucleus init my-stack && cd my-stack
  $ nucleus up
  ```

- **Expected output**:

  ```
  Project 'my-stack' initialized.
    assets/    checks/    nucleus_project.yaml    docker-compose.yaml    .nucleus/    data/

  Booting local stack...
    storage         OK
    catalog         OK
    orchestration   OK
    ledger          OK
  Ready at http://localhost:8765 (Workbench)
  Cold boot: ~6 s
  ```

- **On-screen subtitle**: `Scaffold + boot  ->  ~6 s, no JVM, no cluster`
- **Voiceover (~10 s)**:
  > "`nucleus init` scaffolds a project. `nucleus up` boots the local stack - object storage, Iceberg catalog, run ledger, scheduling daemon."

### Shot 4 - Ingest (0:25 - 0:40, 15 s)

- **Terminal A**:

  ```
  $ nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders
  ```

- **Expected output**:

  ```
  Reading from sqlite:///./data/orders.db (table: orders)...
  Schema inferred: id INT, amount DOUBLE, customer_id INT  (3 columns)
  Creating Iceberg table: raw.orders
  Writing 10 rows...
  Materialization: 6f0a3e2c-2d2f-4f0a-9e1a-3a2b1c4d5e6f
  Snapshot ID:     7070059669214185406
  Wrote 10 rows to raw.orders in 1.2 s.
  ```

- **On-screen subtitle**: `One-liner ingest  ->  Iceberg snapshot, atomic commit`
- **Voiceover (~15 s)**:
  > "`nucleus ingest` is the one-liner that makes the 30-minute beachhead metric possible. Auto-infer schema. Auto-create the Iceberg target. Atomic commit. Real snapshot ID."

### Shot 5 - Query (0:40 - 0:52, 12 s)

- **Terminal A**:

  ```
  $ nucleus query "SELECT customer_id, count(*) AS orders, sum(amount) AS revenue FROM {{ ref('raw.orders') }} GROUP BY 1 ORDER BY revenue DESC LIMIT 3"
  ```

- **Expected output** (Rich table render):

  ```
  +-------------+--------+---------+
  | customer_id | orders | revenue |
  +-------------+--------+---------+
  |           7 |      4 |  454.58 |
  |           3 |      3 |  195.99 |
  |          11 |      3 |   85.10 |
  +-------------+--------+---------+
  3 rows in 0.08 s
  ```

- **On-screen subtitle**: `Jinja {{ ref() }}  ->  DuckDB  ->  Rich table`
- **Voiceover (~12 s)**:
  > "`nucleus query` runs Jinja-templated SQL through DuckDB against the snapshot. The `{{ ref() }}` resolver stays portable when you graduate to Databricks or Snowflake."

### Shot 6 - Workbench (0:52 - 0:58, 6 s)

- **Visual action**: alt-tab from Terminal A to the browser tab at `http://localhost:8765`. The Editorial Hero is already live (Terminal B is running `nucleus workbench up`).
- **What viewer sees**:
  1. Blue-gradient hero with four glassmorphism stat chips (`12 assets / 4.2M rows / 18 checks green / 3 min ago`).
  2. Recent runs card showing `raw.orders` with timestamp "a few seconds ago".
  3. Pipeline DAG with `raw.orders` highlighted.
- **On-screen subtitle**: `Workbench v0.3  ->  asset graph + run ledger + AI Copilot`
- **Voiceover (~6 s)**:
  > "And the Workbench - on the same machine - gives you the asset graph, recent runs, and a Copilot."

### Shot 7 - Close card (0:58 - 1:00, 2 s)

- **Visual**: cut back to a full-screen card. Centered:
  - Line 1: Nucleus logo
  - Line 2: `github.com/nucleus-data/nucleus`
  - Line 3: `Apache 2.0  -  Local-first  -  AI-ready by design`
- **No terminal action.**
- **Voiceover (~2 s)**:
  > "Apache 2.0. Local-first. AI-ready."

---

## 4. Voiceover full script (subtitles version)

Target word count: 130 words at ~180 WPM = ~43 s spoken, leaves 17 s of breathing room and shot transitions.

> "Nucleus - a local-first Python SDK and CLI for Iceberg-native pipelines. Watch the 30-minute beachhead in 60 seconds. Nucleus is a local-first Python SDK and CLI for Iceberg-native pipelines. One `pip install`. No JVM. No cluster. `nucleus init` scaffolds a project. `nucleus up` boots the local stack - object storage, Iceberg catalog, run ledger, scheduling daemon. `nucleus ingest` is the one-liner that makes the 30-minute beachhead metric possible - auto-infer schema, auto-create the Iceberg target, atomic commit, real snapshot ID. `nucleus query` runs Jinja-templated SQL through DuckDB against the snapshot. The `{{ ref() }}` resolver stays portable when you graduate to Databricks or Snowflake. And the Workbench gives you the asset graph, recent runs, and a Copilot. Apache 2.0. Local-first. AI-ready."

---

## 5. Subtitle file (.srt format)

Burn the subtitles in (do NOT rely on platform auto-CC). Save the source as `assets/demos/v0.2/launch_60s.srt`:

```
1
00:00:00,000 --> 00:00:05,000
Nucleus - local-first Python SDK + CLI for Iceberg-native pipelines.

2
00:00:05,000 --> 00:00:15,000
One pip install. No JVM. No cluster.

3
00:00:15,000 --> 00:00:25,000
nucleus init scaffolds; nucleus up boots the local stack.

4
00:00:25,000 --> 00:00:40,000
nucleus ingest - auto-infer schema, atomic Iceberg commit, real snapshot ID.

5
00:00:40,000 --> 00:00:52,000
nucleus query - Jinja-templated SQL through DuckDB against the snapshot.

6
00:00:52,000 --> 00:00:58,000
Workbench: asset graph + run ledger + AI Copilot.

7
00:00:58,000 --> 00:01:00,000
Apache 2.0. Local-first. AI-ready.
```

---

## 6. Post-production checklist

| Step | Tool | Output |
|---|---|---|
| 1. Record screen + Terminal A | OBS Studio (Linux/Mac) or ScreenToGif (Windows) at 1920x1080, 60 fps | `~/scratch/demo-raw.mp4` |
| 2. Record voiceover separately | Audacity, 48 kHz mono, normalize to -3 dB | `~/scratch/voice.wav` |
| 3. Cut to scene timestamps | DaVinci Resolve (free) or ffmpeg | `~/scratch/demo-cut.mp4` |
| 4. Burn in subtitles | DaVinci Resolve or `ffmpeg -vf subtitles=launch_60s.srt` | `~/scratch/demo-subbed.mp4` |
| 5. Mix voiceover under -18 dB | DaVinci Resolve | `~/scratch/demo-mixed.mp4` |
| 6. Encode H.264 12 Mbps, MP4 | `ffmpeg -c:v libx264 -b:v 12M -c:a aac -b:a 128k` | `assets/demos/v0.2/launch_60s.mp4` |
| 7. Generate poster image | `ffmpeg -ss 0.5 -i launch_60s.mp4 -frames:v 1` | `assets/demos/v0.2/launch_60s_poster.png` |
| 8. Verify final file size < 50 MB | `ls -lh assets/demos/v0.2/launch_60s.mp4` | Pass / Re-encode |

**Hard requirement**: final MP4 must be < 50 MB so Twitter and LinkedIn upload it natively (their auto-compression for larger files degrades quality and chops the last 1-2 seconds).

---

## 7. Retake triggers (re-shoot if any of these are true)

- Total runtime > 60 s
- Any forbidden framing in the voiceover ("AI-first", "Spark killer", "Databricks killer", "Data OS") <!-- banned-term: launch-forbidden-framings -->
- A wrapped-library class name leaks into a CLI error (e.g., `OpExecutionContext`, `DuckDBPyConnection`, `DagsterAssetMaterializationPlanningError`) - this would be a release-blocker bug per `scripts/dagster_leak_check.py`
- Boot took > 10 s in Shot 3 (we cite < 10 s; recording must support the claim)
- Workbench tab in Shot 6 does not show the just-materialized `raw.orders`
- Voice clipped, noisy, or out-of-sync with the on-screen action
- Subtitle wraps onto 3+ lines (revise wording to fit 2 lines max)
- Cursor visible during a static frame
- Browser bookmark bar visible
- Any window decoration (close button, dock, taskbar) shows OS-personal info

---

## 8. Distribution targets

- **Primary**: README hero `<video>` embed (see `README_HERO_PATCH.md` for the markdown).
- **Docs site landing**: `docs/site/index.md` (autoplay muted, with "play with sound" button).
- **Twitter Tweet 1**: native MP4 upload paired with the hook tweet.
- **LinkedIn**: native upload (LinkedIn deprioritizes external video links).
- **HN comment**: link to `https://github.com/nucleus-data/nucleus/raw/main/assets/demos/v0.2/launch_60s.mp4` in the first comment.
- **dev.to article**: opening video embed before the pain-first paragraph.

Asset paths (final):

- `assets/demos/v0.2/launch_60s.mp4` (the video)
- `assets/demos/v0.2/launch_60s.srt` (subtitles source)
- `assets/demos/v0.2/launch_60s_poster.png` (frame-0 poster for the README embed)
- `docs/release/launch_kit/demo.cast` (asciinema source for the install + 5-command sequence)

---

## 9. Cross-references

- Shot-by-shot editorial (this file's parent): `docs/release/launch_kit/60_SECOND_DEMO_SCRIPT.md`
- Pre-record founder checklist: `docs/release/launch_kit/DEMO_RECORDING_CHECKLIST.md`
- Asciinema cast source (terminal-only, no voice): `docs/release/launch_kit/demo.cast`
- README hero patch (where the embed will live): `docs/release/launch_kit/README_HERO_PATCH.md`
- Vocabulary discipline (banned framings in the voiceover): `AGENTS.md` section 7 + section 8
- Beachhead claim (the source of "30-minute" in the title card): `docs/specs/nucleus_architecture_v4.1.md` section 1.5
- WSL E2E proof (the empirical 30-min validation): `docs/internal/release-process/e2e_results_20260514T190132.md`

*Last updated 2026-05-15. Refresh trigger: any post-launch retake or any change to the CLI surface that breaks one of the shown commands.*
