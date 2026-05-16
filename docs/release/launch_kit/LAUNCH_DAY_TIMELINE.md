# Launch Day Timeline — Nucleus v0.2.0

*Hour-by-hour Tuesday or Wednesday execution plan for a single founder firing all five public channels in sequence. All times are **Pacific Time** (PT) anchored to the Show HN window. Add **+3 h** for ET, **+8 h** for UTC. Companion to `docs/release/v0.2.0_RELEASE_READINESS.md` (32-item checklist) and `docs/internal/release-process/v0.2_FOUNDER_CLOSE_CHECKLIST.md` (master runbook). Last updated 2026-05-15.*

> **Submission day**: pick **Tuesday or Wednesday**. Avoid Monday (HN absorbs weekend backlog, you drown). Avoid Thursday (HN deprioritizes long-tail discussion). **Never Friday** (weekend dies the post). The actual calendar date is set in `FOUNDER_ACTION_QUEUE.md` once the founder confirms PyPI Trusted Publisher + branch protection are unblocked.

---

## T-24 h — Day before (afternoon prep)

| Time (PT) | Task | Done? |
|---|---|---|
| 14:00 | **Open** `docs/internal/release-process/v0.2_FOUNDER_CLOSE_CHECKLIST.md` and confirm every Phase 1 item is GREEN. If any item is RED, stop — defer launch by one day. | [ ] |
| 14:15 | **Set PoC #5 compensation** in `docs/internal/poc/p5_beachhead/RECRUITMENT_PLAN.md` (recommended `$150` per 90-min session). FOUNDER ACTION: replace the compensation placeholder before outreach. | [ ] |
| 14:25 | **Publish the Calendly link** (e.g., `calendly.com/<you>/nucleus-poc5-30min`). Paste into `RECRUITMENT_PLAN.md` and into the 20 outreach email templates at `docs/internal/poc/p5_beachhead/outreach_emails/`. | [ ] |
| 14:45 | **Stage 20 outreach emails as Gmail drafts** — do not send yet. Each draft addressed individually, no BCC blast. | [ ] |
| 15:00 | **Record the 60-second demo** per `docs/release/launch_kit/60_SECOND_DEMO_SCRIPT.md`. Budget 90 min for retakes; ship if any take meets the retake checklist at the bottom of that file. | [ ] |
| 16:30 | **Upload the demo MP4** to `assets/demos/v0.2/launch_60s.mp4` and confirm the file size is < 50 MB (Twitter/LinkedIn native-upload ceiling). | [ ] |
| 16:45 | **Capture three screenshots** — Workbench dashboard, terminal after `nucleus run`, terminal after `nucleus query`. Save under `assets/screenshots/v0.2/`. | [ ] |
| 17:00 | **Pre-flight social drafts**: open `SOCIAL_POSTS.md` in a side panel; copy each block into the channel's native composer **as a draft** (Twitter, LinkedIn, Reddit). Do not schedule yet — drafts only. | [ ] |
| 17:30 | **Verify CI green on `main`** — `gh run list --workflow=ci.yml --branch=main --limit=1` shows `success`. If not, defer launch. | [ ] |
| 18:00 | **Sleep early.** First HN comments hit at T+5 min and the window for high-quality early responses closes at T+4 h. | [ ] |

---

## T-4 h — Morning of (02:00 PT)

| Time (PT) | Task | Done? |
|---|---|---|
| 02:00 | **Wake** (sorry). First check: <https://status.github.com> + <https://status.pypi.org> — abort if either is red. | [ ] |
| 02:15 | **Re-run governance locally** — `python scripts/check_vocabulary.py && python scripts/check_pinning.py && python scripts/loc_budget.py && python scripts/dagster_leak_check.py`. All four must exit `0`. | [ ] |
| 02:30 | **Re-run pytest** — `pytest tests/ poc/ -m "not integration and not slow" --no-cov -q`. Expect 850+ passed / 0 failed. | [ ] |
| 02:45 | **Verify the PyPI Trusted Publisher binding is live** — load <https://pypi.org/manage/account/publishing/> in a browser; confirm `nucleus-data/nucleus` row exists with workflow `release.yml` and environment `pypi`. | [ ] |
| 03:00 | **Coffee. No code commits between now and T+24 h** — `main` is frozen except for emergency hotfixes (and even then, only if a release-blocking bug surfaces in HN comments). | [ ] |

