# Demo Recording Pre-Flight Checklist - Founder One-Pager

*One page. Print it. Tick boxes physically before you hit record. Source for the editorial decisions: `60_SECOND_DEMO_SCRIPT.md`. Source for production execution: `DEMO_VIDEO_PRODUCTION.md`. Asciinema alternative: `demo.cast`. ASCII-only. Last updated 2026-05-15.*

> **One sentence**: 5 minutes of pre-flight here saves 30 minutes of retakes. Do not skip a step.

---

## Section A - Hardware + environment (3 min)

- [ ] **Laptop on AC power**, not battery (recording on battery throttles CPU and breaks the boot-time claim).
- [ ] **Fresh boot** within the last 30 minutes (cold RAM cache = best B5 boot numbers).
- [ ] **WiFi or wired network is healthy** (`ping -c 3 pypi.org` returns < 50 ms). If you are demoing offline, confirm `/tmp/nucleus-pip-cache/` is pre-warmed (see `DEMO_VIDEO_PRODUCTION.md` section 2 step 2).
- [ ] **Notifications silenced** (macOS Focus mode, Linux GNOME do-not-disturb, Windows Focus Assist).
- [ ] **Screen lock / screensaver disabled** for the next hour (caffeinate / xset / Windows power plan).
- [ ] **External monitor unplugged** (single 1920x1080 capture surface; multi-monitor adds clutter and OBS scene complexity).
- [ ] **Microphone tested** (`arecord -d 3 test.wav && aplay test.wav` on Linux; QuickTime on macOS) - voice clean at -3 dB peak.

---

## Section B - Terminal cosmetics (2 min)

- [ ] **Terminal**: pick one - iTerm2 / Windows Terminal / GNOME Terminal / WezTerm. Same one the whole demo.
- [ ] **Font**: JetBrains Mono or Fira Code at **18 pt**. Bold for prompts is fine; italics for output is not.
- [ ] **Theme**: dark background, light foreground. Recommended: foreground `#e6edf3`, background `#0d1117` (GitHub dark).
- [ ] **No transparency** (opaque background; transparency reads as "fancy" on video, not "professional").
- [ ] **Window size**: 100 columns x 30 rows. Resize before the take so the prompt does not wrap.
- [ ] **Prompt**: simplify to `$ ` (dollar + space). NO git status, NO conda env in prompt, NO virtualenv name (export PS1="\$ " in the take terminal).
- [ ] **Shell history disabled** for the take session (`unset HISTFILE && bash` then `unset PROMPT_COMMAND`). Up-arrow keystrokes accidentally reveal personal history.
- [ ] **TAB completion disabled** (export `bind 'TAB:'` for bash, or skip - the demo types every command end-to-end; do NOT use completion on camera).
- [ ] **Cursor blink off** (set in terminal preferences) - cursor blink is distracting in the recording.

---

## Section C - Browser cosmetics (1 min)

- [ ] **Browser tab order**: only ONE tab open, on `http://localhost:8765` (Workbench).
- [ ] **Bookmark bar hidden** (`Ctrl+Shift+B` to toggle on Chrome/Firefox/Edge).
- [ ] **Zoom**: 110% (the Editorial Hero stat chips read cleanly at this zoom).
- [ ] **DevTools closed** (F12 to close if open).
- [ ] **Browser window matches terminal width** when alt-tabbed (1920x1080 fills the capture frame).
- [ ] **Address bar cleared** to exactly `localhost:8765` (no autosuggest dropdown visible).
- [ ] **Cookie banner / extension toolbars** hidden (the recording should show only the Workbench UI).

---

## Section D - MinIO + local stack pre-warmed (1 min)

- [ ] **Workbench started in a SECOND terminal** you will NOT film: `nucleus workbench up`. Leave running for the entire take.
- [ ] **Verify Workbench is reachable** before the take: `curl -fsS http://localhost:8765/api/health` returns 200. If 5xx, fix before recording.
- [ ] **MinIO** (if your stack uses it): `nucleus up` already brought it up. Verify via `curl -fsS http://localhost:9000` if the take depends on S3-flavored storage.
- [ ] **Stack tear-down rehearsed** between takes: `nucleus down && rm -rf my-stack` returns clean. Re-running takes from a stale directory shows old `raw.orders` rows; the demo must show a fresh materialization.

---

## Section E - Sample data seeded (1 min)

- [ ] **SQLite source exists** at `./data/orders.db` with 10 rows in table `orders` per the script in `DEMO_VIDEO_PRODUCTION.md` section 2 step 3.
- [ ] **Sanity-check row count**: `sqlite3 ./data/orders.db "SELECT COUNT(*) FROM orders;"` returns `10`.
- [ ] **Schema matches the voiceover claim** (`id INT, amount REAL/DOUBLE, customer_id INT`). If the recording host shows a different schema name, update the voiceover to match BEFORE the take.
- [ ] **Query result is deterministic**: running the Shot 5 query against the freshly-seeded data returns the same top-3 rows every time. Verify once, then leave the data alone.

---

## Section F - Vocabulary + governance (1 min)

- [ ] **Voiceover script read aloud once** before recording - listen for any of: "AI-first" / "AI-native" / "Spark killer" / "Databricks killer" / "Data OS" / "AI-native data CLI". If any slip in, rewrite per `AGENTS.md` section 8. <!-- banned-term: launch-forbidden-framings -->
- [ ] **CLI output has no class-name leaks**: run each take command once OFF-CAMERA and grep for `Dagster`, `DuckDBPyConnection`, `OpExecutionContext`, `pyiceberg.exceptions`. If any leak, **STOP** - that is a release-blocker per `scripts/dagster_leak_check.py`. Fix the bug, then re-record.
- [ ] **Boot time on the recording host is < 10 s** for `nucleus up`. If it is over 10 s, retry on a freshly-rebooted laptop; we cite < 10 s in the voiceover and the recording must support the claim (`docs/benchmarks/2026-05-15_baseline.md` section B5).

