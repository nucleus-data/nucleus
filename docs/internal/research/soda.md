# Research: Soda Core

> **Component status in Nucleus**: **v0.5+ OPTIONAL data-quality wrap. Not in v0.1.** v0.1 ships native `@nucleus.check` (Python decorator) + `@nucleus.contract` (schema) per `nucleus_architecture_v4.1.md` §12.2 / §12.5. Soda is forward-leverage research — an *escape hatch* for teams arriving with existing Soda projects, not a replacement for `@nucleus.check`. Per `AGENTS.md §4`: *"data quality framework → native `@nucleus.check` (v0.1) / Soda Core (v0.5+ optional)"*.
> **Pin candidate (if v0.5 fires)**: `soda-core==3.5.6` — **last Apache-2.0 release**, uploaded 2025-09-24 (PyPI verified 2026-05-13). **Not pinned in `pyproject.toml` today.**
> **License**: **MIXED — boundary moved.** v3.x = **Apache-2.0**; v4.x (current main, latest 4.10.0 / 2026-05-12) = **Elastic License 2.0** (source-available; not OSI-approved; hosted-service-restricted). See §1.2 — this is the critical finding.
> **JVM-free**: YES (pure Python). **Research date**: 2026-05-13. **Used in**: nowhere.

Docs anchor per AGENTS.md Constraint #10. Soda is the **defer-and-watch** case: if Soda owns the SodaCL ecosystem at v0.5 time, importing existing user projects matters; if Soda Cloud captures all OSS energy (happening in v4), wrapping costs more than building. We never make Soda the recommended way to author checks.

---

## §1. At a glance

- **Maintainer**: Soda Data N.V. (Tom Baeyens et al.)  •  **GitHub**: https://github.com/sodadata/soda-core  •  **Stars**: ~2.3k (2026-05-13)  •  **Position**: L2 Coordination — optional `@nucleus.check(engine="soda")` in v0.5+. Hidden behind `ctx`; users never `import soda`.

### §1.1 Three Sodas — never conflate them

| Product | What it is | License | In scope? |
|---|---|---|---|
| **Soda Core (OSS)** | Python lib + `soda` CLI; SodaCL parser + scan engine | v3.x Apache-2.0 / v4.x ELv2 | **§4.2 — v0.5+ optional wrap** |
| **Soda Library** | Proprietary superset; anomaly, group-by, reconciliation, schema evolution | Proprietary (45-day trial → paid) | **NEVER** — closed extension |
| **Soda Cloud** | SaaS; scan history, no-code checks, agreements, alerts, "Ask AI" GPT SodaCL assistant | Proprietary (SaaS) | **NEVER** — Constraint #6 (OIDC-only) |
| **Soda Agent / Runner** | Deployment products for Cloud | Proprietary | **NEVER** — not OSS |

