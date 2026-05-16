# 01 — Developer Onboarding

> **What you're doing**: Setting up a complete Nucleus development environment from scratch.
> **Why it matters**: A broken dev environment causes mysterious test failures and wastes hours. This guide ensures your first run is clean.
> **Time**: 30-45 minutes

---

## Prerequisites

Before starting, verify you have:

| Requirement | Version | Check command |
|---|---|---|
| Python | 3.11.x or 3.12.x | `python --version` |
| Git | 2.x | `git --version` |
| Docker + Docker Compose v2 | Docker 24+ | `docker --version` |
| Free disk space | ≥ 10 GB | `df -h .` (Linux/Mac) / `Get-PSDrive C` (Windows) |
| Internet access | For PyPI + Docker Hub | `ping pypi.org` |

**Note**: Docker is required for `nucleus up` (local stack: MinIO + catalog). If Docker is unavailable, you can run most unit tests but not the full beachhead E2E.

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/<org>/nucleus.git
cd nucleus
```

If behind a corporate proxy (e.g., Bosch APAC), set:
```bash
export HTTPS_PROXY=http://your-proxy:8080
export HTTP_PROXY=http://your-proxy:8080
```

---

## Step 2: Create a Virtual Environment

```bash
# Python 3.11 or 3.12 required
python -m venv .venv
```

**Important**: do NOT use the `.venv` that may already be in the repo (it was created for the founder's machine). Always create a fresh one.

---

## Step 3: Activate the Virtual Environment

**Windows (PowerShell)**:
```powershell
.venv\Scripts\Activate.ps1
# If blocked by execution policy:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\Activate.ps1
```

**Mac / Linux (bash/zsh)**:
```bash
source .venv/bin/activate
```

After activation, your prompt should show `(.venv)`.

---

## Step 4: Install the Package

```bash
# Install Nucleus with all development dependencies
pip install -e ".[dev,docs]"
```

This installs:
- Nucleus itself (editable mode — changes to `src/nucleus/` take effect immediately)
- All runtime dependencies (exact pinned versions per `pyproject.toml`)
- Dev tools: ruff, mypy, pytest, pre-commit

**Expected output**: No errors. The final lines should resemble:
```
Successfully installed nucleus-0.1.0 ...
```

---

## Step 5: Smoke Test — CLI

```bash
nucleus --version
```

Expected: `nucleus 0.1.0`

If this fails with `command not found`:
- Verify `.venv` is activated
- Try: `python -m nucleus.cli.main --version`

---

## Step 6: Run the Baseline Test Suite

```bash
python -m pytest tests/ -q --tb=short
```

Expected: some tests pass, some may skip (for features requiring Docker or live services). **Zero failures** is the goal; skips are acceptable.

If failures appear: check whether they are pre-existing (check `docs/internal/FOUNDER_ACTION_QUEUE.md`) or caused by your environment. If new, stop and investigate before proceeding.

---

## Step 7: Run the Beachhead E2E

```bash
python scripts/beachhead_e2e.py
```

Expected output: `8/8 PASS — boot < 10 s`.

This requires Docker to be running. If Docker is unavailable, some gates skip automatically with `SKIP` markers.

---

## Step 8: Run Governance Scripts (Baseline Check)

```powershell
python scripts/check_vocabulary.py
python scripts/check_pinning.py
python scripts/loc_budget.py
python scripts/dagster_leak_check.py
```

All should EXIT 0. If any fails with a pre-existing violation, document it before your first PR — you shouldn't break something that was already broken.

---

## Step 9: Install Pre-commit Hooks (Recommended)

```bash
pip install pre-commit
pre-commit install
```

After this, `git commit` automatically runs ruff + vocabulary checks before accepting the commit. Saves CI round-trips.

---

## Step 10: Open in Cursor / VS Code

```bash
cursor .   # or: code .
```

Recommended extensions (VS Code):
- Python (Microsoft)
- Ruff (Astral)
- Pylance

Cursor users: the project includes `.cursor/rules/nucleus.mdc` (auto-applied to all Cursor sessions) and `.cursor/agents/` (custom subagent definitions). Read them to understand how AI assistance is configured.

---

## Step 11: Read the Mandatory Docs

In order:
1. `AGENTS.md` (30 min) — the universal law of this repo
2. `docs/roadmap/overview.md` (10 min) — version timeline
3. `docs/specs/nucleus_architecture_v4.1.md` (50 min) — architectural bible

Do not write any code until you've read at least `AGENTS.md`.

---

## Step 12: Pick Your First Task

Good starting points:
- GitHub Issues labeled `good-first-issue`
- Items in `docs/internal/FOUNDER_ACTION_QUEUE.md` §"Optional polish" (E5.x items)
- Documentation improvements in `docs/site/`

Avoid first-PR edits to:
- `src/nucleus/coordination/error_translation.py` (complex error translation logic)
- `src/nucleus/ctx/__init__.py` (public API surface — freeze policy applies)
- Any `scripts/check_*.py` governance script

---

## Common Gotchas

### Corporate proxy blocks Docker pull
```powershell
# In Docker Desktop settings: Settings → Resources → Proxies
# Add: HTTP Proxy = http://your-proxy:8080
# HTTPS Proxy = https://your-proxy:8080
```

### Python version mismatch
If `nucleus --version` works but tests fail with syntax errors, check:
```bash
python --version  # must be 3.11.x or 3.12.x
which python      # must point to .venv/bin/python
```

### PowerShell execution policy (Windows)
```powershell
# Run as Administrator if needed:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### `pip install -e ".[dev,docs]"` fails with `wheel build error`
- Some packages (psycopg[binary]) need build tools on Linux: `sudo apt install libpq-dev python3-dev build-essential`
- On Mac: `brew install libpq`
- On Windows: psycopg binary wheel handles this automatically

### Docker not starting on Windows (WSL2 required)
- Enable WSL2: `wsl --install`
- Install Docker Desktop with WSL2 backend enabled

---

## Verification

After completing all steps:

```
[ ] nucleus --version prints 0.1.0 (or later)
[ ] pytest tests/ -q shows 0 failures
[ ] scripts/beachhead_e2e.py shows 8/8 PASS (or SKIP for Docker-unavailable steps)
[ ] All 4 governance scripts EXIT 0
[ ] Pre-commit hooks installed and pass on test commit
```

---

## Rollback

If you need to start fresh:
```bash
deactivate                    # exit virtual env
rm -rf .venv                  # delete venv
# Re-run from Step 2
```

---

## References

- Python: https://www.python.org/downloads/
- Docker Desktop: https://www.docker.com/products/docker-desktop/
- `AGENTS.md §11.4` — per-feature workflow
- `docs/roadmap/HANDOVER.md` — overview for new contributors
