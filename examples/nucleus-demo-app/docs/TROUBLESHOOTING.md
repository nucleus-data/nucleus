# Troubleshooting — Nucleus demo app

Every error a first-time visitor is likely to hit, with the exact fix.
Errors are organised top to bottom by frequency.

---

## "command not found: nucleus"

You have not installed Nucleus in your active Python environment. From
the repository root:

```bash
pip install -e ".[dev]"
```

Then re-open your shell so `nucleus` is on `PATH`. Verify with
`nucleus version`.

---

## "No `nucleus_project.yaml` found in the current directory or its parents."

Run the command from inside `examples/nucleus-demo-app/` (or any
subdirectory of it). The CLI walks up to three levels looking for
`nucleus_project.yaml`.

```bash
cd examples/nucleus-demo-app
nucleus up
```

---

## `nucleus up` reports "Local storage did not report ready within 30 seconds."

MinIO never came up. Check the compose stack:

```bash
docker compose ps
docker compose logs minio
```

Common causes:

* Port `9100` or `9101` already used by another container — change the
  `ports:` mapping in `docker-compose.yaml` and rerun `nucleus up`.
* Docker Desktop not running — start it, then re-run.
* Anti-virus or VPN blocking the bridge network — temporarily disable
  to confirm.

---

## `nucleus up` exits with "compose runner not found"

Docker is not on `PATH`, or `docker compose` is not installed. Either:

* Install Docker Desktop (which ships `docker compose v2`), or
* Install the standalone `docker-compose` binary; the CLI auto-detects
  either.

---

## `python scripts/seed_postgres.py` fails with `connection refused`

Postgres is not yet ready. Wait a few seconds after `nucleus up` and
retry, or check:

```bash
docker compose ps postgres
docker compose logs postgres | tail -n 20
```

If the log shows `database system is ready to accept connections`,
re-run the seed script. If it shows a port conflict, the host port
`5433` is busy — pick another port in `docker-compose.yaml`.

---

## `nucleus run silver.daily_revenue` raises `NucleusAssetNotMaterialized (NE3003)`

You ran a downstream asset before its bronze upstream. v0.1 does not
auto-materialize upstreams. Run the bronze asset first:

```bash
nucleus run bronze.orders
nucleus run silver.daily_revenue
```

The full dependency order is in the README. Auto-upstream-materialize
ships in v0.2.

---

## `nucleus run bronze.orders` raises `NucleusSourceConnectionError (NE1001)`

`ctx.copy_from` could not reach Postgres. Most often:

* You forgot `nucleus up` — start the stack first.
* Postgres is bound to a different port — confirm with
  `docker compose port postgres 5432`.
* Custom URL — check `assets/_common.py` `POSTGRES_URL` (override
  via the `NUCLEUS_DEMO_POSTGRES_URL` env var).

---

## `nucleus run bronze.orders` raises `NucleusSourceNotFound (NE1008)`

Postgres is up but the table does not exist yet. Run the seed script:

```bash
python scripts/seed_postgres.py
```

---

## "Iceberg schema mismatch" after editing a SQL file

If you change a silver/gold SQL output schema in a way that conflicts
with the existing Iceberg metadata, the next materialization will refuse
to commit. Easiest fix during the demo: nuke the warehouse and
rebuild from scratch.

```bash
bash scripts/reset_demo.sh
nucleus up
python scripts/seed_postgres.py
nucleus run bronze.orders         # … and continue down the dependency order
```

The "production" answer is `nucleus snapshot` branching + a controlled
schema-evolution change — see `nucleus snapshot --help` once
`bronze.orders` exists.

---

## `nucleus query` raises `NucleusAssetNotFound (NE3002)`

The `{{ ref('schema.name') }}` argument does not match any registered
Iceberg table. The query message includes a "did you mean…" hint. The
two most common slips:

* Typo in the asset key. Double-check the spelling in `assets/`.
* You forgot to materialize that asset. Run
  `nucleus run <namespace>.<name>` first, then re-run the query.

---

## Workbench UI says "no assets found"

Two checks:

1. You haven't materialized anything yet — run a `nucleus run` cycle
   from the README.
2. The Workbench is pointing at the wrong project root. Run it from
   inside `examples/nucleus-demo-app/`.

---

## "I changed `assets/_common.py` and nothing happened"

Asset modules are imported on every CLI invocation, so a Python edit is
picked up the next time you run `nucleus run <key>` — no daemon to
restart. If your edit changed the asset key string, the old key remains
in the catalog under its previous name; either rename it via
`nucleus snapshot rename` (when shipped) or wipe with
`bash scripts/reset_demo.sh`.

---

## "How do I increase the seed volumes?"

Edit `scripts/generate_seed.py`:

```python
N_CUSTOMERS = 1_000        # try 10_000
N_PRODUCTS  =   500        # try 5_000
N_ORDERS    = 10_000       # try 1_000_000
```

Re-run `python scripts/generate_seed.py`, then re-seed Postgres and
re-materialize the bronze layer. The silver and gold assets work
unchanged at any volume.

---

## Still stuck?

Open an issue at <https://github.com/nucleus-data/nucleus/issues>. Please
include:

* `nucleus version --format json`
* `docker compose ps`
* The full command and the full error output (Nucleus errors include
  a `Docs:` URL in the third line — paste that too).
