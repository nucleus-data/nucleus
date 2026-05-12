# SETUP — Your first session

> **Audience**: You (the solo founder), on Windows 11.
> **Time**: 30-60 minutes the first time. <2 minutes every session after.
> **Goal**: By the end, you can run `pytest` and see green checkmarks.

This is **the** first doc to follow. It walks you from "nothing installed" to "tests passing".

If anything breaks, paste the error and tell me what step you were on.

---

## §1. Install Python

You currently have the Windows Store stub for `python` (not real Python). You need an actual install.

**Recommended: install via winget** (Windows Package Manager, comes with Win 11):

```powershell
# Open PowerShell. Type:
winget install Python.Python.3.12
```

If `winget` is not available, download Python 3.12 from https://www.python.org/downloads/windows/ — pick the latest 3.12.x stable installer. **During install, check "Add Python to PATH"**.

### Disable the Microsoft Store alias

After installing real Python, prevent the Store stub from intercepting `python.exe`:

1. **Start menu** → search "Manage app execution aliases" → open it.
2. Turn **OFF** the toggles for `python.exe` and `python3.exe`.

### Restart PowerShell and verify

Close ALL open PowerShell windows. Open a new one. Verify:

```powershell
python --version
# Expected:  Python 3.12.x   (NOT the Microsoft Store stub message)

py -3.12 --version
# Expected:  Python 3.12.x
```

If you still see the Microsoft Store message, the PATH isn't picking up the real install. Try:
- Search "Edit the system environment variables" → check PATH includes `C:\Users\<you>\AppData\Local\Programs\Python\Python312\` AND `C:\Users\<you>\AppData\Local\Programs\Python\Python312\Scripts\`.
- Or reboot. PowerShell sometimes caches PATH aggressively.

---

## §2. Set up the project's virtual environment

A virtual environment ("venv") gives each project its own isolated Python install. Keeps dependencies sane.

```powershell
# Navigate to the project (you're likely already here):
cd <path\to\your\nucleus\clone>

# Create the venv (this folder is gitignored):
python -m venv .venv

# Activate it. PowerShell syntax:
.\.venv\Scripts\Activate.ps1
```

### If activation is blocked by PowerShell execution policy

You may see:
```
.venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled on this system.
```

Fix it once, for your user only (safe):

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Answer **Y** when prompted. Now retry the `Activate.ps1` line.

### Confirm the venv is active

Your prompt now shows `(.venv)` at the front. Verify:

```powershell
python -c "import sys; print(sys.executable)"
# Expected path includes ...\Mordern Data Platform\.venv\Scripts\python.exe
```

**Important**: Every new PowerShell window starts fresh. Re-activate with `.\.venv\Scripts\Activate.ps1` before each work session.

---

## §3. Upgrade pip and install dev dependencies

The first install pulls ~50 packages (about 250 MB). Takes 3-5 min on a normal connection.

```powershell
python -m pip install --upgrade pip

# Install nucleus in editable mode WITH dev extras.
# Editable (-e .) means: changes to src/ are picked up immediately,
# no reinstall needed.
pip install -e ".[dev]"
```

### If this fails with version conflicts

Some pinned versions in `pyproject.toml` may not exist on PyPI yet (they're targets I picked based on knowledge of recent releases — they might be slightly off).

Quick diagnosis:

```powershell
# This command tells pip to print what it's resolving:
pip install -e ".[dev]" --dry-run -v 2>&1 | Select-String -Pattern "version|not found"
```

If you see "no matching distribution found" for a package, tell me which one and the message — we'll bump that single line in `pyproject.toml`.

**This is expected. Catching pinning drift is exactly what `scripts/check_pinning.py` is for.**

### If a package install hangs

Some packages (`pyarrow`, `polars`) have large wheels. First install can take a minute per package. Be patient.

---

## §4. Run the constraint scripts

These are the 5 scripts we wrote yesterday. They enforce AGENTS.md rules.

```powershell
# (Make sure .venv is still active.)

python scripts/check_pinning.py
python scripts/check_layering.py
python scripts/dagster_leak_check.py
python scripts/check_vocabulary.py
python scripts/loc_budget.py --report
```

### Expected results

| Script | Expected | What if not |
|--------|----------|-------------|
| `check_pinning.py` | **FAIL or PASS depending on if compatibility.md matches pyproject.toml** | If FAIL with mismatches, that's our first real fix opportunity — see §7 |
| `check_layering.py` | **PASS** — only NucleusError code exists, no layer violations | If FAIL, share the output |
| `dagster_leak_check.py` | **PASS** — no Dagster imports yet | If FAIL, share the output |
| `check_vocabulary.py` | May **FAIL** on legitimate uses in docs | See §7 — add inline exemptions |
| `loc_budget.py --report` | Shows ~250 LOC (NucleusError + logging + cli stub) | Should fit easily under 8000 v0.1 ceiling |

### Don't worry if some fail

The point of building this tooling first is to catch issues *before* writing 1000 lines of code. Each failure has a fix — we'll work through them.

---

## §5. Run the test suite

Now the actual moment of truth — **does our `NucleusError` code work?**

```powershell
pytest -v
```

Expected output:
```
tests/test_errors.py::TestThreeFieldContract::test_minimal_construction PASSED
tests/test_errors.py::TestThreeFieldContract::test_explicit_docs_url_wins_over_default PASSED
... (about 20 tests)
tests/test_errors.py::test_top_level_nucleus_exports_nucleus_error PASSED

