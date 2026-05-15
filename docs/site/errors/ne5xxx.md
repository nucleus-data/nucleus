---
title: NE5xxx — Experience Layer Errors
description: Errors from the Experience layer — CLI, SDK, Workbench, scheduling.
---

# NE5xxx — Experience Layer Errors

Errors from the Experience layer — CLI, SDK, Workbench, and scheduling (architecture v4.1 §8).

---

## NE5001 — NucleusConfigError {#ne5001}

Configuration error in `nucleus_project.yaml` or environment.

**Fix:** Check the error message for the specific field. Validate your YAML:

```bash
python -c "import yaml; yaml.safe_load(open('nucleus_project.yaml'))"
```

---

## NE5002 — NucleusDockerUnavailable {#ne5002}

Docker Desktop is not running or not reachable.

**Fix:**
```bash
# macOS / Windows: open Docker Desktop from Applications
# Linux:
sudo systemctl start docker
docker ps   # should list containers without error
```

---

## NE5003 — NucleusPortBound {#ne5003}

Port 9000 or 9001 is already in use.

**Fix:**
```bash
# Find what's using the port
# macOS / Linux:
lsof -i :9000

# Windows (PowerShell):
netstat -ano | findstr :9000

# Stop the conflicting process, then:
nucleus up
```

---

## NE5005 — NucleusScheduleParseError {#ne5005}

Invalid cron expression in a `schedule=` parameter.

**Fix:** Validate your cron expression. The expression must be 5 space-separated fields:

```
MIN HOUR DOM MON DOW
  │    │   │   │   └── day of week (0-7, Sunday = 0 or 7)
  │    │   │   └────── month (1-12)
  │    │   └────────── day of month (1-31)
  │    └────────────── hour (0-23)
  └─────────────────── minute (0-59)
```

Valid examples: `"0 2 * * *"` (2 AM daily), `"0 */6 * * *"` (every 6 hours). Or use presets: `"@daily"`, `"@hourly"`, `"@weekly"`.

---

## NE5006 — NucleusScheduleNotFoundError {#ne5006}

Asset key not found or has no `schedule=` declared.

**Fix:** Ensure the asset exists and has `schedule=` in its decorator:

```bash
nucleus schedule list   # shows all scheduled assets
```

---

## NE5008 — NucleusFeatureDeferredError {#ne5008}

A feature was requested that is not yet available in this version.

**Includes:**
- `nucleus schedule on/off/trigger` (v0.2)
- `nucleus workbench` (v0.2)
- `nucleus chat` when called in v0.1

**Fix:** Check the error message for the workaround. Usually `nucleus run <key>` is the manual alternative. See [Roadmap](../community/roadmap.md) for when the feature ships.
