# PoC #5 — Tester Scenario

> Verbatim instructions given to each tester. Read aloud at session start,
> then handed as a printed / PDF page. Plain data-engineering vocabulary
> only — no Nucleus-specific jargon. The point of PoC #5 is that strangers
> understand the product without prior context.

## What you're doing

You're a new data engineer at a fictitious 10-person startup. You've been
asked to ingest a Postgres `orders` table into Iceberg and produce a
BI-ready aggregate that the team's analyst can query.

You have:

- A fresh laptop (we provide via Tailscale share OR your own MacBook with
  a clean Python environment).
- Postgres credentials for a source DB pre-loaded with ~10K `orders` rows
  (`id`, `customer_id`, `amount`, `created_at`).
- An S3 bucket OR local MinIO container (your choice — credentials in the
  env file we share).
- The Nucleus repo URL: `https://github.com/<org>/nucleus`.
- 90 minutes on the clock (the target is 30 min — 90 is buffer; we will
  not stop you early).
- **No founder available to answer Nucleus questions.** Note them in the
  shared Google Doc; we'll go through them at the end.
- A shared Google Doc to record every question / blocker / surprise.

## Acceptance — when you're done

You're done when **all three** are true:

1. A query like
   `SELECT date, count(*), sum(amount) FROM analytics.orders_daily GROUP BY date`
   returns rows from your machine.
2. The Iceberg snapshot is committed (the Nucleus CLI confirms it).
3. You feel reasonably confident this would survive a Monday morning
   (subjective — we want your honest gut check).

## NOT in scope (don't try)

- Deploying to cloud (laptop only for this session).
- Multi-user / RBAC / authentication.
- The Workbench web UI (CLI + SDK only for v0.1).
- AI Copilot.
- Scheduling / cron / backfills.
- Backfilling history beyond what `nucleus ingest` produces by default.

## During the session

- **Think aloud.** Narrate what you're trying, what you expect, what
  surprises you. The think-aloud track is more valuable than the wall
  clock.
- **Note every confusion** in the shared Doc, with the rough time stamp.
  Examples we want: *"what does X mean?"*, *"I expected Y but got Z"*,
  *"this isn't what I thought"*, *"why is this hard?"*
- **Quit any time.** You're paid in full either way. We learn more from
  honest abort than from forced completion.

## Before you start the hands-on portion

We will show you a single paragraph of marketing copy and ask:
**"What does this tool do, in your own words?"** Answer in 1-2 sentences
based on the paragraph alone. There's no right answer — we want your
first read.

## After the session

We will ask you the following questions; please give honest answers:

1. **Rate (1-5)**: *"Would you use this for a real project?"*
2. **Open-text**: *"What was the worst friction you hit?"*
3. **Open-text**: *"What was the best surprise?"*
4. **Open-text**: *"What's missing for this to be Monday-ready?"*
5. *Optional*: any other feedback, especially on the docs / error
   messages / vocabulary.

## Compensation

$<amount> via Wise / Wire / Stripe within 7 days regardless of completion
outcome. You owe us nothing if you abort early — partial data is still
valuable.

## Recording

This session is screen + audio recorded with your consent (signed form
before the call). Recordings are retained for 90 days, then transcript-only,
and never shared outside the founding team without your separate
opt-in.