---

## Section G - Recording software (1 min)

- [ ] **OBS Studio** (Linux/macOS) or **ScreenToGif** (Windows) configured for **1920x1080 at 60 fps**.
- [ ] **Scene preset saved**: "Nucleus Demo - Terminal" (Display Capture, no webcam, no overlays).
- [ ] **Audio source set to None** for screen capture (voice records separately in Audacity).
- [ ] **Test recording**: 10-second test clip, replay it, confirm the terminal text is sharp (no chroma subsampling artifacts on small fonts).
- [ ] **Recording hot-key memorized** (`F9` in OBS by default). Practice once before the real take.

---

## Section H - Voiceover recording (separate take, 1 min setup)

- [ ] **Audacity / GarageBand / Reaper open** with a new project at 48 kHz mono.
- [ ] **Microphone gain set** so the voiceover script reads at -12 dB peak, -3 dB max.
- [ ] **Pop filter or 6-inch distance** between mouth and mic.
- [ ] **Quiet room** (close windows, turn off HVAC if loud, kill any nearby fans).
- [ ] **Read the voiceover script aloud once** as warm-up. Tongue-twisters: "Iceberg-native", "Jinja-templated", "scheduling daemon".

---

## Section I - Take execution

### First take

- [ ] Hit record on OBS.
- [ ] Wait 1 s of silent dark screen (will be trimmed in post but gives audio room to settle).
- [ ] Run the 5 commands in sequence, in Terminal A:
  1. `pip install nucleus`
  2. `nucleus init my-stack && cd my-stack`
  3. `nucleus up`
  4. `nucleus ingest sqlite:///./data/orders.db --table orders --as raw.orders`
  5. `nucleus query "SELECT customer_id, count(*) AS orders, sum(amount) AS revenue FROM {{ ref('raw.orders') }} GROUP BY 1 ORDER BY revenue DESC LIMIT 3"`
- [ ] Alt-tab to the browser tab on `http://localhost:8765` for the Workbench shot. Hold for 5 s.
- [ ] Alt-tab back to Terminal A. Hold for 1 s on the empty prompt.
- [ ] Stop recording.
- [ ] **Save raw**: `~/scratch/demo-take-01.mp4`.

### Retake triggers (re-shoot if any are true after replay)

- [ ] Total elapsed > 60 s
- [ ] Any wrapped-library class name leaked into a CLI error
- [ ] Boot took > 10 s in Shot 3
- [ ] Workbench tab in Shot 6 did not show `raw.orders` just-materialized (timing race; rerun the ingest right before the alt-tab)
- [ ] Audio (voiceover) was clipped, breathy, or mis-aligned
- [ ] Subtitle wraps onto 3+ lines
- [ ] Cursor visible during a static frame
- [ ] Browser bookmark bar visible
- [ ] OS notification popped up during recording
- [ ] Personal info visible anywhere (username in prompt, file paths revealing real names, etc.)

If 2 or more triggers fire, **stop, reset (`nucleus down && rm -rf my-stack`), restart Section I from scratch**.

---

## Section J - Post-record (5 min)

- [ ] **Trim** the leading silent 1 s and the trailing dead-air. Final cut starts on Shot 1 voiceover and ends on the close-card fade.
- [ ] **Mix voiceover** under the screen recording at -3 dB peak. Verify no clipping.
- [ ] **Burn in subtitles** from the `.srt` source in `DEMO_VIDEO_PRODUCTION.md` section 5. White text, 50%-opacity black bar, bottom third.
- [ ] **Export** as H.264 12 Mbps MP4 to `assets/demos/v0.2/launch_60s.mp4`. Verify file size < 50 MB.
- [ ] **Generate poster image** from frame 0.5 s: save to `assets/demos/v0.2/launch_60s_poster.png`.
- [ ] **Upload to YouTube as UNLISTED** first; verify the embed plays cleanly. Make public only on launch day after the README hero patch ships.
- [ ] **Asciinema parallel cast**: optionally run `asciinema rec docs/release/launch_kit/demo.cast` to capture a terminal-only cast for HN's first-comment link.

---

## Section K - Final sign-off

- [ ] Replay the final video end-to-end ONCE. Stop watching at 60 s. If you can resist re-shooting at this point, you are done.
- [ ] Update `docs/release/launch_kit/WOW_MOMENTS.md` row #2 ("60-sec screencast") - mark the recording as DONE.
- [ ] Update `docs/internal/release-process/FOUNDER_ULTIMATE_SPRINT_RUNBOOK.md` Phase 0 checkbox "Demo video recorded" to checked.
- [ ] Commit asset paths in a single PR: `release: ship 60-sec demo video + poster + asciinema cast (v0.2.0 launch)`.

---

## Cross-references

- Editorial decisions: `60_SECOND_DEMO_SCRIPT.md`
- Production handbook (this file's parent): `DEMO_VIDEO_PRODUCTION.md`
- Asciinema cast: `demo.cast`
- README hero patch (where the video embed lives): `README_HERO_PATCH.md`
- Forbidden framings: `AGENTS.md` section 8
- Beachhead source-of-truth: `docs/specs/nucleus_architecture_v4.1.md` section 1.5
- Benchmark numbers cited in the voiceover: `docs/benchmarks/2026-05-15_baseline.md`

*If you ship and a retake is needed post-launch, log the trigger in `docs/release/v0.2.0_POST_LAUNCH_NOTES.md` so the next demo recording can include the lesson.*