============= 20 passed in 0.5s =============
```

**If they all pass: your tooling is fully working. You're now a Nucleus developer.**

If some fail, paste the failing test names + their error messages. Likely causes:
- Python version mismatch (must be 3.11 or 3.12)
- Editable install didn't pick up `src/nucleus/`
- An import error chain (`structlog` not installed)

---

## §6. (Optional but recommended) Install pre-commit hooks

`pre-commit` runs the same checks locally before each git commit. It catches problems before you push.

```powershell
# Initialize git first if you haven't:
git init
git add -A
git commit -m "chore: initial scaffolding (Pre-Heartbeat)"

# Then install the hooks:
pre-commit install
```

Now every `git commit` runs ruff, mypy, and our constraint scripts on the changed files.

To run all hooks on all files (useful first time):

```powershell
pre-commit run --all-files
```

Expect this to take 30-60s the first time (it builds isolated environments for each hook). Subsequent runs are <5s.

---

## §7. Common fixes for first-run issues

### `check_pinning.py` reports "matrix_mismatches"

This means a pinned version in `pyproject.toml` doesn't match the version listed in `docs/compatibility.md`. They were authored sequentially; small drift is expected.

**Fix**: Decide which version is correct (typically the actual installed one), then update the other doc to match. Tell me which package and I'll patch both.

### `check_pinning.py` reports "no matching distribution"

A pinned version doesn't exist on PyPI. (My version guesses may be slightly off.)

**Fix**: Run:
```powershell
pip index versions <package_name>
```
Pick a real version near my guess. Edit `pyproject.toml`, run `pip install -e ".[dev]"` again.

### `check_vocabulary.py` reports hits in docs

We have docs that legitimately use words like "data lake" or "metastore" in discussion (e.g., explaining why we don't use them).

**Fix**: Add an inline exemption marker on the offending line:
```
... we don't use the term "metastore" because... <!-- banned-term: metastore -->
```

The script will skip lines containing that marker.

### `pytest` fails with `ModuleNotFoundError: No module named 'nucleus'`

The editable install didn't register. Run:
```powershell
pip install -e ".[dev]"
```
again, then retry `pytest`.

### `mypy` complains about missing stubs for `structlog`

Some libs don't ship type stubs. Add an override in `pyproject.toml`'s `[[tool.mypy.overrides]]` if it blocks you.

---

## §8. Daily workflow (after first-time setup)

Once §1-§5 is done, each session is just:

```powershell
# Open the project
cd <path\to\your\nucleus\clone>

# Activate the venv
.\.venv\Scripts\Activate.ps1

# Pull latest if you have a remote (later, when we set up GitHub)
# git pull

# Make changes...

# Before committing:
make ci  # if you installed GnuWin32 make
# OR run individually:
python scripts/check_pinning.py
python scripts/check_layering.py
python scripts/dagster_leak_check.py
python scripts/check_vocabulary.py
python scripts/loc_budget.py --report
ruff check .
ruff format --check .
mypy
pytest

# Commit
git add -A
git commit -m "feat(ctx): describe what you changed"
```

If you installed pre-commit hooks (§6), most of these run automatically on commit.

---

## §9. What's next after setup

Once `pytest` is green:

1. **Read [`docs/onboarding/learning_path.md`](docs/onboarding/learning_path.md)** — your personalized module ladder.
2. **Start M0** of the learning path (~10-15 hrs over 1-2 weeks).
3. **In parallel**, read `src/nucleus/errors.py` and `tests/test_errors.py` end-to-end. Understand what it does and why. This is your first real code reading.
4. When M0 is done and you've absorbed `errors.py`, **come back and ask me to continue with Day 3** (security threat model + research docs) OR jump to Tier 0 implementation.

There is no rush.

---

## §10. Asking me for help

If you get stuck, just say:

> "On SETUP.md step §X.Y, I see this error: [paste]"

I have the full context of every file we created. I can usually diagnose in one round-trip.

For unfamiliar Windows error messages, prefer to copy them verbatim (not paraphrase). Tracebacks and error codes carry the diagnostic info I need.

---

*This file is yours to edit. As you hit gotchas, add fixes here. Future-you will thank present-you.*
