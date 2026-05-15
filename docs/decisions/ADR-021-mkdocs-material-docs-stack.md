# ADR-021: MkDocs Material Documentation Stack

**Status:** ACCEPTED
**Date:** 2026-05-15
**Author:** Nucleus Team
**Supersedes:** None (first docs stack ADR)
**References:** AGENTS.md §11 (documentation), pyproject.toml `[project.optional-dependencies.docs]`

---

## Context

Nucleus v0.1.0 reached beta (2026-05-14, 8/8 WSL E2E PASS). External testers (PoC #5) need polished documentation to evaluate the platform without insider context. The existing `docs/onboarding/quickstart.md` and scattered spec files are not sufficient for a public-facing evaluation path.

Requirements:
1. A complete public documentation site (~55 pages) covering installation, quickstart, concepts, guides, cookbook, CLI reference, API reference, errors, governance, and philosophy
2. Auto-generated API reference from Python docstrings (no manual maintenance)
3. Search built-in
4. Mobile-responsive
5. Matches the editorial brand (Indigo/Deep Purple palette, Inter + JetBrains Mono fonts)
6. Build artifact is a static site (deployable to GitHub Pages, Cloudflare Pages, Vercel)
7. Must integrate with existing `pyproject.toml` extras pattern and CI workflow

Ratified 2026-05-15: code shipped in commit a41a82c (v0.2.0 handover bundle).

---

## Options considered

### Option A — MkDocs Material

- **License:** MIT
- **Maturity:** Industry standard for Python project docs (used by FastAPI, Polars, Pydantic, Dagster, etc.)
- **API auto-generation:** mkdocstrings\[python\] — reads Python docstrings + type annotations directly
- **Build:** Static HTML via `mkdocs build`
- **LOC impact:** Zero proprietary LOC (content only)
- **Extras:** mkdocs-glightbox (lightbox), mkdocs-include-markdown-plugin (reuse), pymdown-extensions (rich markdown)

### Option B — Sphinx + ReadTheDocs theme

- **License:** BSD-2-Clause
- **Maturity:** Older, more complex configuration; best for API reference heavy projects
- **DX:** RST syntax is harder for non-Python contributors; `conf.py` is verbose
- **Verdict:** Overkill; Material's mkdocstrings handles API ref just as well with simpler config

### Option C — Docusaurus

- **License:** MIT
- **Maturity:** Excellent for multi-language projects; requires Node.js
- **DX:** Adds Node.js dependency to a Python project; breaks the "pure Python" contributor story
- **Verdict:** Rejected — adding Node.js to a pure-Python project violates Pillar 5 (minimal resources) and increases contributor setup burden

---

## Decision

**Chosen: Option A — MkDocs Material**

Rationale:
1. Zero new language dependencies (Python-only)
2. Industry standard for Python project docs — familiar to contributors
3. `mkdocstrings[python]` provides auto-generated API reference with zero maintenance overhead
4. MIT license — GREEN tier per ADR-007
5. Compatible with exact-pin policy (Constraint #11)
6. Static output deployable anywhere

---

## Consequences

### LOC budget impact

Zero — docs content is not counted in the 30K LOC proprietary budget (per `pyproject.toml` `[tool.nucleus].loc_exclude`).

### New dependencies (docs extras only — not runtime)

| Package | Version | License |
|---------|---------|---------|
| `mkdocs` | 1.6.1 | BSD-2-Clause |
| `mkdocs-material` | 9.5.49 | MIT |
| `mkdocstrings[python]` | 0.27.0 | ISC |
| `mkdocs-include-markdown-plugin` | 7.2.2 | Apache-2.0 |
| `mkdocs-glightbox` | 0.5.2 | MIT |
| `pymdown-extensions` | 10.21.3 | MIT |

All GREEN tier per ADR-007. Not installed with `pip install nucleus` (docs extra only).

### Files created

- `mkdocs.yml` — root configuration
- `docs/site/` — full ~55-page site tree
- `.github/workflows/docs.yml` — build-only CI (deploy workflow is separate)

### Maintenance

- Upgrade path: one-component-per-PR per Constraint #11
- Major version upgrade (e.g., mkdocs-material 10.x) requires ADR amendment
- CI fails on `mkdocs build --strict` warnings — keeps link integrity enforced

### Open questions for founder

1. **Hosting:** GitHub Pages vs Cloudflare Pages vs Vercel. CI/CD builder will wire deploy; this ADR covers build only.
2. **Custom domain:** `docs.nucleus-data.io` or `nucleus.dev/docs`?
3. **Versioning:** mike (mkdocs versioning) is configured in `mkdocs.yml` extra; activate when multiple stable versions exist.
4. **Logo/favicon:** Placeholder SVG used; final design deferred to founder.

---

## Verification

```powershell
# Install docs extras
.\.venv\Scripts\python.exe -m pip install -e .[docs]

# Build (strict)
mkdocs build --strict --site-dir _site_test

# Governance
.\.venv\Scripts\python.exe scripts\check_vocabulary.py
.\.venv\Scripts\python.exe scripts\check_pinning.py
.\.venv\Scripts\python.exe scripts\check_licenses.py
```

Expected: zero warnings, zero errors, all governance scripts EXIT 0.
