"""PoC #3 — ``nucleus ingest`` one-liner (SQLite → filesystem Iceberg).

See ``docs/specs/nucleus_poc_plan.md`` §3 for the full spec and acceptance criteria.
This package contains throw-away validation code; the production version
will live in :mod:`nucleus.ctx.copy_from` (~200 LOC per the plan) only
after PoC #3 passes.
"""
