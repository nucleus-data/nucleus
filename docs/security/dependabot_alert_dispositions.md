# Dependabot Alert Dispositions

> **Created**: 2026-05-15 — GitHub repo Dependabot setup audit (foreground sweep).
> **Repo**: `mtoanng/nucleus` (private, beta).
> **Reviewer**: founder (via swarm-implementer foreground sweep, parent-supervised).
> **Cross-refs**: `AGENTS.md` §11.13 (Constraint #11 — upgrade discipline), `docs/security/threat_model_v1.md` §11 (action items), `docs/security/README.md` (security docs nav).

This file is the **single source of truth** for *why* a given Dependabot alert was dismissed. The dismissal comment posted on each alert links back here for the full rationale (the GitHub API limits inline dismissal comments to 280 characters, so the alert-side comment is a pointer + one-line summary; the audit trail lives below).

When you `gh api ".../dependabot/alerts/{N}" --jq .dismissed_reason` you will see `tolerable_risk`. When you read this file you will see *exactly which Nucleus code path makes that risk N/A in production* — pinned to file + line where applicable.

If a future Nucleus change introduces the vulnerable code path, the corresponding alert MUST be re-opened by editing `state=open` via `gh api -X PATCH`. The verification greps below are the canonical "did this change re-open the attack surface?" probes.

---

## Conventions

- **N/A in production** = the vulnerable code path is not invoked in any Nucleus runtime entry point (CLI, Workbench server, ctx SDK, governance scripts).
- **Dev-only** = the dependency is only consumed at build time, by the frontend tool-chain (Vite, postcss, tailwind), or inside a non-shipped path (`vite dev`, `vite preview`).
- **Upstream-fix-pending** = an upstream Dependabot PR exists in this repo that resolves the same CVE at the version-bump level (PR #7 for postcss, PR #8 for vite); dismissal is the foreground action; the PR remains the eventual fix.
- All dismissals use GitHub's `dismissed_reason: "tolerable_risk"`. The closest alternative `"not_used"` was considered but rejected because it implies *we plan to keep the dep but not use it* — for vite/postcss we *do* use them at build-time; only the vulnerable surface is unused.

---

## Verification greps (re-run any time)

```powershell
# Dagster I/O manager attack path (CVE-2026-41490)
rg "from dagster_(duckdb|snowflake|gcp|deltalake|snowflake_polars)" src/
#   Expected: 0 hits.  Result on 2026-05-15: 0 hits.

# Dagster notebook handler attack path (CVE-2025-51481)
rg "get_notebook_data|jupyter" src/
#   Expected: 0 hits.  Result on 2026-05-15: 0 hits.

# Vite dev/preview server in production runtime
rg "vite preview|vite dev|vite serve" .
#   Expected: only in src/nucleus/workbench/frontend/package.json scripts block (not invoked by production).
#   Verified: docker/Dockerfile.production builds the Python wheel and ENTRYPOINT=["nucleus"]; no `vite preview` invocation.

# postcss in Nucleus runtime
rg "postcss" src/nucleus/workbench/
#   Expected: package.json + postcss.config.js only (both build-time).  Result on 2026-05-15: as expected.

# Workbench production static-file serving path
rg "StaticFiles|mount.*static" src/nucleus/workbench/
#   Expected: src/nucleus/workbench/app.py L33 import + L106 mount.
#   Workbench production serves PRE-BUILT static assets from src/nucleus/workbench/static/index.html via FastAPI.
```

If any of these greps return unexpected results in a later audit, **re-open the corresponding alert** and re-evaluate.

---

## Dismissed as `tolerable_risk` — 14 alerts

| # | Severity | CVE / GHSA | Package | Range | Rationale |
|---|---|---|---|---|---|
| 3 | HIGH 8.3 | CVE-2026-41490 / GHSA-mjw2-v2hm-wj34 | dagster | ≤ 1.13.0 | SQL injection via dynamic partitions in I/O managers (`dagster-duckdb`, `dagster-snowflake`, `dagster-gcp`, `dagster-deltalake`, `dagster-snowflake-polars`). **N/A**: Nucleus wraps `@dagster.asset` directly via PoC #1 Error Translation Layer (`src/nucleus/coordination/error_translation.py`); none of the vulnerable I/O manager subpackages are imported anywhere in `src/`. Architecture: `docs/specs/nucleus_architecture_v4.1.md` §6.3 ("Dagster wrapped + hidden behind `ctx`"); ADR-001 PoC #1 promotion. |
| 2 | MED 6.6 | CVE-2025-51481 / GHSA-h7x8-jv97-fvvm | dagster | < 1.10.16 | Local File Inclusion via `get_notebook_data` handler when Dagster gRPC server is exposed. **N/A**: Nucleus does NOT expose a Dagster gRPC server — Dagster is embedded as an in-process library wrapped behind the `ctx` SDK. The `get_notebook_data` handler path requires the Dagster webserver / `dagster api grpc` mode, neither of which Nucleus ships. Architecture: `docs/specs/nucleus_architecture_v4.1.md` §6.3. |
| 1 | MED 6.3 | CVE-2026-39365 / GHSA-4w7w-66w2-5vf9 | vite | ≤ 6.4.1 | Path traversal via `.map` requests on the dev server. **Dev-only**: the Workbench production binary is `docker/Dockerfile.production` which builds the Python wheel and entrypoints to `nucleus` CLI — there is no `vite preview` or `vite dev` in any runtime path. Static assets are pre-built into `src/nucleus/workbench/static/` and served by FastAPI `StaticFiles` (`src/nucleus/workbench/app.py` L33, L106). PR #8 in this repo bumps vite to 6.4.2; that PR remains open for founder review. |
| 4 | MED 6.5 | CVE-2025-24010 / GHSA-vg6x-rcgg-rjx6 | vite | ≤ 5.4.11 | CORS + WebSocket hijack on dev server. **Dev-only**: same rationale as #1. |
| 5 | MED 5.3 | CVE-2025-30208 / GHSA-x574-m823-4x7w | vite | < 5.4.15 | Trailing-slash file-fence bypass on dev server. **Dev-only**: same rationale as #1. |
| 6 | MED 5.3 | CVE-2025-31125 / GHSA-4r4m-qw57-chr8 | vite | < 5.4.16 | `?raw??` query bypass on dev server. **Dev-only**: same rationale as #1. |
| 7 | MED 5.3 | CVE-2025-31486 / GHSA-xcj6-pq6g-qj4x | vite | < 5.4.17 | `.svg` `server.fs.deny` bypass on dev server. **Dev-only**: same rationale as #1. |
| 8 | MED 6.0 | CVE-2025-32395 / GHSA-356w-63v5-8wf4 | vite | < 5.4.18 | `#` request-target bypass on dev server. **Dev-only**: same rationale as #1. |
| 9 | MED 6.0 | CVE-2025-46565 / GHSA-859w-5945-r5v3 | vite | ≤ 5.4.18 | `/.env/.` `server.fs.deny` bypass on dev server. **Dev-only**: same rationale as #1. |
| 10 | LOW 2.3 | CVE-2025-58752 / GHSA-jqfw-vq24-v9c3 | vite | ≤ 5.4.19 | `server.fs.deny` HTML response bypass. **Dev-only**: same rationale as #1. |
| 11 | LOW 2.3 | CVE-2025-58751 / GHSA-g4jq-h2w9-997c | vite | ≤ 5.4.19 | Public-dir symlink `server.fs.deny` bypass. **Dev-only**: same rationale as #1. |
| 12 | MED 6.0 | CVE-2025-62522 / GHSA-93m4-6634-74q7 | vite | ≤ 5.4.20 | Backslash `server.fs.deny` bypass on Windows. **Dev-only**: same rationale as #1. |
| 13 | MED 6.3 | CVE-2026-39365 / GHSA-4w7w-66w2-5vf9 | vite | ≤ 6.4.1 | (Duplicate of #1 — second range/manifest match for the same advisory.) **Dev-only**: same rationale as #1. |
| 14 | MED 6.1 | CVE-2026-41305 / GHSA-qx2v-qp2m-jg93 | postcss | < 8.5.10 | XSS via `</style>` injection during CSS processing. **Build-time only**: postcss is loaded by Vite at `vite build` to apply Tailwind + autoprefixer plugins per `src/nucleus/workbench/frontend/postcss.config.js`. The output is a static bundle shipped under `src/nucleus/workbench/static/assets/`. postcss never runs at request time. PR #7 in this repo bumps postcss to 8.5.10; that PR remains open for founder review. |

---

## Re-open conditions (any of these = re-open the alert + re-evaluate)

| Condition | Affects |
|---|---|
| Any import of `dagster_duckdb`, `dagster_snowflake`, `dagster_gcp`, `dagster_deltalake`, `dagster_snowflake_polars`, or another Dagster I/O manager package appears under `src/nucleus/` | Alert #3 |
| Any import of Dagster notebook handlers OR `nucleus` ships a `dagster api grpc` entry point OR `dagster webserver` exposed via Docker compose | Alert #2 |
| `vite preview` OR `vite dev` invoked as a production ENTRYPOINT/CMD in any Dockerfile under `docker/` | Alerts #1, #4–#13 |
| Workbench moves to runtime CSS processing (any new direct `import 'postcss'` outside the build tool-chain) | Alert #14 |

---

## Upstream-fix PRs (pending founder review)

| PR | Fixes | Status |
|---|---|---|
| [#7](https://github.com/mtoanng/nucleus/pull/7) | postcss 8.4.49 → 8.5.10 (Alert #14) | Open; CI re-runs needed after CHANGELOG-check Dependabot exemption lands |
| [#8](https://github.com/mtoanng/nucleus/pull/8) | vite 5.4.11 → 6.4.2 (Alerts #1, #4–#13) | Closed pending ADR — major version bump triggers Constraint #11 ADR requirement; founder will redraft as a coordinated v0.2.1 PR after the v5 → v6 breaking-change audit |

The dismissals above stand even after PRs #7/#8 land. Once the bumps are merged, GitHub will mark the alerts auto-resolved; the dismissal is harmless overlap.

---

*Refresh this doc when: a new Dependabot alert is dismissed; a re-open condition fires; or the verification greps return unexpected results.*
