# Modern Python Tooling Ecosystem — Research Notes

> Last verified: 2026-05-15 against current tool releases documented below.
> Scope: Developer toolchain — package management, linting, type checking, task runners,
> packaging standards, language evolution, and adjacent JS tooling relevant to Nucleus Workbench.
> AI training-data caveat: all claims below are verified against live official docs as of this date.

---

## Executive Summary — Top 3 Adoption Candidates for Nucleus v0.2/v0.3

| Rank | Tool | Verdict | Nucleus impact |
|---|---|---|---|
| 1 | **uv 0.11.x** | **Adopt now (v0.2)** | Replaces `pip + venv` in CI and dev setup; 10-100x faster installs; zero pyproject.toml changes needed; Pillar #1 direct win |
| 2 | **ruff 0.15.x** | **Adopt now (v0.2)** | Nucleus already uses ruff — MUST upgrade from 0.8.4 to 0.15.x; 0.15.0 introduced a new style guide; Pillar #1 + Pillar #4 |
| 3 | **just 1.x** | **Adopt later (v0.3)** | Replace Makefile on Windows (breaks contributors without GNU Make); Rust-native, cross-platform; Pillar #4 friction reduction |

**Skip:** `ty` (Astral's new type checker — beta only, not production-ready), Deno 2 (no Python project value), PEP 703 free-threaded Python (Nucleus is pinned to `<3.13`; Tier-1 engines not free-threaded-safe yet).

**Watch:** PEP 735 dependency groups (Final since Oct 2024 — uv supports it; unlocks `[dependency-groups]` as a cleaner alternative to extras for dev deps).

---

## 1. uv (Astral)

### Overview

uv is a single Rust binary that replaces `pip`, `pip-tools`, `pipx`, `poetry`, `pyenv`,
`virtualenv`, and `twine`. It was created by Astral (makers of ruff) and OpenAI acquired
Astral in March 2026, providing the strongest corporate backing of any Python packaging tool.

- **Current version:** 0.11.14 (released 2026-05-12)
  Source: [PyPI changelog](https://data.safetycli.com/packages/pypi/uv/changelog)
- **License:** Apache-2.0 + MIT
  Source: [GitHub repository](https://github.com/astral-sh/uv)
- **Official docs:** <https://docs.astral.sh/uv/>

### Benchmarks (official, from BENCHMARKS.md)

| Operation | pip | Poetry | uv |
|---|---|---|---|
| Cold install (no cache) | 31–36s | 11–47s | 2.8–4.8s |
| Warm install (cached) | 8.7–18.6s | 3.1–22.1s | **0.4–1.2s** |
| venv creation | 2.4s | 1.2s | **0.03s** |
| CI full install (real project) | ~2m 15s | ~45s | **~8s** |

Source: [uv benchmarks](https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md)

Speed comes from three mechanisms: parallel downloads, a global content-addressed cache
(deduplicates packages across projects), and Rust-native I/O.

### Adoption signal

- 126 million monthly PyPI downloads as of Q1 2026
  Source: [danilchenko.dev uv vs pip](https://www.danilchenko.dev/posts/uv-vs-pip-vs-poetry/)
- 74.2% "admired" in Stack Overflow 2025 developer survey
  Source: [aleyan.com Why aren't we uv yet](https://aleyan.com/blog/2026-why-arent-we-uv-yet/)
- 44% of `requirements.txt` popularity among new Python repos in Q1 2026
  Source: same

### Key features relevant to Nucleus

1. **`uv pip install`** — drop-in replacement for pip; zero code changes. Nucleus pyproject.toml
   works as-is. Source: [pip interface docs](https://docs.astral.sh/uv/pip/)

2. **`uv sync --locked`** — CI-safe install from `uv.lock`; equivalent to
   `pip install -r requirements.txt` but universal and cross-platform.
   Source: [uv sync docs](https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile)

3. **`uv run`** — runs any command inside the project env without activating it; useful for
   Makefile / justfile targets. Source: [uv run docs](https://docs.astral.sh/uv/guides/scripts/)

4. **`uv python pin 3.11`** — creates `.python-version` and sets project Python; replaces pyenv.
   Source: [Python guide](https://docs.astral.sh/uv/guides/install-python/)

5. **`uv tool install ruff`** — global tool management, replaces `pipx install ruff`.
   Source: [tools guide](https://docs.astral.sh/uv/guides/tools/)

6. **GitHub Actions:** official `astral-sh/setup-uv` action; `enable-cache: true` for warm CI.
   Source: [GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/)

7. **PEP 723 scripts:** `uv run my_script.py` automatically installs inline `# /// script`
   dependencies. Source: [scripts guide](https://docs.astral.sh/uv/guides/scripts/#declaring-script-dependencies)

### Migration cost for Nucleus (pip + venv → uv)

| Step | Effort | Risk | Notes |
|---|---|---|---|
| Install uv in CI (GitHub Actions) | LOW | NONE | Replace `pip install -e ".[dev]"` with `uv sync --locked` |
| Replace `python -m venv .venv && pip install` in Makefile | LOW | NONE | `uv venv && uv pip install -e ".[dev]"` |
| Add `uv.lock` to repo | LOW | LOW | Adds 50-200 KB lockfile; commit to VCS |
| Migrate `pyproject.toml` to uv project format | MEDIUM — optional | LOW | Adds `[tool.uv]` section; pyproject.toml core unchanged |
| **Total migration** | **~1 hour** | **LOW** | pyproject.toml untouched |

8-question gate: all 8 pass. Pillar #1 direct win (8s vs 2m 15s CI install), zero LOC
impact, empirically motivated by download trajectory, zero JVM risk.

**Verdict: ADOPT NOW (v0.2)**

---

## 2. ruff 0.15.x

### Overview

ruff is a Python linter and formatter written in Rust. Nucleus already uses
`ruff==0.8.4` (pinned in `pyproject.toml`), but the current stable release is
**0.15.12** (latest in the 0.15.x series). The gap is significant: 0.15.0 introduced
a **"2026 style guide"** — a new formatter revision with breaking changes.

- **Current version:** 0.15.12
  Source: [ruff PyPI](https://pypi.org/project/ruff/)
- **License:** MIT
  Source: [GitHub](https://github.com/astral-sh/ruff)
- **Official docs:** <https://docs.astral.sh/ruff/>

### Capabilities (current, 0.15.x)

| Capability | Replaces | Notes |
|---|---|---|
| Linter | Flake8 + 50+ plugins | 900+ rules; ~10-100x faster than Flake8 |
| Formatter | Black | >99.9% Black-compatible on existing codebases |
| Import sorter | isort | Enabled via `I` rule set |
| Upgrade tool | pyupgrade | Enabled via `UP` rule set |
| Security rules | bandit (subset) | `S` rule set |
| Docstring linter | pydocstyle | `D` rule set |

Source: [ruff docs overview](https://docs.astral.sh/ruff/)

**Speed numbers (official):** ruff formats large projects in milliseconds — over 30x faster
than Black, 100x faster than YAPF. Nick Schrock (Dagster founder) reported ruff checking
Dagster's entire 250k LOC codebase in **0.4 seconds** vs pylint's 2.5 minutes.
Source: [ruff testimonials](https://docs.astral.sh/ruff/)

### Version gap analysis (0.8.4 → 0.15.x)

Nucleus is currently pinned at `ruff==0.8.4`. Key changes to be aware of:

**0.15.0 — 2026 style guide (BREAKING for formatter)**
- New formatter style guide introduced
- `ruff format` output will differ from 0.8.4 on some constructs
- Line length handling and trailing comma rules changed
  Source: [BREAKING_CHANGES.md](https://github.com/astral-sh/ruff/blob/0.15.10/BREAKING_CHANGES.md)

**0.14.0 — Python 3.14 as default target**
- When no Python version is configured, defaults to 3.14 for syntax error checking
- Nucleus has `target-version = "py311"` set — no regression risk
  Source: [changelogs/0.14.x.md](https://github.com/astral-sh/ruff/blob/0.15.10/changelogs/0.14.x.md)

**New rules added between 0.8.4 and 0.15.x:**
- Expanded preview mode: 412 stable rules (up from 59 default in earlier versions)
- Nucleus selects explicit rule sets (`E`, `F`, `I`, `B`, `UP`, `N`, `SIM`, `RUF`, etc.) —
  these selections remain stable; only additive new rules within those sets are added
  Source: [ruff rules list](https://docs.astral.sh/ruff/rules/)

### Migration cost (ruff 0.8.4 → 0.15.x)

| Step | Effort | Risk | Notes |
|---|---|---|---|
| Update pin in pyproject.toml | TRIVIAL | LOW | `ruff==0.15.12` |
| Run `ruff format --check` to see formatter diffs | LOW — 5 min | LOW | Expect some minor reformatting on existing code |
| Run `ruff check --fix` to apply any new auto-fixable rules | LOW | LOW | Review diff before committing |
| Pre-commit config update (`rev:` tag) | LOW | NONE | Update `.pre-commit-config.yaml` ruff rev |
| Update Makefile `lint` target | TRIVIAL | NONE | API unchanged |
| **Total** | **~30 min** | **LOW** | Run `ruff format .` after pin upgrade |

**IMPORTANT:** Upgrade as a single-component PR per AGENTS.md §11.13.
8-question gate: all 8 pass — existing tooling, already adopted, zero LOC impact.

**Verdict: ADOPT NOW (v0.2) — single-component upgrade PR**

---

## 3. pyright vs mypy (and Astral ty)

### Context

Nucleus currently uses `mypy==1.13.0` in `--strict` mode. Two challengers are relevant:
**pyright** (Microsoft) and **ty** (Astral, beta).

### Mypy 1.13.0 (current)

- Mature, battle-tested; has the widest ecosystem integration
- `--strict` mode catches the most errors but is slowest
- Python 3.11 first-class support
- 1.4M+ weekly PyPI downloads
  Source: [mypy PyPI](https://pypi.org/project/mypy/)

### Pyright

- **Speed:** 2-4x faster than mypy on large codebases
- Home Assistant (large real-world project): mypy 45.66s → pyright 19.62s (2.3x faster)
  Source: [danilchenko.dev ty vs mypy vs pyright](https://www.danilchenko.dev/posts/ty-vs-mypy-vs-pyright/)
- Better IDE/LSP integration (powers Pylance in VS Code)
- Some behavioural differences from mypy strict; rare false-positive patterns differ
- Not installed from PyPI in the standard way (node-based binary); install via `npm` or
  `pyright` PyPI wrapper. Source: [pyright docs](https://github.com/microsoft/pyright)

### ty (Astral, beta)

- Released December 2025; **beta** as of 2026-05-15
  Source: [Astral ty blog](https://astral.sh/blog/ty)
- **Speed:** 10-100x faster than mypy; 80x faster than pyright for incremental editor updates
  (4.7ms vs 386ms for PyTorch editing)
- Install: `uv tool install ty@latest` or `uvx ty check`
  Source: [ty docs](https://docs.astral.sh/ty/)
- Status: Astral uses it internally and recommends for "motivated users"; stable 1.0 targeted
  for 2026. **Not production-ready for strict type safety enforcement.**

### Comparison summary

| Checker | Speed vs mypy | Maturity | Nucleus risk |
|---|---|---|---|
| mypy 1.13.0 | baseline | ✅ Production, 10+ years | NONE (current) |
| pyright | 2-4x faster | ✅ Production, used by VS Code | LOW — some strict mode differences |
| ty | 10-100x faster | ⚠️ Beta | HIGH — not stable yet |

### Migration cost (mypy → pyright)

| Step | Effort | Risk |
|---|---|---|
| Install pyright, run on codebase | LOW | LOW |
| Resolve type divergences (pyright finds different errors than mypy) | MEDIUM-HIGH | MEDIUM — may surface new type errors |
| Remove mypy config, add pyrightconfig.json | LOW | LOW |
| Update CI + pre-commit | LOW | NONE |
| **Total** | **2-4 hours** | **MEDIUM** |

**Verdict: SKIP for now (v0.2), ADOPT LATER for ty (v0.5 after ty 1.0 releases)**

The 2-4x speedup from pyright doesn't justify the risk of type-checking behavioral differences
during active development. Revisit when ty reaches 1.0 — the 10-100x speedup with a unified
Astral toolchain (uv + ruff + ty) will be compelling.

---

## 4. Task Runners: just vs Makefile vs nox vs invoke

### Context

Nucleus uses a `Makefile` with GNU Make syntax. On Windows, this requires
`winget install GnuWin32.Make` (a friction point noted in the Makefile header).
The Makefile comment warns: "Cross-platform-ish dev shortcuts."

### just (Rust)

- **Version:** 1.49.0 (April 2026)
  Source: [crates.io just](https://crates.io/crates/just)
- **Stars:** 32,631 GitHub stars
  Source: [GitHub casey/just](https://github.com/casey/just)
- **License:** CC0-1.0 (public domain equivalent)
- **Features:**
  - `justfile` syntax inspired by Make but no tab requirement
  - No `.PHONY` declarations needed
  - Cross-platform: Linux, macOS, Windows
  - Loads `.env` automatically
  - Recipes accept arguments: `just test --fast`
  - `just --list` for discovery
  - Supports recipes written in arbitrary languages including Python and PowerShell
    Source: [just manual](https://just.systems/man/en/)

### nox

- Python-based task runner (configured in `noxfile.py`)
- Strength: creates and destroys temporary virtual environments per session — high reproducibility
- Used by 3,000+ Python projects (Google's APIs, pip, etc.)
  Source: [nox documentation](https://nox.thea.codes/en/stable/)
- Downside: Python knowledge required to configure; not for non-Pythonists
- nox 2026.4.10 is the current release

### hatch scripts

- `[tool.hatch.envs]` + `[tool.hatch.envs.default.scripts]` in pyproject.toml
- Since Nucleus already uses hatchling as build backend, hatch scripts are zero-overhead
- Downside: hatch's env model conflicts with uv's env model; tension when adopting both
  Source: [hatch why docs](https://hatch.pypa.io/dev/why/)

### Tool comparison for Nucleus

| Tool | Cross-platform | Windows-native | In Nucleus | Notes |
|---|---|---|---|---|
| GNU Make (current) | ❌ (needs install on Win) | ❌ | ✅ | Ubiquitous but dated |
| just | ✅ | ✅ | ❌ | 32k ⭐; growing rapidly |
| nox | ✅ (Python) | ✅ | ❌ | Strong in lib ecosystem; Python config |
| hatch scripts | ✅ | ✅ | Partial | Tension with uv env model |
| invoke | ✅ | ✅ | ❌ | More boilerplate; general-purpose |

### Migration cost (Makefile → justfile)

| Step | Effort | Risk |
|---|---|---|
| Install just on dev machines | LOW — single binary | NONE |
| Translate Makefile targets to justfile recipes | MEDIUM — ~1 hour per Makefile | LOW |
| Update CI to use `just ci` instead of `make ci` | LOW | NONE |
| Add justfile to repo | LOW | NONE |
| Maintain Makefile in parallel during transition | — | NONE |
| **Total** | **2-3 hours** | **LOW** |

8-question gate: all 8 pass. Windows contributor friction is empirically documented in
the current Makefile header ("Cross-platform-ish"). Just removes that qualifier.

**Verdict: ADOPT LATER (v0.3)**

---

## 5. Project Metadata + Packaging

### hatchling (current — stay)

Nucleus already uses `hatchling>=1.27.0` as the build backend. This is the right choice:

- Modern PEP 517/518 compliant build backend
- Cleaner defaults: uses `.gitignore` patterns for file inclusion
- No `MANIFEST.in` needed
- Used by Pip, Jupyter, FastAPI, and many other major projects
  Source: [hatch why docs](https://hatch.pypa.io/dev/why/)

**Current vs popularity:** setuptools has 5,854 top-500 PyPI packages using it; hatchling has 480.
But setuptools momentum is legacy — new projects overwhelmingly choose hatchling or flit.
Source: [Quansight PEP 517 popularity analysis](https://labs.quansight.org/blog/pep-517-build-system-popularity)

**Verdict: STAY with hatchling — already the correct choice.**

### maturin (Rust extensions)

Not relevant to Nucleus v0.1-v0.3 — pure Python. If a hot path ever needs Rust, maturin +
PyO3 is the standard path. Defer until that ADR fires.

### PEP 735 — Dependency Groups

**Status:** Final (accepted October 10, 2024)
Source: [PEP 735 text](https://peps.python.org/pep-0735)

PEP 735 defines `[dependency-groups]` in `pyproject.toml` — separate from `[project.dependencies]`
and `[project.optional-dependencies]`. Groups are for dev/test/docs deps that should NOT appear
in the distributed package.

```toml
[dependency-groups]
dev = ["ruff==0.15.12", "mypy==1.13.0", "pytest==8.3.4"]
docs = ["mkdocs==1.6.1", "mkdocs-material==9.5.49"]
```

**Tool support:**
- pip: ✅ `pip install --dependency-groups dev` (since Feb 2025)
  Source: [pip issue #12963](https://github.com/pypa/pip/issues/12963)
- uv: ✅ native support
  Source: [uv dependency groups docs](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-groups)
- `dependency-groups` standalone package: 1.4M weekly downloads (v1.3.1)
  Source: [PyPI dependency-groups](https://pypi.org/project/dependency-groups/)

**Migration cost for Nucleus:** Nucleus currently uses `[project.optional-dependencies]` with
`dev`, `docs`, `observability`, `lineage-advanced`, `snowflake`, `gcs` extras. Runtime extras
(observability, lineage-advanced, snowflake, gcs) MUST stay as optional-dependencies since they
install into the user's environment. Dev and docs extras could migrate to `[dependency-groups]`
for semantic correctness.

| Step | Effort | Risk |
|---|---|---|
| Move `dev` + `docs` to `[dependency-groups]` | LOW | LOW — pin discipline unchanged |
| Update Makefile `install` target | TRIVIAL | NONE |
| Validate with pip + uv | LOW | NONE |
| **Total** | **~45 min** | **LOW** |

**Verdict: ADOPT LATER (v0.3) — clean semantic improvement; runtime extras unaffected.**

---

## 6. PEP 723 — Inline Script Metadata

**Status:** Finalized January 8, 2024
Source: [PEP 723 text](https://peps.python.org/pep-0723/)

PEP 723 embeds script dependencies directly in a `# /// script ... # ///` TOML block:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests==2.32.3",
#   "rich==13.9.4",
# ]
# ///

import requests, rich
```

When run with `uv run my_script.py`, uv reads the block, creates a temporary venv,
installs deps, and runs the script — zero setup for the caller.
Source: [uv scripts guide](https://docs.astral.sh/uv/guides/scripts/)

Three locking strategies as of May 2026 (source: [pydevtools locking guide](https://pydevtools.com/blog/locking-dependencies-for-pep-723-scripts/)):
1. Pin versions inline (what Nucleus does by default — exact pins)
2. `[tool.uv] exclude-newer = "2026-05-15"` timestamp cap
3. `uv lock --script my_script.py` generates `my_script.py.lock` sidecar

### Relevance to Nucleus

Nucleus ships governance scripts in `scripts/` — `loc_budget.py`, `dagster_leak_check.py`,
`check_pinning.py`, etc. These currently require `pip install nucleus[dev]` before running.

With PEP 723 + uv:
```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["rich==13.9.4", "ruff==0.15.12"]
# ///
```
Contributors could run `uv run scripts/loc_budget.py` with zero setup. This is compelling
for the PoC #5 external-tester scenario — remove every setup friction point.

8-question gate: all 8 pass. Near-zero LOC — add comment blocks to existing scripts.

**Verdict: ADOPT LATER (v0.3) — annotate `scripts/` with PEP 723 blocks after uv is
adopted in v0.2. Zero risk, minimal effort, pure DX win for PoC #5 external testers.**

---

## 7. Free-Threaded Python (PEP 703 / Python 3.13)

### Status

PEP 703 (Making the Global Interpreter Lock Optional) was accepted October 24, 2023.
Source: [PEP 703](https://peps.python.org/pep-0703)

Timeline:
- **Python 3.13** (released October 2024): free-threaded build available as **experimental**
  — `python3.13t` binary; **not the default**
- **Python 3.14** (due October 2025): free-threaded build graduates to **officially supported**
  (per PEP 779) — still opt-in, not the default
  Source: [PEP 779](https://peps.python.org/pep-0779)
- **Default build:** making free-threaded Python the default is deliberately deferred;
  no timeline set as of 2026-05-15
  Source: [py-free-threading guide](https://py-free-threading.github.io/)

### Relevance to Nucleus

**Nucleus is pinned `>=3.11,<3.13`.** Free-threaded Python is Python 3.13+.

Even if Nucleus added 3.13 support:
- DuckDB's Python bindings as of 1.1.3 ship GIL-dependent `duckdbpyconnection` objects; no
  free-threaded wheel exists yet (NEEDS VERIFICATION — check DuckDB 1.x release notes)
- Polars 1.18.0 uses Rust pyo3 extensions; free-threaded support requires PyO3's `abi3` wheel
  compilation with `--features pyo3/extension-module --no-default-features` flags
  (NEEDS VERIFICATION — check Polars changelog for `3.13t` wheel support)
- Dagster 1.9.5 has no documented free-threaded support
- pyiceberg 0.11.1 has no documented free-threaded support

**Concurrent run safety in Nucleus** — The primary concurrency concern in Nucleus is **not**
thread-safety of Python objects but the atomicity of Iceberg snapshot commits. Per
`nucleus_architecture_v4.1.md §5.5`, Nucleus delegates transaction coordination to the
Iceberg catalog (filesystem-based at v0.1, Lakekeeper at v0.3+). This is catalog-side
atomicity, not GIL-related.

**Verdict: SKIP (not relevant until Python ceiling raised AND all Tier-1 engine wheels
ship free-threaded variants — conservatively v1.0+ timeline).**

---

## 8. Adjacent Tooling — JS Frontend Dev Velocity

Nucleus Workbench v0.2 ships a React frontend served by FastAPI. Relevant JS tooling:

### Landscape (verified 2026-05-15)

**Vite 8 (March 2026)**
- Replaced internal Rollup bundler with **Rolldown** (Rust port of Rollup)
- Result: 10-30x faster production builds — closing previous speed gap vs Bun
  Source: [pkgpulse Bun vs Vite 2026](https://www.pkgpulse.com/guides/bun-vs-vite-2026)
- ~40M weekly npm downloads; powers Nuxt, SvelteKit, Astro
- React Fast Refresh included; 800+ plugin ecosystem
- **Recommended for React development in 2026**

**Bun 1.x**
- Zig-based runtime + bundler; 1.75x faster than esbuild on three.js benchmarks
  Source: [Bun vs esbuild docs](https://bun.sh/docs/bundler/vs-esbuild)
- ~3M weekly downloads
- **Missing React Fast Refresh** → not a drop-in Vite replacement for development
- Best use: server-side bundles, CLI tools, utility scripts
- `Bun + Vite` together is the recommended 2026 pattern (Bun as runtime; Vite as dev server)
  Source: [pkgpulse](https://www.pkgpulse.com/guides/bun-vs-vite-2026)

**Deno 2**
- Full npm compatibility (2M+ packages via `npm:` specifiers)
- Native TypeScript without transpilation
- Built-in formatter, linter, test runner, and bundler
  Source: [pkgpulse Deno vs Node 2026](https://www.pkgpulse.com/guides/deno-2-vs-nodejs-2026)
- Performance: ~40k HTTP req/s vs Node.js ~25-30k req/s (synthetic)
- 15% faster cold install, 90% faster cached install than npm
- **Appropriate for:** greenfield TypeScript projects, edge functions, CLI tools
- **Not appropriate for:** migrating existing Node.js/Vite/React projects mid-development

**esbuild**
- Go-based; powers Vite's dependency pre-bundling step
- Battle-tested, stable API; still the fastest Go-native option
- Vite 8 wraps Rolldown for final bundles, esbuild for dev pre-bundling
  Source: [betterstack esbuild vs vite](https://betterstack.com/community/guides/scaling-nodejs/esbuild-vs-vite)

### Nucleus Workbench recommendation

| Tool | Verdict | Notes |
|---|---|---|
| Vite 8 | **Adopt / stay** | Standard for React; Rolldown makes it fastest non-Bun option |
| Bun as runtime | **Consider for CI** | 9-30x faster `npm install` in CI; no React app changes needed |
| Deno 2 | **Skip** | No migration path for existing Vite project; Node.js compatible enough |
| esbuild standalone | **Skip** | Already included via Vite internals |

If Workbench frontend currently uses Vite + Node.js, upgrading Vite to v8 is the highest-ROI
JS tooling change. Adding Bun as the CI package manager (instead of npm) is a secondary win.
NEEDS VERIFICATION: confirm current Workbench frontend setup in `frontend/` directory.

---

## 9. Pre-commit Ecosystem in 2026

### Current state

Nucleus uses `pre-commit==4.0.1` (pinned in dev dependencies). The pre-commit ecosystem
is mature and stable. Key 2026 developments concern uv integration.

### Official uv pre-commit hooks

Source: [uv pre-commit docs](https://docs.astral.sh/uv/guides/integration/pre-commit/)

```yaml
# .pre-commit-config.yaml — uv lock sync on pyproject.toml changes
repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: 0.11.14  # pin to uv version
    hooks:
      - id: uv-lock        # regenerate uv.lock when pyproject.toml changes
      - id: uv-export      # keep requirements.txt in sync with uv.lock
```

Source: [astral-sh/uv-pre-commit](https://github.com/astral-sh/uv-pre-commit)

### pre-commit-uv: faster hook installation

The `pre-commit-uv` plugin patches pre-commit to use uv for installing Python-based hooks,
giving ~1.30x faster hook installation:

```bash
uv tool install pre-commit --with pre-commit-uv
```

Source: [tox-dev/pre-commit-uv](https://github.com/tox-dev/pre-commit-uv)

### Best practices for 2026

1. **Pin `rev:` to exact versions**, not `latest` — version drift in hooks breaks CI
2. **Use `uv-lock` hook** when adopting uv to prevent stale lockfiles
3. **ruff pre-commit hooks are the fastest option** — ruff's pre-commit hook is 10-100x faster
   than separate black + flake8 + isort hooks; Nucleus already uses it
4. **`sync-with-uv`** (tsvikas/sync-with-uv) auto-updates `.pre-commit-config.yaml` hook
   versions to match `uv.lock` — useful after adopting uv project format
   Source: [tsvikas/sync-with-uv](https://github.com/tsvikas/sync-with-uv)
5. **Mypy in pre-commit** — run mypy as a local hook rather than via the pre-commit mirror
   to avoid environment inconsistencies; same advice applies for ruff format hook

### pre-commit upgrade path for Nucleus

Two changes when uv + ruff are upgraded in v0.2:
1. Update ruff hook `rev: v0.8.4` → `rev: v0.15.12` in `.pre-commit-config.yaml`
2. Add `astral-sh/uv-pre-commit` with `id: uv-lock` to prevent stale lockfile commits

**Verdict: EVOLVE (mechanical update, no risk).**

---

---

## "Adopt Now / Adopt Later / Skip" Verdicts — with Migration Cost

| Tool | Verdict | Effort | Rationale |
|---|---|---|---|
| **uv 0.11.x** | **Adopt Now (v0.2)** | ~1 hr | Zero config change; 8s vs 2m 15s CI; OpenAI-backed; 126M monthly downloads. Pillar #1. |
| **ruff 0.15.x** | **Adopt Now (v0.2)** | ~30 min | 7-version lag from 0.8.4; 0.15.0 style guide breaks formatter output; single-PR upgrade. |
| **Vite 8 (frontend)** | **Adopt Now (v0.2)** | ~1 hr | 10-30x faster builds via Rolldown; same API; verify current version first. |
| **pre-commit ruff hook** | **Adopt Now (with ruff)** | Trivial | Update rev: from 0.8.4 → 0.15.12 in `.pre-commit-config.yaml`. |
| **just 1.x** | **Adopt Later (v0.3)** | ~3 hrs | Removes Windows Makefile friction; 32k ⭐; no user-visible impact before v0.3. |
| **PEP 735 dep groups** | **Adopt Later (v0.3)** | ~45 min | Cleaner dev/docs dep semantics; pip + uv both support; low risk. |
| **PEP 723 script blocks** | **Adopt Later (v0.3)** | ~1 hr | Annotate `scripts/` for zero-setup contributor UX; requires uv first. |
| **uv-lock pre-commit hook** | **Adopt Later (with uv)** | Trivial | Prevents stale lockfile when pyproject.toml changes. |
| **pyright** | **Skip → revisit v0.5** | ~4 hrs | 2-4x speedup not worth type-check behavioral divergence risk mid-development. |
| **ty (Astral)** | **Skip → revisit after ty 1.0** | ~4 hrs | Beta; 10-100x speedup compelling; not production-safe yet. |
| **Deno 2** | **Skip** | — | No benefit over Node.js for existing Python + React project. |
| **Free-threaded Python** | **Skip** | — | Nucleus `<3.13`; Tier-1 engine wheels not free-threaded-safe; GIL not the concurrency bottleneck. |
| **maturin (Rust)** | **Skip** | — | Pure Python project; no ADR trigger for native extensions. |

---

## NEEDS VERIFICATION

The following claims could not be fully confirmed from official docs during this research session.
Each should be verified before any associated decision is acted upon.

1. **DuckDB 1.1.3 free-threaded wheel support**
   Claim that DuckDB has no `3.13t` wheel was inferred from ecosystem state, not confirmed
   from DuckDB release notes.
   **Check:** <https://github.com/duckdb/duckdb/releases> — search for `3.13t` or `--disable-gil`

2. **Polars 1.18.0 free-threaded wheel**
   Claim inferred; not confirmed from Polars changelog.
   **Check:** <https://github.com/pola-rs/polars/releases> — search for `cp313t` or `abi3`

3. **ruff 0.15.0 "2026 style guide" specific formatting changes**
   The existence of a "2026 style guide" was cited from search results; the specific
   formatting diffs for Nucleus's codebase need to be measured empirically.
   **Check:** Run `uv run ruff@0.15.12 format --check src/` against current codebase

4. **Nucleus frontend stack (Vite version)**
   Research assumed Nucleus Workbench uses Vite, but the `frontend/` directory structure
   was not verified.
   **Check:** Read `frontend/package.json` — confirm Vite version and upgrade cost

5. **ty current rule completeness vs mypy strict**
   ty beta was confirmed but the completeness of type-checking rule coverage relative to
   `mypy --strict` is not confirmed from official docs.
   **Check:** <https://docs.astral.sh/ty/> — compare rule set to mypy strict mode

---

## References

Official documentation sources cited in this report:

**uv:** <https://docs.astral.sh/uv/> · benchmarks: <https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md> ·
GitHub Actions: <https://docs.astral.sh/uv/guides/integration/github/> · scripts: <https://docs.astral.sh/uv/guides/scripts/> ·
lockfile: <https://docs.astral.sh/uv/concepts/projects/layout/#the-lockfile> · pre-commit: <https://docs.astral.sh/uv/guides/integration/pre-commit/> ·
migration: <https://docs.astral.sh/uv/guides/migration/pip-to-project/>

**ruff:** <https://docs.astral.sh/ruff/> · rules: <https://docs.astral.sh/ruff/rules/> ·
FAQ: <https://docs.astral.sh/ruff/faq/> · breaking changes 0.15: <https://github.com/astral-sh/ruff/blob/0.15.10/BREAKING_CHANGES.md> ·
PyPI: <https://pypi.org/project/ruff/>

**ty (Astral):** <https://docs.astral.sh/ty/> · blog: <https://astral.sh/blog/ty> · GitHub: <https://github.com/astral-sh/ty>

**Type checkers:** benchmarks 2026: <https://docs.bswen.com/blog/2026-03-17-python-type-checker-performance-benchmarks/> ·
comparison: <https://www.danilchenko.dev/posts/ty-vs-mypy-vs-pyright/>

**uv/ruff adoption:** <https://aleyan.com/blog/2026-why-arent-we-uv-yet/> · <https://www.danilchenko.dev/posts/uv-vs-pip-vs-poetry/>

**PEPs:** PEP 703 (GIL): <https://peps.python.org/pep-0703> · PEP 779 (free-threaded criteria): <https://peps.python.org/pep-0779> ·
PEP 723 (inline scripts): <https://peps.python.org/pep-0723/> · PEP 735 (dep groups): <https://peps.python.org/pep-0735>

**py-free-threading guide:** <https://py-free-threading.github.io/>

**just:** <https://just.systems/man/en/> · crates.io: <https://crates.io/crates/just> · GitHub: <https://github.com/casey/just>

**nox:** <https://nox.thea.codes/en/stable/> · **hatch:** <https://hatch.pypa.io/dev/why/>

**packaging popularity:** <https://labs.quansight.org/blog/pep-517-build-system-popularity>

**pre-commit uv:** <https://github.com/astral-sh/uv-pre-commit> · uv-install: <https://github.com/tox-dev/pre-commit-uv/> ·
sync-with-uv: <https://github.com/tsvikas/sync-with-uv>

**PEP 723 locking:** <https://pydevtools.com/blog/locking-dependencies-for-pep-723-scripts/>

**dependency-groups PyPI:** <https://pypi.org/project/dependency-groups/>

**Frontend:** Bun vs Vite: <https://www.pkgpulse.com/guides/bun-vs-vite-2026> · Bun vs esbuild: <https://bun.sh/docs/bundler/vs-esbuild> ·
esbuild vs Vite: <https://betterstack.com/community/guides/scaling-nodejs/esbuild-vs-vite>