Per the SodaCL feature-availability matrix (https://docs.soda.io/soda-cl/soda-cl-overview.html): no-code checks, agreements, and most anomaly checks explicitly **`✖️ Requires Soda Core`** — NOT in the OSS lib. Any "Cloud" feature is off-table.

### §1.2 v3 → v4: license + design break (read before anything else)

Soda Core changed both license and data model at v4.0 (2026-01-28). THE critical fact.

| Dimension | v3.x (legacy, bug-fix) | v4.x (current main) |
|---|---|---|
| **License** | Apache-2.0 (`/v3/LICENSE`) | Elastic License 2.0 (`/main/LICENSE`) |
| **PyPI classifier** | `OSI Approved :: Apache` (3.5.6) | `"Proprietary"` (4.7.0; ELv2 not OSI-approved) |
| **Data model** | SodaCL YAML DSL | Data Contracts YAML (total redesign) |
| **Latest** | 3.5.6 (PyPI, 2025-09-24) | 4.10.0 (GitHub, 2026-05-12) |
| **DuckDB connector** | `soda-core-duckdb==3.5.6` → **`duckdb<1.1.0`** — **CONFLICTS with `duckdb==1.1.3`** (§8.2) | NEEDS VERIFICATION |

**ELv2 is NOT open source by OSI** (https://raw.githubusercontent.com/sodadata/soda-core/main/LICENSE): free to use/modify, but ❌ "may not provide … as a hosted or managed service" (anti-cloud clause; blocks Nucleus Cloud shipping managed Soda) and ❌ "may not … circumvent the license key functionality" (v4 ships runtime DRM). **Net**: if we wrap, we wrap v3.x only. v4 is forbidden by Pillar #2 / Pillar #5 the moment Nucleus has a Cloud product.

---

## §2. What Soda Core is, in Nucleus terms

A Soda **scan** runs a list of **checks** against a **data source**, returns pass/fail/error.

| Soda term | Nucleus term | Surface (v0.5+, IF we wrap) |
|---|---|---|
| `checks.yml` (SodaCL file) | collection of `@nucleus.check` defs | parsed at adapter load |
| `checks for <dataset>:` block | checks attached to one **asset** | single-asset only at v0.5 |
| `scan` (a run) | check **materialization** | called by AMA after upstream commit |
| `configuration.yml` | derived from `ctx.engine` | never user-facing |
| Soda Cloud Trace | run id | mapped to our run id; we do NOT POST to Cloud |
| `from soda.scan import Scan` | adapter-internal | users never `import soda` |

---

## §3. Official documentation URLs

Verified by `WebFetch` 2026-05-13.

- **OSS overview (v3)**: https://docs.soda.io/soda-core/overview-main.html — "free, open-source"; "Compatible with **basic** SodaCL checks"
- **SodaCL ref + feature-availability matrix** (authoritative for what's free): https://docs.soda.io/soda-cl/soda-cl-overview.html
- **v3 README + pin guidance**: https://github.com/sodadata/soda-core/tree/v3
- **LICENSES**: v3 Apache-2.0 https://raw.githubusercontent.com/sodadata/soda-core/v3/LICENSE • main ELv2 https://raw.githubusercontent.com/sodadata/soda-core/main/LICENSE
- **GitHub releases**: https://github.com/sodadata/soda-core/releases • **PyPI**: https://pypi.org/project/soda-core/ • **DuckDB connector**: https://pypi.org/project/soda-core-duckdb/

**404 on 2026-05-13** (flag for AI): `https://docs.soda.io/soda-core/configuration.html` — docs reorganized around v3/v4; use `https://github.com/sodadata/soda-core/blob/v3/docs/configuration.md`. No central exceptions reference — read `soda.common.exceptions` in v3.5.6 source at v0.5 time.

---

## §4. Position in Nucleus

This section answers: **why doesn't v0.1 ship Soda?** All four subsections cite architecture v4.1.

### §4.1 Why NOT in v0.1

v4.1 §12.2 already includes `@nucleus.check` (Python decorator) in the v0.1 catalog. Combined with `@nucleus.contract` (§12.5, schema), this covers the SodaCL check shapes real beachhead users hit in their first 30 days:

| SodaCL check | Native v0.1 equivalent | Coverage |
|---|---|---|
| `row_count > 0` / `between X and Y` | `@nucleus.check` w/ `df.shape[0]` | ✅ |
| `missing_count(col) = 0` | Iceberg `NOT NULL` + `@nucleus.contract` | ✅ (rejected at write) |
| `duplicate_count(col) = 0` | `@nucleus.check` w/ `df.unique(col)` | ✅ |
| `invalid_count(col)` regex | `@nucleus.check` w/ Polars `str.contains` | ✅ |
| `schema` (forbidden cols / wrong type) | `@nucleus.contract` schema dict | ✅ **pre-write**, not post-hoc |
| FK: `values in (X) must exist in Y (Z)` | `@nucleus.check` w/ SQL anti-join via `ctx.sql` | ✅ |
| `freshness(col) < 1d` | v0.5+ contract `freshness` per §12.5 | ⏸ Soda also paid-gates |
| `anomaly detection for row_count` | Not in scope (requires stats model) | ❌ (Soda gates behind `soda-core-scientific` too) |

**80% rule**: native `@nucleus.check` covers all eight for ~300 LOC. Adding Soda in v0.1 would (1) add YAML DSL alongside Python (§4.3 vocab cost), (2) add ~7 transitive deps (§8.1), (3) cost ~250-400 ms cold-start hitting PoC #4's `<10s` budget (NEEDS VERIFICATION), (4) **block on `duckdb==1.1.3`** connector conflict (§8.2), (5) buy nothing measurable on the <30-min beachhead. 8-question gate fails Q2/Q6/Q7/Q8. **Defer.**

### §4.2 v0.5+ Soda integration as OPTIONAL

Forward-leverage case: a 5-15 engineer team adopts Nucleus **after** investing 6 months in a `checks.yml` repo. We must not force them to rewrite. Conceptual surface (**NEEDS VERIFICATION** at design time):

```python
@nucleus.check(engine="soda")
def orders_quality(ctx):
    return ctx.checks.run_sodacl("checks/sales.yml")

# Or asset-attached:
@nucleus.asset(checks=["checks/sales.yml"])
def fct_orders(ctx): ...
```

Target adapter `coordination/soda_check_adapter.py` ≤**300 LOC** (smaller than dlt — we only call `Scan.execute()` and shape results). We **read** SodaCL; we never **recommend** writing it.

Wrap viable iff: author-side free (✅ v3 Apache 2.0); ship-side free for Nucleus OSS (✅ if we pin v3.5.6); **run-side free for Nucleus Cloud only on v3 — NO on v4 due to ELv2 hosted-service clause** (§8.3); adds value only as import path for existing Soda users.

### §4.3 SodaCL (YAML DSL) vs `@nucleus.check` (Python decorator)

SodaCL example (https://docs.soda.io/soda-cl/soda-cl-overview.html) and native Nucleus equivalent:

```yaml
checks for dim_customer:
  - row_count between 10 and 1000
  - missing_count(birth_date) = 0
  - invalid_percent(phone) < 1 %:
      valid format: phone number
  - duplicate_count(phone) = 0
```

```python
@nucleus.check(asset="dim_customer")
def basic_quality(df):
    assert 10 <= df.shape[0] <= 1000
    assert df.filter(pl.col("birth_date").is_null()).shape[0] == 0
    assert df.filter(~pl.col("phone").str.contains(PHONE_RE)).shape[0] / df.shape[0] < 0.01
    assert df.unique("phone").shape[0] == df.shape[0]
```

| Axis | SodaCL DSL | `@nucleus.check` Python |
|---|---|---|
| Vocabulary footprint | Adds `checks for`, `missing_count`, `invalid_percent`, `valid format`, `agreement`, `metric` | None — Polars / DuckDB / Python |
| LLM authorability | Good (Soda's GPT SodaCL assistant is Cloud-only) | Excellent (Pillar #3) |
| Composable w/ Python logic | Limited — escapes to "SQL Failed Rows" | Native |
| Pre-write enforcement | **No** — runs post-scan; bad data already committed | **Yes** — contracts gate write (v4.1 §6.3) |
| Schema-check warm-up | Needs ≥2 measurements (1st = `[NOT EVALUATED]`) | None |
| IDE support | YAML, linter-less | Cursor + mypy strict |

**Decision per AGENTS.md §7**: Python decorator is v0.1. If SodaCL is exposed at v0.5+, it stays opt-in, scoped to imported existing Soda projects, and never the recommended way for new users.

### §4.4 Integration with `@nucleus.asset`

Per v4.1 §6.3, the v0.5+ Soda wrap slots into the Asset Materialization Adapter post-commit (after pre-write contract → atomic commit → OpenLineage → registry → native `@nucleus.check`), then translates scan results to `NucleusCheckResult` / `NucleusError`.

**Error translation** (mandatory per v4.1 §6.4):

| Soda failure | `NucleusError` target | Detection |
|---|---|---|
| Scan `result == "fail"` (data bad) | `NucleusCheckFailed` (asset + check name + metric in `cause`) | `Scan.has_check_fails()` — NEEDS VERIFICATION vs v3.5.6 |
| Scan `result == "error"` (Soda errored) | `NucleusInternalError` (our wrap, our problem) | `Scan.has_error_logs()` |
| SodaCL YAML parse failure | `NucleusConfigError` w/ file+line+col | `soda.common.exceptions.SodaSqlClError` — NEEDS VERIFICATION |
| DB connection failure | `NucleusEngineError` | Underlying `duckdb.ConnectionException` per `docs/internal/research/duckdb.md` §6 |

**No `soda.` / `SodaCL` / `Scan` substring in any user-facing error string.** Extend `scripts/dagster_leak_check.py`. Adapter MUST NOT expose Soda Cloud trace IDs or Library-only / no-code / agreement concepts; detect in YAML and raise `NucleusUnsupportedCheckError` pointing at the feature-availability matrix.

---

## §5. Programmatic API surface (what we'd wrap if v0.5 fires)

Against `soda-core==3.5.6` only. Entry point: `from soda.scan import Scan` (per docs programmatic-checks example). Adapter constructs one `Scan` per asset materialization, then chains: `set_data_source_name(name)` → `add_configuration_yaml_file(path)` (we generate minimal config from `ctx.engine`; never user-edited) → `add_sodacl_yaml_file(path)` / `add_sodacl_yaml_files(dir)` pointing at user's `checks.yml` → `add_variables(vars)` for `${NOW}` etc. → `scan.execute()` (NEEDS VERIFICATION — docs example doesn't show the trigger explicitly) → `scan.has_check_fails()` / `get_logs_text()` (NEEDS VERIFICATION vs v3.5.6 source) for translation routing.

**Not used**: Soda-Cloud-shaped methods (`execute_with_cloud_publish` etc.; names illustrative — **DO NOT verify**). Anything from `soda_library` package — proprietary.

---

## §6. Performance characteristics

**No Nucleus benchmark yet** — repeat under v0.5 PoC before quoting. Cold start `import soda.scan` ≈ 250-400 ms (NEEDS VERIFICATION); lazy-import in adapter only. Soda is a **SQL-generator** (per v3 README: "aggregated SQL queries"), not a row scanner — time ≈ sum of generated SQL latencies; memory low (scalar aggregations only). `missing_count(col)` ≈ same query plan as `polars.LazyFrame.filter().count()`; overhead is YAML parse + result shaping (single-digit ms/scan). Anomaly detection requires `soda-core-scientific` extra (scipy + numpy) — out of v0.5 wrap scope.

---

## §7. Swap-target analysis (v4.1 §9.3)

### §7.1 The in-house alternative is already the v0.1 default

`@nucleus.check` (Python decorator, v0.1 native, ~300 LOC) IS the swap target. If Soda becomes unviable, we **codemod-out**, not replace. Ship `nucleus migrate from-sodacl` only if telemetry shows Soda adoption > 5%. Unusual case where the swap target is *upstream of* the wrap — we don't maintain two ways to author the same thing.

### §7.2 External alternatives

| Candidate | License | Cost to swap from `soda-core==3.5.6` | Verdict |
|---|---|---|---|
| **Great Expectations** | Apache-2.0 (NEEDS VERIFICATION) | Medium — different DSL ("expectations"); large deps; ~10k stars | **Acceptable swap.** Vocab cost — "test suite"/"expectations" banned per AGENTS.md §7; adapter must remap to "check". |
| **Pandera** | MIT | Low — decorator-based; close to `@nucleus.check`/`@nucleus.contract` | **Watch** — strongest competitor to native v0.1 surface. |
| **dbt-tests** | Apache-2.0 | Low — but reintroduces dbt; conflicts with v4.1 §11 | **Reject.** |
| **PyArrow + Polars** | Apache-2.0 / MIT | Already in-tree | Already used by `@nucleus.contract` v0.1. Schema enforcer, not framework. |
| **Custom — fully native** | Nucleus | Already in v0.1 (`@nucleus.check`) | **The default.** |

**Verdict**: native `@nucleus.check` is v0.1 path + long-term default. Soda is opt-in wrap for migrating users. GE is the only external swap worth tracking; we do NOT pre-build a GE adapter. Stranded risk = **low** because we never made Soda the recommended path.

---

## §8. Compatibility with Nucleus pins (2026-05-13)

The DuckDB conflict alone is enough to defer the wrap until either Soda v3 bumps DuckDB or we adopt a different connection strategy.

### §8.1 Dep matrix (soda-core==3.5.6, the only candidate)

Against our existing pins: `jinja2==3.1.5` ∈ `<4.0,>=2.11` ✅; `click==8.1.7` ∈ `~=8.0` ✅; `opentelemetry-api==1.29.0` ∈ `<2.0.0,>=1.16.0` ✅; Python `>=3.11,<3.13` ⊃ Soda's `>=3.7` ✅; Windows wheel `py3-none-any.whl` published ✅.

New transitives (**7+ total** — flag in v0.5 ADR): `ruamel.yaml<0.18.0,>=0.17.0`; `antlr4-python3-runtime~=4.11.1` (~2 MB; SodaCL parser uses ANTLR); `pydantic<3.0.0,>=2.0.0` (invasive — adapter must import only `soda.scan`, not pydantic models); plus `sqlparse`, `inflect`, `python-dotenv`, `requests` (common).

### §8.2 The DuckDB connector — BLOCKING

`soda-core-duckdb==3.5.6` (PyPI 2026-05-13) requires **`duckdb<1.1.0`** — **HARD CONFLICT** with our `duckdb==1.1.3` (pip resolver fails).

Options at v0.5 time: (1) ❌ downgrade DuckDB — breaks default engine; (2) ⚠ ship wrap without DuckDB — Postgres-only half-feature; (3) ❓ bypass connector with injected `DataSourceConnection` — NEEDS VERIFICATION v3.5.6 supports it (likely not); (4) ✅ file PR to v3 branch bumping `duckdb>=1.0,<2.0` (low-priority for maintainers given v4 focus).

**Therefore**: v0.5 wrap is realistically Postgres-only or v4-or-bust. v4 + Nucleus Cloud = legal blocker. **Defer wrap until evidence demands it.**

### §8.3 License compatibility with Nucleus's Apache-2.0 distribution

`pyproject.toml:20`: `license = { text = "Apache-2.0" }`. **`soda-core==3.5.6` (Apache-2.0)**: ✅ fully compatible; permissive transitive redistribution fine. **`soda-core` v4.x (ELv2)**: ⚠ not OSI-approved, hosted-service-restricted. Textually mixable, but (a) downstream users hosting Nucleus as SaaS would violate ELv2's anti-cloud clause and (b) Nucleus Cloud (v0.5+) would violate it. **Net**: ban v4 in the adapter; assert `soda.__version__.startswith("3.")` at import.

### §8.4 Maintenance + survival risk

v3.5.6 last release **2025-09-24** (~8 months stale; v3 branch is pure bug-fix per maintainers). v4 cadence is 10 releases in ~4 months (4.0 → 4.10.0; active but breaking). Stars 2.3k; **forks 0** per GitHub fetch (unusual — NEEDS VERIFICATION at v0.5 time via `/network/members`). Bus factor: small Soda Data N.V. employee team. Vendor-controlled OSS. v3 EOL risk ≈ moderate-high over 24 months.

---

## §9. Decision log

**Why Soda Core is v0.5+ optional, never v0.1, and never replaces `@nucleus.check`:**

- **v0.1**: native `@nucleus.check` + `@nucleus.contract` cover the 8 SodaCL shapes most beachhead users hit (§4.1). Soda buys nothing on the 30-min metric, costs 7+ deps + DSL vocab cost + DuckDB pin conflict. **Defer.**
- **v0.5+ optional**: wrap iff telemetry shows ≥5% of beachhead teams arrive with `checks.yml` AND v3 line has a working DuckDB connector (or we ship Postgres-only). Adapter ≤300 LOC. **Conditional.**
- **Never blocking**: at v0.5+, `engine="soda"` is one of N quality engines alongside native `@nucleus.check` (default). New-check authoring always uses the Python decorator; SodaCL is read-only from Nucleus's POV.
- **Never wrap v4 (ELv2)**: hosted-service clause conflicts with Nucleus Cloud; DRM conflicts with Pillar #2. If v3 dies, **codemod-out**, don't upgrade into ELv2.
- **Never wrap Soda Library / Cloud**: proprietary; conflicts with Constraint #6 (OIDC-only) and `AGENTS.md §0`.

**Triggers that would fire v0.5+ wrap work**: (1) ≥5% of `nucleus init` projects contain `checks.yml`/`soda` install; (2) ≥3 distinct GitHub issues requesting Soda import; (3) v3 DuckDB connector compatible with `duckdb>=1.0,<2.0`; (4) ELv2 reversed or v3 dual-licensed back (improbable).

**Decision ADR**: NOT yet written. If v0.5 fires this work, open `docs/decisions/ADR-NNN-soda-v05-optional-wrap.md` referencing this research.

---

## §10. Known gotchas + AI hallucination risks

### Likely AI hallucinations (verify before merge)

- ❌ "Soda Core is Apache 2.0." — TRUE for **v3.x only**; v4.x is ELv2. Always specify version.
- ❌ `pip install soda-core` (no pin) — pulls latest = v4.10.0 = ELv2. Always pin to v3.x.
- ❌ `from soda_core.scan import Scan` — wrong; correct is `from soda.scan import Scan`.
- ❌ `Scan.add_check(check_str: str)` — does not exist; checks come from YAML via `add_sodacl_yaml_file(path)`.
- ❌ `scan.run()` — fabricated; docs show `scan.execute()` (NEEDS VERIFICATION).
- ❌ Anomaly detection in OSS Core — NO; requires `soda-core-scientific` extra OR Soda Library.
- ❌ "Soda Cloud is free" — NO. `from soda.library import …` — proprietary, never import.
- ❌ First-party `dbt-soda` package — does not exist; community glue only.
- ❌ `engine="soda"` as v0.1 API — NOT in v0.1 per v4.1 §12 + §18.

### Real gotchas from official docs

- **"test" vs "check" vocab mismatch.** Soda OSS overview opens with "test data quality"; AGENTS.md §7 bans "test" for asset-attached checks. Adapter docs MUST translate to "check" in any user-facing surface.
- **Schema check needs ≥2 measurements** before non-`[NOT EVALUATED]` result. Native `@nucleus.contract` has no such warm-up — flag divergence.
- **`${NOW}` variables** runtime-bound via `scan.add_variables(...)`; cannot be used in agreement-mode (Cloud-only).
- **Filter blocks** (`filter customer [daily]: where: ...`) coexist with `checks for ...` in the same YAML. Adapter must parse + propagate or reject.
- **Dialect-specific SQL generation**: v4.5+ release notes mention dialect-specific SQL; cross-engine portability NOT guaranteed.
- **License-key DRM clause** (ELv2 §Limitations) implies v4 has runtime gating. Adapter ships v3-only; rejects v4 at import.

### CI hardening (if v0.5+ wrap fires)

Extend `scripts/check_vocabulary.py` to ban `SodaCL`, `Soda Cloud`, `Soda Library`, `test data quality` in user strings; extend `scripts/dagster_leak_check.py` to catch `from soda.`, `soda.scan.`, `Scan(`, `SodaSqlClError`; pin `soda-core` + connector together (mismatched = release blocker); adapter import gate: `assert soda.__version__.startswith("3.")`.

---

## §11. Next reads when v0.5 work starts (NOT NOW)

- [ ] **Trigger telemetry**: ≥5% of beachhead teams installing `soda-core`? If no, defer further; do not open ADR.
- [ ] **v3 liveness + DuckDB connector**: any v3 bugfix after 3.5.6? If frozen >12 months → treat EOL; pivot codemod to GE/Pandera. Re-check `soda-core-duckdb` constraint; if still incompatible, v0.5 wrap is Postgres-only.
- [ ] **API verification**: `Scan.execute()` / `Scan.has_check_fails()` against v3.5.6 source. Update §5.
- [ ] **Performance benchmark**: 1M-row missing_count via Soda-on-DuckDB vs native `@nucleus.check`. >20% overhead → "import-only" wrap.
- [ ] **`nucleus migrate from-sodacl` codemod design**: row_count/missing/duplicate/schema mechanical; anomaly + reconciliation not codemod-able.

---

## §12. Useful links

- https://docs.soda.io/soda-core/overview-main.html — OSS overview (v3). **Bookmark.**
- https://docs.soda.io/soda-cl/soda-cl-overview.html — SodaCL DSL + feature-availability matrix. Authoritative for what's free.
- https://github.com/sodadata/soda-core/tree/v3 — v3 README + pin guidance
- https://raw.githubusercontent.com/sodadata/soda-core/v3/LICENSE — Apache-2.0 (v3) • https://raw.githubusercontent.com/sodadata/soda-core/main/LICENSE — Elastic License 2.0 (v4)
- https://pypi.org/project/soda-core/ • https://pypi.org/project/soda-core-duckdb/ • https://github.com/sodadata/soda-core/releases

---

*Last verified: 2026-05-13 against `soda-core==3.5.6` (v3, Apache-2.0) and `soda-core==4.10.0` (v4, ELv2). Re-verify when v0.5 telemetry fires the wrap decision, before pinning, or on any major bump. Log any AI-fabricated Soda APIs to [`docs/internal/research/ai_hallucinations.md`](./ai_hallucinations.md).*

*This doc is **forward-leverage research**, NOT a blocking artifact for v0.1. Per `AGENTS.md §11.1` (phase gate) and v4.1 §18 (roadmap), data-quality wrap work cannot start until PoC #1 (Dagster Error Translation) passes AND v0.5 telemetry triggers fire per §9.*
