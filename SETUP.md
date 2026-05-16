# SETUP — Your first session

> **Audience**:
> - **Founder** on Windows 11 — follow §1-§10 below.
> - **PoC #5 external testers** on macOS (Apple Silicon or Intel) — jump to [**`## macOS Setup`**](#macos-setup) (§M1-§M8) per [`poc/p5_beachhead/RECRUITMENT.md`](poc/p5_beachhead/RECRUITMENT.md) §scheduling: *"≥ 3 macOS, ≥ 1 Linux or Windows-WSL2"*.
>
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

We have docs that legitimately use words like "data lake" or "metastore" in discussion (e.g., explaining why we don't use them). <!-- banned-term: multiple -->

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

### Corporate HTTP_PROXY interception (Bosch and similar networks)

If `HTTP_PROXY` is set system-wide, S3 clients on Windows will fail to reach the local storage container (returns HTTP 407 indefinitely). Either:

- Pass `--noproxy "*"` to `curl.exe` and `wget`, OR
- Set `NO_PROXY=localhost,127.0.0.1` in the shell environment before launching `nucleus` commands or any S3 SDK (boto3, AWS CLI). In PowerShell: `$env:NO_PROXY = "localhost,127.0.0.1"`.

This affects only Windows-side clients; ingest code running inside WSL is unaffected because WSL has its own network namespace.

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

## macOS Setup

> **Audience**: PoC #5 external testers on macOS (Apple Silicon M1/M2/M3 or Intel x86_64) per [`poc/p5_beachhead/RECRUITMENT.md`](poc/p5_beachhead/RECRUITMENT.md) §scheduling. The founder runs Windows (§1-§10 above); macOS coverage is **mandatory** for PoC #5 — per [`poc/p5_beachhead/DESIGN.md`](poc/p5_beachhead/DESIGN.md) §"Status gate", *"`SETUP.md` instructions verified on the host OS the tester uses"* is a precondition.
>
> **Time**: 20-40 minutes the first time. <2 minutes per session after.
> **Goal**: Same as Windows — `pytest` green and `nucleus` CLI on `$PATH`, ready for the [`poc/p5_beachhead/SCENARIO.md`](poc/p5_beachhead/SCENARIO.md) 30-minute beachhead flow.

These macOS sections (§M1-§M8) **parallel** the Windows §1-§10 above; they do not replace them. OS-neutral steps (constraint scripts, test runs, pre-commit) reuse §4-§6 verbatim — only Python install (§M1), venv activation (§M2), and Docker (§M3) differ.

---

### §M1. Install Python 3.11 on macOS

[`pyproject.toml`](pyproject.toml) pins `requires-python = ">=3.11,<3.13"`. Pick **3.11** (matches `[tool.mypy] python_version = "3.11"` and `[tool.ruff] target-version = "py311"`). 3.12 also works but the founder pins 3.11 as the canonical CI version.

> ⚠️ **Do NOT use the system `python3`.** macOS ships a system Python (typically 3.9 on older macOS, 3.12+ on Sonoma/Sequoia). Mixing it with our pinned dev environment causes permission errors on `pip install` (system site-packages is owned by root) and silent version drift. **Always invoke `python3.11` explicitly** for venv creation; inside the venv, plain `python` is correct.

#### Option A — Homebrew (recommended for most testers)

```bash
# Install Homebrew first if missing (https://brew.sh):
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11:
brew install python@3.11
# NEEDS VERIFICATION: confirm exact formula name `python@3.11` against current
# Homebrew (run `brew search python@3` if uncertain). Past variants on older
# Homebrew releases included `python-3.11` and `python311`.

python3.11 --version
# Expected: Python 3.11.X  (X = current patch)

# If `python3.11` is not on PATH after install (PATH precedence on Apple Silicon
# vs Intel installs Homebrew at /opt/homebrew vs /usr/local respectively):
brew link python@3.11 --overwrite --force
```

#### Option B — Official python.org installer

1. Download from https://www.python.org/downloads/macos/ — pick the latest `Python 3.11.X` *macOS 64-bit universal2* installer (universal2 = single binary for Apple Silicon + Intel).
2. Run the `.pkg` installer; it installs to `/Library/Frameworks/Python.framework/Versions/3.11/`.
3. **macOS Gatekeeper** quarantine — first launch may require `xattr -d com.apple.quarantine "/Applications/Python 3.11/Install Certificates.command"`.
4. **SSL certificates** — run **once** after install or `pip install` fails with `SSL: CERTIFICATE_VERIFY_FAILED` against PyPI: `/Applications/Python\ 3.11/Install\ Certificates.command`.

#### Option C — pyenv (advanced; testers juggling multiple Python versions)

```bash
brew install pyenv
pyenv install 3.11.11   # NEEDS VERIFICATION: latest 3.11.x patch — run `pyenv install -l | grep 3.11`
pyenv local 3.11.11     # writes .python-version into the current dir
python3.11 --version    # → 3.11.11
```

---

### §M2. Set up the project's virtual environment

POSIX shell syntax — **different from the Windows PowerShell `Activate.ps1`** in §2 above.

```bash
# Navigate to the project clone:
cd ~/path/to/nucleus

# Create the venv (folder is gitignored):
python3.11 -m venv .venv

# Activate (zsh / bash — macOS default since Catalina is zsh):
source .venv/bin/activate
```

Your prompt now shows `(.venv)` at the front. Verify:

```bash
which python
# Expected: /<absolute path>/nucleus/.venv/bin/python
#   NOT /opt/homebrew/bin/python3.11   (Apple Silicon Homebrew)
#   NOT /usr/local/bin/python3.11      (Intel Homebrew)
#   NOT /usr/bin/python3               (system Python)

python -c "import sys; print(sys.executable)"
# Expected: same .venv path as above.
```

> ⚠️ **PATH precedence gotcha**: if `which python` shows the Homebrew path even after `source .venv/bin/activate`, your `~/.zshrc` is prepending Homebrew **after** activation runs. Fix: re-source the venv in a fresh shell (the issue is order-of-evaluation in your rc file), or temporarily `export PATH="$VIRTUAL_ENV/bin:$PATH"`.

Every new terminal starts fresh — re-run `source .venv/bin/activate` per session. Adding `cd ~/path/to/nucleus && source .venv/bin/activate` to a shell alias saves keystrokes.

---

### §M3. Install Docker Desktop on macOS

The v0.1 stack runs the storage substrate in Docker — currently MinIO `RELEASE.2025-09-07T16-13-09Z` (`sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e`, verified 2026-05-13) per [`docs/internal/research/minio.md`](docs/internal/research/minio.md) §2.1, with [`docs/decisions/ADR-008-storage-substrate-v01.md`](docs/decisions/ADR-008-storage-substrate-v01.md) (PROPOSED) introducing SeaweedFS as the dual-track default. Either way, you need a Docker daemon; on macOS that means Docker Desktop.

> **Storage substrate**: As of [ADR-008](docs/decisions/ADR-008-storage-substrate-v01.md) (2026-05-13), `docker-compose.yml` at repo root defaults to **SeaweedFS** (Apache-2.0, actively maintained). The archived MinIO release (`RELEASE.2025-09-07T16-13-09Z`, AGPLv3, upstream archived 2026-04-25) lives in `docker-compose.minio.yml` for opt-in use. `docker compose up` picks the default; `docker compose -f docker-compose.minio.yml up` picks the alternate. Iceberg byte path is identical; no application-layer code change.

#### Install

```bash
brew install --cask docker
# NEEDS VERIFICATION: Cask name `docker` vs `docker-desktop` (Homebrew renamed
# circa 2024-2025; `brew search --casks docker` to confirm).
```

OR download the `.dmg` from https://www.docker.com/products/docker-desktop/ (URL NEEDS VERIFICATION; Homebrew Cask is more reliable). After install, **launch Docker Desktop from `/Applications`** — the daemon does not autostart on first install. The whale icon appears in the menu bar when ready.

#### Apple Silicon vs Intel

Docker Desktop auto-pulls the correct architecture (arm64 for Apple Silicon, amd64 for Intel) when both manifests exist. Confirm a pulled image's arch with `docker inspect <image> | grep Architecture` — expected `arm64` or `amd64`. If only `amd64` is published, the image runs under **Rosetta 2** emulation (slower, higher RAM). Per [`docs/internal/research/minio.md`](docs/internal/research/minio.md) §3.2 the MinIO upstream archived 2026-04-25, so the pinned `RELEASE.2025-09-07T16-13-09Z` will not receive future arm64 manifests — see §M8 #2 for the PoC #5 implication. **NEEDS VERIFICATION** on Apple Silicon arch availability for that exact tag, and on the SeaweedFS pin once [ADR-008](docs/decisions/ADR-008-storage-substrate-v01.md) accepts.

#### Resource limits

Docker Desktop → Settings → Resources:

| Setting | Minimum | Recommended |
|---|---|---|
| Memory | 4 GB | 8 GB (room for storage container + Postgres source + DuckDB workspace) |
| CPUs | 2 | 4 |
| Disk image size | 32 GB | 64 GB |

Per [`poc/p4_boot_time/DESIGN.md`](poc/p4_boot_time/DESIGN.md) the `nucleus up` cold-start budget is **<10s**; the 4 GB / 2 CPU floor inflates container start time and risks blowing it.

#### Verify Docker

```bash
docker --version            # → Docker version 24.0+ (older Desktop ships 23.x; upgrade)
docker compose version      # → v2.20+ (note: `docker-compose` V1 standalone is deprecated;
                            #          always use `docker compose` with a space)
docker run --rm hello-world # → "Hello from Docker!" — confirms the daemon is reachable
```

---

### §M4. Upgrade pip and install dev dependencies

Same flow as Windows §3 — only the activation differs (POSIX, not PowerShell). Inside the activated venv:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

The `[dev]` extra pulls `ruff`, `mypy`, `pytest`, `pre-commit`, `testcontainers`, `hypothesis`, and the `pytest-{cov,xdist,asyncio}` plugins per [`pyproject.toml`](pyproject.toml) `[project.optional-dependencies] dev`. First install pulls ~50 packages (~250 MB); 3-5 min on a typical connection. `pyarrow` and `polars` wheels are large — 30-60 s each on slow links.

If pinning conflicts surface, the diagnosis from Windows §3 *"If this fails with version conflicts"* applies on macOS — only the shell-pipe syntax changes:

```bash
pip install -e ".[dev]" --dry-run -v 2>&1 | grep -E "version|not found"
# (Use `grep -E` instead of PowerShell `Select-String`.)
```

---

### §M5. Verify install — the macOS smoke checklist

Run these in order; all should print versions, not errors:

```bash
python3.11 --version            # → Python 3.11.X
which python                    # → .../nucleus/.venv/bin/python  (venv active)
docker --version                # → Docker version 24.0+
docker compose version          # → v2.20+
git --version                   # → 2.30+ (older: `xcode-select --install`)

# Constraint scripts (identical to Windows §4):
python scripts/check_pinning.py
python scripts/check_layering.py
python scripts/dagster_leak_check.py
python scripts/check_vocabulary.py
python scripts/loc_budget.py --report

# Test suite (identical to Windows §5):
pytest -v
# Expected: ~20 tests PASSED in <1s.

# CLI entry point per `docs/specs/nucleus_cli_spec.md` §3.7:
nucleus version
# Expected: prints `nucleus 0.0.0` plus pinned wrapped-OSS versions
# (duckdb, polars, pyarrow, pyiceberg, dagster). If `command not found`: venv
# not active OR `pip install -e ".[dev]"` did not register the entry point.
```

Continue with Windows §6 (pre-commit hooks) and §8 (daily workflow) — both POSIX-shell-clean, with `source .venv/bin/activate` substituted for `.\.venv\Scripts\Activate.ps1`.

---

### §M6. First Nucleus invocation (post-Tier-0)

> ⚠️ **Pre-Heartbeat status** ([`README.md`](README.md) §Status): `nucleus init` / `up` / `down` / `run` / `ingest` / `query` are **specified** in [`docs/specs/nucleus_cli_spec.md`](docs/specs/nucleus_cli_spec.md) §3 but not yet implemented. The block below is the **target** PoC #5 user flow; on a Tier-0 build (Mo 1-2) it works end-to-end.

After install, the [`poc/p5_beachhead/SCENARIO.md`](poc/p5_beachhead/SCENARIO.md) 30-min beachhead flow on macOS is:

```bash
nucleus init my-data-stack    # Scaffolds project per `docs/specs/nucleus_cli_spec.md` §3.1
cd my-data-stack
nucleus up                    # Boots local stack — target <10s (PoC #4 budget).
                              # Wraps `docker compose up -d <storage>` + filesystem-backed
                              # pyiceberg.SqlCatalog + in-process Dagster Definitions
                              # per `docs/specs/nucleus_cli_spec.md` §3.2.
```

Verify boot in <10s:

| Surface | URL / path | Default credentials | Source |
|---|---|---|---|
| **MinIO Console** (when MinIO compose) | http://localhost:9001 | `minioadmin` / `minioadmin` | [`docs/internal/research/minio.md`](docs/internal/research/minio.md) §2.1 + §4.3 (NEEDS VERIFICATION on default-cred preservation per Worker BB §2.1 + `docs/specs/nucleus_cli_spec.md` §10 NV #7) |
| **MinIO S3 endpoint** | http://localhost:9000 | (sigv4 with above) | Same |
| **SeaweedFS S3 endpoint** (when SeaweedFS compose, default per [ADR-008](docs/decisions/ADR-008-storage-substrate-v01.md)) | http://localhost:9000 | configurable | NEEDS VERIFICATION (ADR-008 PROPOSED; final pin + UI URL pending acceptance) |
| **Iceberg catalog file** | `./.nucleus/catalog.db` | (SQLite) | `docs/specs/nucleus_cli_spec.md` §7 + §10 NV #5 |

Continue per [`poc/p5_beachhead/SCENARIO.md`](poc/p5_beachhead/SCENARIO.md): `nucleus ingest postgres://... --table public.orders --as raw.orders` → SQL transform via `ctx.sql` → `nucleus query "SELECT ..."` → BI-ready Iceberg snapshot committed.

---

### §M7. macOS-specific troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `command not found: nucleus` | `.venv` not active | `source .venv/bin/activate` from project root |
| `command not found: python3.11` | Homebrew formula didn't link | `brew link python@3.11 --overwrite --force` |
| `Cannot connect to the Docker daemon at unix:///var/run/docker.sock` | Docker Desktop not started | Open Docker Desktop in `/Applications`; wait for "Docker Desktop is running" in the menu bar |
| `bind: address already in use` on port 9000 | Another process (prior MinIO/SeaweedFS, or anything else) holds the port | `lsof -i :9000` to find the PID; `kill <PID>`; OR remap the storage port in `docker-compose.yml` |
| `SSL: CERTIFICATE_VERIFY_FAILED` from `pip install` | python.org installer didn't run the cert script | Run `/Applications/Python\ 3.11/Install\ Certificates.command` once |
| `xcrun: error: invalid active developer path` | Xcode Command Line Tools missing | `xcode-select --install` (popup-driven; ~10 min) |
| `mach-o, but built for...` arch mismatch when running a wheel | Wheel pulled for the wrong arch (Apple Silicon vs Intel) | `pip install --force-reinstall --no-cache-dir <package>` to re-fetch the right arch |
| Slow `nucleus up` on Apple Silicon (>10s) | Storage image only published as amd64; running under Rosetta 2 | `docker inspect <image> \| grep Architecture` to confirm; flag in PoC #5 stuck-points (per `poc/p5_beachhead/RECRUITMENT.md`) |
| `python3` resolves to system 3.9 / 3.12 instead of 3.11 | `$PATH` precedence on macOS | Always invoke `python3.11` explicitly outside the venv; inside the venv, plain `python` is correct |

For unfamiliar errors, copy verbatim per Windows §10 — same protocol. macOS `Console.app` (`/Applications/Utilities/Console.app`) surfaces system-level errors not visible in the terminal.

---

### §M8. PoC #5 considerations for macOS testers

External testers on macOS run the same `git clone` → `nucleus up` → `nucleus ingest` → `nucleus query` flow as Windows testers ([`poc/p5_beachhead/SCENARIO.md`](poc/p5_beachhead/SCENARIO.md)), with three OS-derived nuances worth surfacing in the moderator's pre-session brief:

1. **Docker startup overhead is lower on macOS than on Windows.** macOS Docker Desktop runs containers in a lightweight VM (Apple Virtualization framework or HyperKit) without Windows Hyper-V's enable-feature dance. Per [`docs/internal/research/minio.md`](docs/internal/research/minio.md) §7 the MinIO single-binary cold-start is `<500ms` on Linux/macOS and `+1-3s` on Docker Desktop overhead — meaningfully faster than the same path on Windows (where Hyper-V layered on top inflates startup further). Expect macOS testers to land closer to the `<10s` `nucleus up` target. **NEEDS VERIFICATION** against PoC #4 measurements once they're produced on both OSes.

2. **Apple Silicon image-arch parity is per-image (cross-ref §M3).** The only third-party container is the storage substrate. The **archived** MinIO `RELEASE.2025-09-07T16-13-09Z` receives no future arm64 builds; if its existing arm64 manifest is incomplete on an M-series tester's machine, Docker Desktop falls back to Rosetta 2 emulation and `nucleus up` slows. SeaweedFS (per [ADR-008](docs/decisions/ADR-008-storage-substrate-v01.md)) historically publishes arm64 — pin TBD. Flag a Rosetta fallback as a PoC #5 stuck-point. **NEEDS VERIFICATION** pre-PoC #5 dry-run on both substrates.

3. **`nucleus doctor` is the intended session "step 0" — but ships v0.3+.** Per [`docs/specs/nucleus_cli_spec.md`](docs/specs/nucleus_cli_spec.md) §4.5, `nucleus doctor` will check Python `>=3.11,<3.13`, Docker reachable, ports `9000/9001` free, MinIO health, catalog valid, OL transport reachable, and disk free `>5 GB`. Per [`poc/p5_beachhead/RECRUITMENT.md`](poc/p5_beachhead/RECRUITMENT.md), PoC #5 testers run it as step 0. **It is a v0.3+ command** (NEEDS VERIFICATION on availability for the PoC #5 dry-run window — if the v0.1 ship date moves before v0.3, the §M5 manual checklist substitutes for `nucleus doctor`).

Per [`poc/p5_beachhead/DESIGN.md`](poc/p5_beachhead/DESIGN.md) §"Status gate", *"`SETUP.md` instructions verified on the host OS the tester uses (macOS primary; Windows + Linux as stretch)"* is a precondition. **§M1-§M8 closes the macOS half of that gate**; the Windows half is §1-§10 above; the Linux half is the natural POSIX subset of §M1-§M8 (skip §M3 Docker Desktop in favour of the native `docker` package; everything else carries — NEEDS VERIFICATION via a Linux dry-run before recruitment opens).

---

*This file is yours to edit. As you hit gotchas, add fixes here. Future-you will thank present-you.*