---

## T-1 h — Final pre-fire (05:00 PT)

| Time (PT) | Task | Done? |
|---|---|---|
| 05:00 | **Push the tag.** Follow `RELEASE_READINESS.md` Phase 2: stage commit → push → `git tag -a v0.2.0` → `git push origin v0.2.0`. **This is the moment of public commitment.** | [ ] |
| 05:10 | **Watch the PyPI publish workflow** — `gh run watch --repo nucleus-data/nucleus`. Expect ~6–8 min total. All three jobs must go green: `build`, `publish-pypi`, `create-release`. | [ ] |
| 05:25 | **Cold install smoke from PyPI** — `python -m venv .venv-pypi && .\.venv-pypi\Scripts\Activate.ps1 && pip install nucleus-data==0.2.0 && nucleus version`. Must print `0.2.0`. | [ ] |
| 05:35 | **Replace auto-generated Release body with curated notes** — `gh release edit v0.2.0 --notes-file docs/release/v0.2.0_RELEASE_NOTES.md`. | [ ] |
| 05:45 | **Verify the docs site is live** — load <https://nucleus-data.github.io/nucleus/> (or your domain) in a clean browser tab; click through the quickstart and confirm the install copy distinguishes PyPI release install from local-dev editable install. GitHub Pages requires the repo to be public or GitHub Pro until enabled. | [ ] |
| 05:50 | **Open all five composer tabs**, drafts already pasted: HN submit, Twitter, LinkedIn, Reddit /r/dataengineering, dev.to. Stage the URLs in a notes file so you can grab them quickly for cross-linking later. | [ ] |
| 05:55 | **Final breath.** Re-read the HN first-comment draft (`docs/release/launch_kit/hn_post.md`). Make sure you can paste it within 60 s of submission. | [ ] |

---

## T-0 — Fire (06:00 PT / 09:00 ET)

> **The 30-minute critical path.** Every minute over budget is a minute the post sits below the front-page fold while ranking is still soft.

| Time (PT) | Task | Done? |
|---|---|---|
| 06:00 | **Submit Show HN** at <https://news.ycombinator.com/submit>. Title from `SHOW_HN_HEADLINES.md` top recommendation (A1). URL field = repo. Submit. | [ ] |
| 06:01 | **Paste first comment** from `hn_post.md` immediately — the comment must land within 60 s so it pins above other replies. | [ ] |
| 06:03 | **Fire Twitter / X thread** — paste all 10 tweets from `SOCIAL_POSTS.md` §1 in sequence; attach the 60-sec demo MP4 to Tweet 1; pin Tweet 1 to profile. | [ ] |
| 06:10 | **Send the 20 PoC #5 outreach emails** — release the Gmail drafts staged at T-24 h. Each goes individually (no BCC). | [ ] |
| 06:20 | **Capture the HN submission URL** (`news.ycombinator.com/item?id=NNNNNNNN`) — paste into a notes file for cross-channel replies. | [ ] |
| 06:25 | **Do not manipulate votes.** Share the repo and answer comments in good faith; do not ask friends to vote and do not vote-ring. | [ ] |
| 06:30 | **30-minute window CLOSED.** Move into response mode. | [ ] |

---

## T+1 h — First-comment response window (07:00 PT)

By now your HN post has 5–30 comments. The first 4 h of comment-thread health determines whether the post stays on the front page through the day.

