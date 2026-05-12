# Learning Path — Building Nucleus as a Junior Data Engineer

> **Audience**: You — the solo founder building Nucleus with me as your pair.
> **Style**: Honest, sequential, project-specific. Not generic.
> **Time**: Budget ~6-10 hrs/week of focused learning alongside coding.
> **Companion**: [`AGENTS.md`](../../AGENTS.md), [`docs/conventions/engineering.md`](../conventions/engineering.md), [`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md)

This is **your** doc. It's not in the public roadmap. It exists because building a data engineering platform requires deeper knowledge than using one, and you're going to grow into that knowledge as we go.

**Two principles**:
1. **Learn what you need, when you need it.** Don't pre-load 600 hours of theory.
2. **Build to learn, learn to build.** Each module ends with a concrete exercise that becomes useful Nucleus code.

---

## §0. What you already have (probably)

You said you're a junior DE. I'll assume you have:

- ✅ Python — variables, functions, classes, basic stdlib (`os`, `pathlib`, `json`)
- ✅ SQL — `SELECT`, `JOIN`, `GROUP BY`, basic window functions
- ✅ Git — clone, commit, push, branch, basic merge
- ✅ Command line basics (Windows PowerShell counts; Unix-like commands you may need help with)
- ✅ Some exposure to ETL — you've moved data from A to B somehow

What I'm **not** assuming:
- ❌ Iceberg / Lakehouse internals
- ❌ Dagster
- ❌ Apache Arrow
- ❌ Type theory / Python generics
- ❌ Building distributable Python packages
- ❌ Writing libraries vs writing scripts (these are different)

If anything in §0 is wrong (e.g. you actually do know Iceberg), tell me and I'll adjust.

---

## §1. The 4-Module learning ladder

Each module corresponds to a tier in our roadmap. You don't need to finish a module before starting the next — they're stacked but interleaved.

| Module | Trigger | Time | What you'll learn |
|--------|---------|------|-------------------|
| **M0: Foundations** | Now | 10-15 hrs | Project tooling, Python features we'll use, decision-making |
| **M1: Tier 0 prep** | Before Heartbeat code | 20-30 hrs | Iceberg, Arrow, DuckDB internals |
| **M2: Tier 1 prep** | Before v0.1 work | 30-40 hrs | Dagster internals, error translation, type systems |
| **M3: Tier 2+** | Later | open-ended | FastAPI, AI integration, performance profiling |

---

## §M0. Foundations (NOW, ~10-15 hrs)

You'll feel the difference between "I can write Python" and "I can write a Python library other people will install". This is that bridge.

### M0.1 Python features Nucleus uses heavily

You may or may not know these. Spend 30 min on each unfamiliar one.

| Feature | Why we use it | Read |
|---------|---------------|------|
| **Type hints (strict)** | mypy catches bugs before runtime; AI generates better code from typed sigs | https://docs.python.org/3/library/typing.html (sections "Type aliases", "Generic", "Protocol", "Annotated") |
| **`Protocol`** | Defines interfaces structurally (no inheritance needed). `Engine` is a Protocol. | https://typing.readthedocs.io/en/latest/spec/protocol.html |
| **`dataclass` & `msgspec.Struct`** | Lightweight typed records; `NucleusError` uses these | https://docs.python.org/3/library/dataclasses.html and https://jcristharif.com/msgspec/structs.html |
| **`pathlib.Path`** | Replaces `os.path` everywhere. Cleaner. | https://docs.python.org/3/library/pathlib.html |
| **`tomllib`** | Stdlib TOML reader (Python 3.11+). Used in our scripts. | https://docs.python.org/3/library/tomllib.html |
| **`ast` module** | Parses Python code as data. Our scripts use it for layering check. | https://docs.python.org/3/library/ast.html |
| **Decorators** | `@nucleus.asset` is a decorator. Understand how they work. | https://realpython.com/primer-on-python-decorators/ |
| **Context managers (`with`)** | Resource cleanup. Our DB connections use them. | https://docs.python.org/3/library/contextlib.html |
| **f-strings & format spec** | Required by our style guide. | https://docs.python.org/3/reference/lexical_analysis.html#f-strings |
| **`pytest` fundamentals** | Our only test framework. | https://docs.pytest.org/en/stable/getting-started.html |

**You know enough when**:
- You can read `scripts/check_pinning.py` end-to-end and explain every line.
- You can write a `Protocol` defining an `Engine` interface with two methods.

### M0.2 Project tooling crash-course

| Tool | What | Read |
|------|------|------|
| **`uv`** | Fast Python package manager. We'll use it for dev envs. | https://docs.astral.sh/uv/ |
| **`ruff`** | Linter + formatter in one. | https://docs.astral.sh/ruff/ |
| **`mypy` strict mode** | Type checker. Read the "Common issues" section. | https://mypy.readthedocs.io/en/stable/common_issues.html |
| **`pre-commit`** | Runs checks before each commit. | https://pre-commit.com/ |
| **GitHub Actions** | Our CI. | https://docs.github.com/en/actions/quickstart |
| **Conventional Commits** | Our commit format. | https://www.conventionalcommits.org/en/v1.0.0/ |

**Hands-on exercise** (2-3 hrs):
1. Create a new venv: `python -m venv .venv` (Windows) / activate it.
2. `pip install pre-commit ruff mypy pytest`.
3. Run `pre-commit run --all-files`. See what passes / fails.
4. Run `python scripts/check_pinning.py` — does it report PASS or FAIL? Read the output carefully.
5. Run `python scripts/loc_budget.py --report`. Total LOC should be ~0 (no source yet).

### M0.3 Reading our own architecture

Read in this order, ~6 hrs total:

1. [`README.md`](../../README.md) — 15 min. The vision.
2. [`AGENTS.md`](../../AGENTS.md) — 45 min. The 11 constraints. Memorize them.
3. [`docs/architecture/C4_context.md`](../architecture/C4_context.md) — 30 min. Who uses Nucleus and why.
4. [`docs/architecture/C4_container.md`](../architecture/C4_container.md) — 45 min. The 5 layers in detail.
5. [`docs/architecture/sequence_error_translation.md`](../architecture/sequence_error_translation.md) — 45 min. The most important sequence.
6. [`docs/conventions/engineering.md`](../conventions/engineering.md) — 1 hr. Skim, then deep-read §3 (layers), §4 (errors), §7 (interfaces).
7. [`docs/decisions/ADR-001-no-iceberg-commit-service.md`](../decisions/ADR-001-no-iceberg-commit-service.md) — 20 min. The ADR pattern.
8. [`nucleus_architecture_v4.1.md`](../../nucleus_architecture_v4.1.md) — 2-3 hrs. The source-of-truth. Don't try to remember everything; just orient.

**You know enough when**:
- You can answer: "Why are there exactly 5 layers, not 4 or 6?"
- You can recite the 11 hard constraints from memory.
- You can explain why we don't build a custom Iceberg commit service.

### M0.4 How to work with me (your AI pair)

This meta-skill saves enormous time. Spend 1-2 hrs internalizing.

**When you're stuck**, ask me in this format:
1. **What I'm trying to do** (1 sentence).
2. **What I've already tried** (bullet points).
3. **What's actually happening** (error message, screenshot, or quote).
4. **What I think the issue is** (your hypothesis — even if wrong, this anchors my reply).

**When you want me to write code**, prefer this format:
1. **Constraint**: "Per AGENTS.md #X" or "Per engineering.md §Y" — name the rule.
2. **Goal**: One sentence on the outcome.
3. **Interface**: Show the function signature you want, even if it's a sketch.
4. **Boundaries**: What I should NOT change (existing tests, other modules).

**Bad prompt**: *"Write the ctx SDK."*
**Good prompt**: *"Per the ctx SDK Spec §3.2, implement just `ctx.copy_from(source, *, table, target, mode='replace')` for Postgres only. Return a `Result` struct. Don't touch anything in coordination/. Stop after the function is written; I'll write the tests."*

**When I propose something**, treat it like a code review:
- Is it consistent with all 11 constraints? Check explicitly.
- Did I cite official docs (Constraint #10)? If not, push back.
- Did I invent an API? (Verify the parameters actually exist in the library version we pinned.)
- Is the LOC count reasonable?

We will both make mistakes. Catching mine is part of the workflow.

---

## §M1. Tier 0 prep — The data foundations (~20-30 hrs)

When you've finished M0, start M1. You need this before we write the first line of Heartbeat code.

### M1.1 Apache Arrow (~5 hrs)

Arrow is the *pivot* type system. Every byte of data in Nucleus passes through Arrow.

**Read**:
- https://arrow.apache.org/docs/python/getstarted.html — 1 hr
- https://arrow.apache.org/docs/python/data.html — 1 hr (data types, Table, RecordBatch)
- https://arrow.apache.org/docs/python/ipc.html — 30 min (zero-copy IPC)

**Hands-on** (2-3 hrs):
- Build a `pa.Table` from a dict of lists. Inspect schema. Cast columns. Print as Pandas, then Polars.
- Write 1000 rows to Parquet using `pyarrow.parquet.write_table`. Read back. Verify equality.
- Convert a `pa.Table` to a `polars.DataFrame` and back. Confirm zero-copy by inspecting buffer addresses.

**You know enough when**:
- You can name 3 reasons Arrow > Pandas as the in-memory format.
- You can list every Arrow type we use (see `docs/patterns/type_mapping.md` §3).
- You can write and read Parquet via PyArrow without help.

### M1.2 Apache Iceberg (~6-8 hrs)

Iceberg is the *table format* — our open contract with the world.

**Read** (in order):
1. https://iceberg.apache.org/docs/latest/ — 30 min overview
2. https://iceberg.apache.org/spec/ — 2 hrs (yes, read the SPEC; sections 1-4 minimum)
3. https://py.iceberg.apache.org/ — 2 hrs (the Python binding we use)
4. https://py.iceberg.apache.org/api/ — 1 hr (the API reference)

**Concepts to internalize**:
- **Snapshots** — every commit creates a new immutable snapshot
- **Manifests** — files listing the data files in a snapshot
- **Metadata file** — JSON pointer-of-pointers; atomic swap is the commit
- **Catalogs** — what swaps the pointer atomically (we use filesystem catalog for v0.1)
- **Schema evolution** — adding/renaming columns is metadata only

**Hands-on** (3-4 hrs):
- `pip install pyiceberg`
- Create a local catalog (filesystem-based).
- Define a schema, create a table, append a few PyArrow batches.
- Inspect the resulting directory: open `metadata/v1.metadata.json`, look at manifests.
- Time-travel: append twice, read by snapshot_id of the first append.
- Schema-evolve: add a column. Re-read. Confirm new column is null in old rows.

**You know enough when**:
- You can draw the relationship between metadata files, manifests, and data files on a whiteboard.
- You understand WHY Iceberg commits are atomic (single-pointer swap).
- You can explain "graduation" (Mode 1 in our yield-to-giants strategy) in your own words.

### M1.3 DuckDB (~3-4 hrs)

DuckDB is our default SQL engine. Embedded, in-process, fast.

**Read**:
- https://duckdb.org/docs/api/python/overview — 30 min
- https://duckdb.org/docs/data/parquet/overview — 30 min
- https://duckdb.org/docs/extensions/iceberg — 30 min (key for us)

**Hands-on** (2-3 hrs):
- `pip install duckdb`
- Query a Parquet file directly: `duckdb.sql("SELECT * FROM 'data.parquet'")`.
- Query an Iceberg table via DuckDB's iceberg extension. Note: this is the SAME table you wrote in M1.2!
- Use DuckDB's PyArrow interop: `conn.from_arrow(table).filter("x > 0").to_pl()`.

**You know enough when**:
- You can list 3 things DuckDB does better than Pandas.
- You can use DuckDB's PyArrow interop in both directions.

### M1.4 Polars (~3-4 hrs)

Polars is our DataFrame engine — Rust-fast, lazy by default.

**Read**:
- https://docs.pola.rs/user-guide/concepts/ — 1 hr (expressions, lazy vs eager, contexts)
- https://docs.pola.rs/user-guide/transformations/joins/ — 30 min
- https://docs.pola.rs/user-guide/lazy/optimizations/ — 30 min

**Hands-on** (1-2 hrs):
- `pip install polars`
- Write 10K rows. Use lazy mode (`pl.scan_csv`). Apply a chain of filters/aggregates. Print the query plan with `.explain()`.
- Convert to/from Arrow. Convert to/from DuckDB relation.

**You know enough when**:
- You understand "lazy" vs "eager" and which we prefer.
- You can write a Polars query plan and predict its execution order.

---

## §M2. Tier 1 prep — Orchestration & error handling (~30-40 hrs)

Trigger: when Tier 0 Heartbeat ships and we start v0.1 design.

### M2.1 Dagster fundamentals (~10-15 hrs)

You'll wrap Dagster heavily. You need to understand it deeply.

**Read** (in order):
1. https://docs.dagster.io/concepts/assets/software-defined-assets — 2 hrs
2. https://docs.dagster.io/concepts/io-management/io-managers — 2 hrs
3. https://docs.dagster.io/concepts/repositories-workspaces/repositories — 1 hr
4. https://docs.dagster.io/concepts/execution/materializing-assets — 2 hrs
5. https://docs.dagster.io/api — skim (we'll come back here often)

**Concepts to internalize**:
- **Asset** vs Op — we use Assets exclusively
- **Asset key** — `AssetKey(["raw", "orders"])` maps to `raw.orders`
- **Materialization** — the act of computing and storing
- **IOManager** — how data flows between assets
- **DagsterInstance.ephemeral** — what we use locally
- **Code locations** vs Definitions — for v0.1, we use one code location

**Hands-on** (5-8 hrs):
- `pip install dagster`
- Write a 3-asset DAG: `raw_users` → `clean_users` → `user_counts`.
- Run it with `materialize_to_memory`.
- Add an asset that fails. Observe the exception that surfaces.
- **Crucial exercise**: copy-paste the failing-asset exception type. This is what our Error Translation Layer must catch.

**You know enough when**:
- You can answer: "What's the difference between an Op and an Asset?"
- You can list the 5 most common Dagster exception types we'll see.
- You can describe what `materialize_to_memory` does internally.

### M2.2 Error translation theory (~5 hrs)

Read [`docs/architecture/sequence_error_translation.md`](../architecture/sequence_error_translation.md) again with fresh eyes after M2.1. Now it'll make sense.

**Read also**:
- Python exception chaining: https://docs.python.org/3/tutorial/errors.html#exception-chaining
- `__cause__` vs `__context__`
- How to write `__str__` for a "user-helpful" error

**Hands-on** (2-3 hrs):
- Implement a minimal `ErrorTranslator` class (~50 lines).
- Register a translator for `KeyError` → `MyKeyMissingError("key X not found")`.
- Walk through a chained exception (`raise B() from A()`); your translator should see B but report on A.

### M2.3 Python type system deep-dive (~5-8 hrs)

Strict typing in a library is hard. You'll trip on this regularly until you've practiced.

**Read**:
- https://typing.readthedocs.io/en/latest/spec/ — sections "Type aliases", "Generic types", "Protocol", "Variance" (3-4 hrs total)
- https://mypy.readthedocs.io/en/stable/generics.html — 1 hr
- https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html — 30 min reference

**Hands-on** (2-3 hrs):
- Write a Generic class: `class Cache(Generic[K, V]): ...`.
- Use a `TypeVar` with bound and constraints.
- Define a `Protocol` with a class method and verify mypy enforces it structurally.

### M2.4 Property-based testing (~3-4 hrs)

We use `hypothesis` for type-mapping verification.

**Read**:
- https://hypothesis.readthedocs.io/en/latest/quickstart.html — 30 min
- https://hypothesis.readthedocs.io/en/latest/data.html — 1 hr (strategies)

**Hands-on** (2 hrs):
- Write a property test: "for any list of ints, sorting twice = sorting once".
- Write one for our type mapping: "for any Postgres `INTEGER`, round-trip via Arrow → Polars → Arrow is identity".

---

## §M3. Tier 2+ — When we get there

Defer learning until the work needs it. Sketches only.

### M3.1 FastAPI (for Workbench backend)
When Tier 2 ("Workbench") starts.

### M3.2 React + TypeScript (Workbench frontend)
You may pick a different stack here (HTMX, Marimo). Decide later.

### M3.3 Performance profiling (cProfile, py-spy, scalene)
When we hit a perf issue we can't reason about.

### M3.4 LLM integration (OpenAI / Anthropic / Ollama clients)
When Tier 2 Copilot starts. Likely month 8-14.

### M3.5 Distributed systems (DataFusion, Daft)
When Tier 4 Intelligence starts. Likely month 20+.

---

## §2. Common junior-DE pitfalls (forewarned)

These are the bugs that cost most data engineers a week each. You'll avoid them because you know about them now.

### §2.1 Timezone hell
`TIMESTAMP` (naive) vs `TIMESTAMPTZ` (UTC). They are **different types**. Mixing them = bugs that show up at midnight 6 months later.
→ Our rule in [`docs/patterns/type_mapping.md`](../patterns/type_mapping.md) §3.5: always UTC after extraction.

### §2.2 NULL ≠ empty string ≠ 0 ≠ false
Postgres, Iceberg, Polars, DuckDB all preserve NULL faithfully. **You** must not "fix" NULL with defaults silently.
→ Our rule: §7 of type_mapping.md.

### §2.3 Decimal → Float silently
A `NUMERIC(10,4)` cast to `f64` quietly loses precision. Currency math becomes wrong.
→ Always preserve decimal type end-to-end.

### §2.4 Schema drift
A column type changes upstream. Your pipeline doesn't notice. Wrong data flows for weeks.
→ Schema contracts (engineering.md §7.2, coordination/contracts.py) catch this.

### §2.5 Encoding issues
Postgres `TEXT` is UTF-8. CSV files may be Latin-1. Don't assume. Always specify.
→ Always `encoding="utf-8"` unless you have a reason. When reading CSV, set explicitly.

### §2.6 Eager loading of huge tables
`df = pd.read_sql("SELECT * FROM ten_million_rows")` will OOM your machine.
→ Stream. Use `chunksize=`. In Polars, use `scan_*` and `.collect(streaming=True)`.

### §2.7 Not checking file/connection close
Connections leak. File handles too. Use `with` blocks religiously.

### §2.8 Test on a sample, ship on full data
Your code works on 100 rows. It hangs on 100M rows. Always test with a realistic scale.

### §2.9 Catching `except Exception`
Swallows your bug. Hides real errors.
→ Our rule: never bare except. Always re-raise as NucleusError with cause.

### §2.10 Believing AI without verifying
Including me. Doubly so for library APIs. **Always verify against current docs (Constraint #10).** I will get version mismatches wrong sometimes.

---

## §3. Tracker — your progress

Keep this updated. It's *your* note to self.

| Module | Status | Hours | Notes |
|--------|--------|-------|-------|
| M0.1 Python features | ⬜ Not started | 0 | |
| M0.2 Project tooling | ⬜ Not started | 0 | |
| M0.3 Reading architecture | ⬜ Not started | 0 | |
| M0.4 Working with AI pair | ⬜ Not started | 0 | |
| M1.1 Apache Arrow | ⬜ | 0 | |
| M1.2 Apache Iceberg | ⬜ | 0 | |
| M1.3 DuckDB | ⬜ | 0 | |
| M1.4 Polars | ⬜ | 0 | |
| M2.1 Dagster | ⬜ | 0 | |
| M2.2 Error translation | ⬜ | 0 | |
| M2.3 Python typing | ⬜ | 0 | |
| M2.4 Property testing | ⬜ | 0 | |

Marks: ⬜ Not started · 🟨 In progress · ✅ Done · ⏭️ Skipped

---

## §4. Quick references (pin these tabs)

- Python: https://docs.python.org/3/
- mypy: https://mypy.readthedocs.io/en/stable/
- pytest: https://docs.pytest.org/en/stable/
- PyArrow: https://arrow.apache.org/docs/python/
- PyIceberg: https://py.iceberg.apache.org/
- DuckDB Python: https://duckdb.org/docs/api/python/overview
- Polars: https://docs.pola.rs/api/python/stable/
- Dagster: https://docs.dagster.io/

**Always reference the URL that matches our pinned version in [`docs/compatibility.md`](../compatibility.md).** Old docs lie about new APIs.

---

## §5. Closing principle

You don't have to be senior on Day 1. You have to be:

1. **Honest about gaps** — flag them; don't fake them.
2. **Curious about why** — ask "but why?" three times for every decision.
3. **Patient with breaks** — when stuck, sleep on it. Real understanding comes overnight.
4. **Disciplined about constraints** — the 11 constraints exist to protect us from ourselves; respect them.

This is enough.

---

*This doc is yours. Edit it as you learn. Mark modules done. Note pitfalls you hit. Add resources I missed. It is the only doc that exists for you specifically.*
