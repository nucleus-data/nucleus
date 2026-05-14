# PoC #5 Beachhead Validation — Tester Scenario

**Time budget**: 30 minutes (hard cap, no extensions).
**Goal**: A first-time tester reaches a BI-ready Iceberg table starting from `git clone`.
**Persona**: 0-2 years data engineering experience, MacBook / Linux laptop, Python 3.11 installed.

> Success metric per [`AGENTS.md` §11.8](../../../AGENTS.md) + [`nucleus_architecture_v4.1.md` §1.5](../../../nucleus_architecture_v4.1.md): 5-engineer startup team, `git clone` → BI-ready Iceberg table in **<30 minutes**. PoC #5 tests a single-tester subset of that promise on the SQLite → filesystem-Iceberg path validated by PoC #3 (Postgres + S3 path is v0.3+ scope).

> **State as of 2026-05-13**: `nucleus init` ships live; `nucleus ingest` / `nucleus query` / `nucleus run` are expected live before recruitment opens; `nucleus up` / `nucleus down` remain stubs and the tester will use `docker compose up -d` directly. Re-verify against [`docs/onboarding/quickstart.md`](../../onboarding/quickstart.md) the morning sessions begin — abort PoC #5 if any in-scope command is still a stub.

---

## Setup (5 min — clock starts here)

1. Open a fresh terminal. Confirm prerequisites:

   ```bash
   python3.11 --version    # expect 3.11.x
   docker --version
   git --version
   ```

2. Clone the repo and create a virtual environment:

   ```bash
   git clone https://github.com/nucleus-data/nucleus.git
   cd nucleus
   python3.11 -m venv .venv
   source .venv/bin/activate          # macOS / Linux
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   ```

3. Install Nucleus in editable mode:

   ```bash
   pip install -e ".[dev]"
   ```

4. Smoke-check the install:

   ```bash
   nucleus version
   ```

   Expected: a version string. Any error → log to `FEEDBACK_FORM.md` and proceed.

## Beachhead path (20 min)

Reference recipe: [`docs/recipes/sqlite_to_iceberg.md`](../../recipes/sqlite_to_iceberg.md). You **may not open the recipe during the test** — it is the founder-side reference, not yours. The steps below are the only path you should follow.

5. Boot the local storage substrate (SeaweedFS via Docker):

   ```bash
   docker compose up -d
   ```

   `nucleus up` is a stub at v0.1 start; `docker compose` is the supported substitute per [`quickstart.md`](../../onboarding/quickstart.md) Step 4.

6. Create a fresh Nucleus project in a sibling directory:

   ```bash
   cd ..
   nucleus init beachhead-test
   cd beachhead-test
   ```

7. Prepare a tiny SQLite source (5 rows is enough — the point is the flow, not the volume):

   ```bash
   sqlite3 sales.db <<'SQL'
   CREATE TABLE customers (id INTEGER PRIMARY KEY, email TEXT NOT NULL,
                           signup_ts TEXT NOT NULL, ltv REAL NOT NULL DEFAULT 0);
   INSERT INTO customers VALUES
     (1,'a@example.com','2026-01-05T08:23:00Z',  49.99),
     (2,'b@example.com','2026-01-12T11:09:00Z', 120.00),
     (3,'c@example.com','2026-02-03T16:42:00Z',   0.00),
     (4,'d@example.com','2026-02-19T09:55:00Z',  12.50),
     (5,'e@example.com','2026-03-08T14:30:00Z',1234.56);
   SQL
   ```

8. Ingest into Iceberg:

   ```bash
   nucleus ingest sqlite:///./sales.db --table customers --as raw.customers
   ```

   Expected: a confirmation that `raw.customers` was created and a snapshot was committed.

## Validation (5 min)

9. Query the new asset:

   ```bash
   nucleus query "SELECT count(*), min(signup_ts), max(signup_ts) FROM raw.customers"
   ```

   Expected: `5 | 2026-01-05T08:23:00Z | 2026-03-08T14:30:00Z`.

10. You are **done** when step 9 returns the expected row OR the 30-minute timer expires — whichever arrives first.

## Friction logging

Open [`FEEDBACK_FORM.md`](./FEEDBACK_FORM.md) in a separate editor **before** the timer starts. Every single piece of friction is logged in the table with `Time elapsed | Step | Friction (what / why / would-you-quit?)`. Examples of what counts as friction: a typo in any command output, a confusing error message, a step that took longer than expected, a moment where you thought "I'd give up here in a real job", a missing assumption (e.g. "the README didn't say I needed Docker"). Log it. Don't filter.

## Hard rules for testers

- You **cannot** ask the founder questions during the 30 minutes — log the question instead.
- You **cannot** read PRs, commits, design docs, or architecture files (only this scenario + the FEEDBACK form).
- You **cannot** use AI assistants (Cursor, Copilot, ChatGPT, Claude, Gemini, etc.) during the test — they paper over the friction we are trying to surface.
- All friction (typos, errors, confusion, dead-ends, "I'd quit here" moments) **MUST** be logged.
- The test ends at 30:00 OR when step 9 returns the expected row — whichever is first. No extensions; the cap is the metric.