| Time (PT) | Task | Done? |
|---|---|---|
| 07:00 | **Open the HN thread** — refresh every 5 min. The first wave of comments will be "this is just dbt + Dagster wrapped" / "why not Spark" / "another data platform". Have `HN_REDDIT_FAQ.md` open in a second tab. | [ ] |
| 07:05 | **Reply to every top-level comment in the first hour** — even one-liners. Velocity > polish in the first 4 h. Use the `HN_REDDIT_FAQ.md` answers as a starting point; paraphrase, don't paste verbatim (looks robotic). | [ ] |
| 07:15 | **Top-10 critical-take script** (paraphrase, don't paste): | |
| | (1) "Just dbt?" → see FAQ Q2 (we wrap, don't replace; 180 LOC ceiling; native Iceberg writes are the differentiator). | [ ] |
| | (2) "Just Dagster?" → see FAQ Q7 (boot time, error translation, asset-graph-hidden ergonomics). | [ ] |
| | (3) "Why not Spark?" → see FAQ Q1 (JVM, single-node envelope, yield-to-giants). | [ ] |
| | (4) "Why Iceberg over Delta?" → see FAQ Q5 (every catalog converging on Iceberg). | [ ] |
| | (5) "AI is just ChatGPT?" → see FAQ Q6 (yes, intentionally; v0.5 lineage-aware arrives later). | [ ] |
| | (6) "How does it scale?" → see FAQ Q14 (single-node until graduation; documented honestly). | [ ] |
| | (7) "License pivot risk?" → see FAQ Q8 (Apache 2.0 forever, no BSL/SSPL). | [ ] |
| | (8) "ACID without coordinator?" → see FAQ Q10 (catalog handles it; advisory lock for single-machine). | [ ] |
| | (9) "Will the API break?" → see FAQ Q19 (core data APIs stable; AI APIs may evolve). | [ ] |
| | (10) "What if you abandon it?" → see FAQ Q20 (Iceberg bytes are vendor-neutral; Apache 2.0 means anyone can fork). | [ ] |
| 07:45 | **Do NOT respond to hostile content-free comments** ("this is just a wrapper / fad / X-killer"). Engaging amplifies them. Silence drops them. | [ ] |
| 08:00 | **Snack break — 15 min off-screen** before the next wave. | [ ] |

---

## T+4 h — Second-wave channels (10:00 PT)

By now the HN post has either taken the front page (you've crossed ~40 points) or it hasn't. Either way, fire the second-wave channels now.

| Time (PT) | Task | Done? |
|---|---|---|
| 10:00 | **Fire LinkedIn post** — paste from `SOCIAL_POSTS.md` §2; attach the 60-sec demo as native LinkedIn video (NOT a YouTube link); add the three hashtags from the post body. | [ ] |
| 10:10 | **Fire r/dataengineering submission** — paste title + body from `SOCIAL_POSTS.md` §3; apply `Open Source` flair; do NOT cross-post to /r/Python or /r/programming the same day (Reddit auto-flags). | [ ] |
| 10:20 | **Publish dev.to article** — paste from `SOCIAL_POSTS.md` §4 (intro) + expand to the full article body (~1,500 words) using `blog_post_launch.md` as the source; tag with `dataengineering`, `iceberg`, `python`, `showdev`. | [ ] |
| 10:30 | **Cross-link from HN comment** — leave a polite top-level comment under the OP: *"Also discussing on r/dataengineering: [link] and LinkedIn: [link]. Same questions, different angles."* | [ ] |
| 10:35 | **Cross-link from Reddit comment** — same as above, in reverse. | [ ] |
| 10:40 | **Tweet the dev.to article** — quote-tweet your Tweet 10 with the dev.to URL. | [ ] |
| 11:00 | **Take a real lunch.** The next critical check-in is T+12 h. | [ ] |

---

## T+12 h — Evening check-in (18:00 PT)

| Time (PT) | Task | Done? |
|---|---|---|
| 18:00 | **HN thread health** — count: comments, upvotes, current rank (page 1 / 2 / 3+). If page 1, you're cruising. If page 3+, the post peaked; do not resubmit today. | [ ] |
| 18:10 | **Production-fires triage** — open the GitHub Issues tab. Any issue with `installation broken` / `crash on first run` / `data loss` priority labels needs a hotfix branch before sleep. Anything else queues for the morning. | [ ] |
| 18:30 | **PoC #5 reply triage** — check Gmail for replies from the 20 outreach emails. Calendly auto-handles booked slots. Anyone who replied "interested but not now" gets a 1-line thank-you. Anyone who replied "no thanks" gets nothing. | [ ] |
| 18:45 | **One more round of HN/Reddit responses** — by now you're hitting "depth" questions (architecture, scaling, business model). Use `HN_REDDIT_FAQ.md` Q4 / Q11 / Q12 / Q14 / Q15. | [ ] |
| 19:30 | **Off-screen for the night.** The first 24-h cycle is well past the velocity-decay window; tomorrow's check-in handles long-tail. | [ ] |

---

## T+24 h — Post-mortem (06:00 PT, next day)

Total elapsed: 24 h from Show HN submission.

| Time (PT) | Task | Done? |
|---|---|---|
| 06:00 | **Snapshot HN metrics** — final upvote count, comment count, peak rank, hours on front page. Save into `docs/release/launch_kit/post_mortem_v0.2.0.md`. | [ ] |
| 06:10 | **Snapshot Twitter/LinkedIn metrics** — impressions, retweets/reshares, profile-follow delta. Same file. | [ ] |
| 06:20 | **GitHub stars delta** — `gh api repos/nucleus-data/nucleus | jq .stargazers_count` minus the count at T-1 h. Same file. | [ ] |
| 06:30 | **PyPI download count** — <https://pypistats.org/packages/nucleus> shows 24-h totals 12–24 h after the first install. Capture and log. | [ ] |
| 06:45 | **Open issues / pull requests delta** — `gh issue list --state open --limit 100 | wc -l` and same for PRs. Triage anything tagged `installation broken` / `data loss` to top of the v0.2.1 hotfix queue. | [ ] |
| 07:00 | **Write a 200-word post-mortem note** in `post_mortem_v0.2.0.md`: what worked, what didn't, what to do differently for the v0.3 launch. Three bullets each. | [ ] |
| 07:30 | **Update `FOUNDER_ACTION_QUEUE.md`** with the new top priority (PoC #5 sessions if booked, hotfix bug list, v0.3 planning kickoff). | [ ] |
| 08:00 | **STOP.** No more launch-day activity. Tomorrow is for the next thing. | [ ] |

---

## Stop-conditions during the timeline

If any of these fire, **PAUSE and triage** before continuing:

- **CI red on `main`** at T-4 h → defer launch by 24 h, fix in foreground.
- **PyPI publish workflow FAILs** at T-1 h → check the OIDC binding; if not fixable in 30 min, defer.
- **GitHub or PyPI is down** at T-0 → defer to next eligible day (Tue or Wed).
- **HN auto-flags / shadowbans the post** → email <hn@ycombinator.com> politely; resubmit only after they reply.
- **Hostile comment thread spirals** (e.g., 5+ "this is just X" comments in a row) → stop responding; let the thread cool. Your reply-velocity feeds the troll.
- **Production-breaking bug surfaces in the first hour** (e.g., `pip install nucleus-data` immediately fails) → pull the GitHub Release back to draft (`gh release edit v0.2.0 --draft`); fix; re-publish. The PyPI artifact stays live (you can't unpublish, only yank).
- **You are tired and angry** at any point → take a 30-min walk before the next response. Tired-and-angry comments survive forever on HN; hold the bar.

---

## What this timeline does NOT cover

- **Pre-launch outreach** to potential users / beta testers — out of scope; handled separately via `docs/internal/poc/p5_beachhead/RECRUITMENT_PLAN.md`.
- **Investor outreach** — out of scope; the Mo 24 decision gate (ADR-002 §8.3) is the right time to start that conversation, not launch day.
- **Press / journalist outreach** — out of scope for v0.2; we are not a press story yet. Revisit at v0.5+ when there are external users to quote.
- **YouTube / podcast appearances** — out of scope; the 60-sec demo MP4 is the only video asset for v0.2.

---

*If launch day deviates from this plan in a way worth remembering, log it in `post_mortem_v0.2.0.md` so v0.3 launch starts from a better baseline. Last updated 2026-05-15.*
