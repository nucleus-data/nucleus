---
title: Common Errors
description: The most frequent NE-errors and their quick fixes.
---

# Common Errors

## `nucleus up` hangs or fails

**Symptom:** `nucleus up` waits for more than 30 seconds, or fails with NE5002.

```
Error: Docker Desktop is not available.
Fix:   Start Docker Desktop and retry 'nucleus up'.
       [NE5002]
```

**Fix:** Open Docker Desktop (or run `sudo systemctl start docker` on Linux). Wait for the whale icon to turn steady (not animating). Then retry `nucleus up`.

---

## `nucleus run` fails with NE1001

```
Error: Could not reach source 'postgres://...'. Connection refused.
       [NE1001]
```

**Fix:**
1. Verify the database is running: `docker ps | grep postgres`
2. Test the connection: `psql <connection_string> -c "SELECT 1"`
3. Check firewall / VPN isn't blocking port 5432
4. Verify credentials match what's in your `.env` or connection string

---

## `nucleus query` fails with NE3003

```
Error: Asset 'analytics.daily_revenue' is defined but has never been materialized.
Fix:   Run 'nucleus run analytics.daily_revenue' first.
       [NE3003]
```

**Fix:**

```bash
nucleus run analytics.daily_revenue
# Then retry:
nucleus query "SELECT * FROM {{ ref('analytics.daily_revenue') }} LIMIT 10"
```

---

## Contract violation (NE2001)

```
Error: Data does not match the declared schema for 'staging.orders'.
       Column 'order_date' has nulls but the contract declares not_null.
       [NE2001]
```

**Fix:**
1. Inspect the source data: `nucleus query --asset raw.orders`
2. Find the rows with null `order_date`
3. Either fix the source data, or update the contract to allow nulls
4. Re-run: `nucleus run staging.orders`

---

## `nucleus ingest` fails with NE1002 (commit conflict)

**Symptom:** Two `nucleus run` or `nucleus ingest` commands ran simultaneously.

**Fix:** Wait for any running process to finish, then retry. Check for stale processes:

```bash
# macOS / Linux
ps aux | grep "nucleus"
# Kill any stale processes
kill <pid>
```

---

## `nucleus up` port conflict (NE5003)

```
Error: Port 9000 is already in use.
Fix:   Stop the process using port 9000 and retry 'nucleus up'.
       [NE5003]
```

**Fix:**

```bash
# Find what's using port 9000
lsof -i :9000          # macOS / Linux
netstat -ano | findstr ":9000"  # Windows

# Stop it, then:
nucleus up
```

If another SeaweedFS/MinIO instance is running from a different project, run `nucleus down` in that project first.

---

## Concurrent runs on Windows (Beta Tier 2)

**Beta Tier 2** — v0.2.0 reliability caveat documented per `docs/internal/research/ultimate_upgrade/04_brutal_internal_audit.md` §7 F1; architectural fix tracked for **v0.2.1**.

**Symptom:** Two overlapping `nucleus run` sessions against the **same asset** can **both succeed** on **Windows**, each producing **its own Iceberg snapshot** instead of enforcing a strict single logical winner — a silent double-write hazard (**row count** / snapshot divergence).

**Evidence:** `docs/internal/benchmarks/2026-05-15_baseline.md` §B4 **Concurrent run safety** (**lines 148–152**).

**Workarounds (until v0.2.1):**

1. Serialize materializations (one **`nucleus run`** at a time).
2. Coordinate an **external lock** across shells or CI runners if parallelism is unavoidable.
3. Prefer **Linux** or **macOS** when overlapping materializations against one asset are required.
