# Research: Lance + LanceDB

> **Pinned**: **NOT YET** — v0.5+ scope (Mo 20-28 per v4.1 §18.4). Latests: `pylance==6.0.0`, `lancedb==0.30.2`. **Verified**: 2026-05-13.
> **Docs**: https://lance.org/ (format) • https://docs.lancedb.com/ (DB) — **Repos**: https://github.com/lance-format/lance • https://github.com/lancedb/lancedb
> **Used in**: **NOT YET — deferred to v0.5+.** Planned: `src/nucleus/physics/` (Lance writer) + `src/nucleus/intelligence/` (LanceDB for Copilot retrieval).

Research anchor per AGENTS.md Hard Constraint #10. Read before v0.5 scoping touching multimodal assets, vectors, embeddings, RAG, or the AI Copilot. **Do not write Lance/LanceDB code from memory.**

---

## §1. At a glance

- **Two distinct OSS projects**, same brand, both **Apache 2.0**:
  - **Lance** — open lakehouse *format* (file + table + catalog spec). Repo `lance-format/lance` (moved from `lancedb` org in 2025-2026). PyPI `pylance`. Import `import lance`. ≈ "Parquet+Iceberg reimagined for multimodal AI — 100× random access, native vectors/images/video, data-evolution-with-backfill".
  - **LanceDB** — embedded multimodal retrieval library *built on* Lance. Repo `lancedb/lancedb`. PyPI `lancedb`. Import `import lancedb`. ≈ "SQLite-for-vectors on Lance — embedded hybrid vector / FTS / SQL retrieval".
- Rust core + Python bindings. **No JVM** — satisfies Constraint #1.
- Lance is **Tier 0 (immortal)** per v4.1 §3/§4 (alongside Arrow / Iceberg / Parquet / S3 API). LanceDB-the-library is **Tier 1** — swappable to Qdrant / Weaviate / pgvector / Chroma (§7).
- **Name collision**: *Pylance* (Microsoft VS Code Python language server) ≠ *pylance* (PyPI, Lance SDK). Disambiguate in code review.

---

## §2. Version verification (2026-05-13)

Sources: `pypi.org/pypi/{pylance,lancedb}/json`, GitHub release pages.

| Fact | `pylance` | `lancedb` |
|---|---|---|
| Latest on PyPI | **6.0.0** (2026-05-11) | **0.30.2** (2026-03-31) |
| Yanked? | ✗ No | ✗ No |
| Python (classifiers / `requires_python`) | 3.9-3.14 / `>=3.9` | 3.10-3.13 / `>=3.10` |
| PyArrow floor | `>=14` | `>=16` |
| Our `pyarrow==18.1.0` inside? | ✓ | ✓ |
| License | Apache-2.0 (classifier) | Apache-2.0 (classifier) |
| Release cadence | Rapid; breaking changes labeled `!` | **~2 weeks** stable + preview channel |
| Internal dep | `lance-namespace<0.8,>=0.7.2` | `lance-namespace>=0.3.2` |

Wheels (cp39-abi3): macOS arm64/x86_64, manylinux x86_64/aarch64, Windows — universal across our beachhead platforms.

**Implications**: pylance majors are noisy (`2.0.0rc*` → `3.0.0` → `4.0.0` → `6.0.0` in weeks); every upgrade is a major-version move; ADR required (Constraint #11). lancedb 0.x is pre-1.0; 2-week cadence reinforces churn. Combined Python floor is `lancedb>=3.10`; combined PyArrow floor is `>=16`; our 3.11 + 18.1.0 pins are safe today. When v0.5+ pins these, exact pins only: `pylance==X.Y.Z` / `lancedb==X.Y.Z`.

---

## §3. Why Nucleus uses Lance and LanceDB

- **Layer**: Lance at L0 (Physics) alongside Iceberg/Parquet — *another* table format we wrap, not a replacement. LanceDB at L3 (Intelligence) for Copilot retrieval.
- **Cited mandates** (v4.1): §3 / §4 row 4 (Tier 0 + LF-aligned claim flagged in §9); §5.4 (*"Vector Storage: Lance / LanceDB (v0.5+)"*); §18.4 (*"Lance + multimodal optional"*); §20.1 (*"❌ A vector database (use Lance)"*); §1.2 row 9 (*"AI/ML and BI separate → Iceberg + Lance unified"*); AGENTS.md §4 (*"Custom vector storage → use Lance / LanceDB"*).
- **Default = WRAP**, never build. We never author vector storage or indices. **Why these, not other vector DBs**: alignment with Tier 0 substrate (Arrow + open spec + open governance), single-binary embedded library (same DX as DuckDB/Polars), unified table format that *also* indexes vectors (no separate silo). **Out of scope** for v0.1–v0.3 — gated on v0.5 (Mo 20-28 per v4.1 §17.2).

---

## §4. Core concepts — Lance ≠ LanceDB (memorize)

Two technologies, one brand. Conflating them is the single biggest hallucination risk here.

### §4.1 Lance as multimodal table format (alongside Iceberg-backed tabular)

Lance is a complete lakehouse format with three layers — file format, table format, catalog spec — analogous to Parquet + Iceberg + REST catalog, unified.

Primitives (https://lance.org/format/table) — analogs to Iceberg in parens: **Dataset** (Table), **Manifest** (`vN.metadata.json`), **Fragment** (partition; `uint32` id; one+ data files + optional deletion file), **Data file** (Lance v2/v2.1 file format, NOT Parquet), **Deletion file** (Arrow IPC for sparse / Roaring Bitmap for dense; position-based), **Version** (Snapshot; monotonic; MVCC; ACID), **Field IDs** (immutable integer IDs; tombstone `-2` for evolution). **Indices** (Iceberg has none): scalar `BTREE / BITMAP / LABEL_LIST / INVERTED (FTS) / NGRAM / ZONEMAP / BLOOMFILTER / RTREE` + vector `IVF_FLAT / IVF_PQ / IVF_HNSW`.

**Lance has, Iceberg lacks**: (1) **data evolution with backfill** — adding a derived column = writing one new data file per fragment (no rewrite; Iceberg requires copy-on-write); (2) **native multimodal columns** — blob encoding for images/video/audio + zero-copy fixed-size-list vectors. **Iceberg has, Lance lacks** (NEEDS VERIFICATION on each upgrade): equality deletes (Lance is position-deletes only); multi-engine *write* maturity (Spark / Trino / Flink all write Iceberg in prod; Lance writers are newer).

### §4.2 LanceDB for v0.5+ vector retrieval (RAG, semantic search)

LanceDB is an **embedded** retrieval library — same DX shape as DuckDB / SQLite. Same process, no server. Each table is a Lance dataset. Ops: create, add rows, vector search, BM25, hybrid (vector + FTS + SQL), schema evolution, time travel. Vector indexes: IVF_PQ (default), IVF_HNSW, IVF_FLAT. Scalar indexes: same set Lance ships (LanceDB is a thin layer). Deployment: **LanceDB OSS** (embedded, Apache 2.0) — the only mode we use; LanceDB Enterprise (managed) is out of scope. Cadence: ~2-week stable + preview.

### §4.3 Coexistence with Iceberg (when to pick Lance vs Iceberg)

**Complementary, not interchangeable**: a Lance dataset cannot be read by PyIceberg; an Iceberg table cannot be opened by `lance.dataset(...)`. Unification happens at L2 in the Asset Materialization Adapter, which dispatches by `@nucleus.asset(format=...)`. Both formats can co-locate in one catalog — Apache Polaris (our v0.3+ co-default per v4.1 §5.7) supports both natively (Polaris blog, Jan 2026 — §11).

| Question | Iceberg | Lance |
|---|---|---|
| Primary consumer? | BI / SQL / dashboards | ML training / RAG / agent retrieval |
| Schema? | Tabular | Tabular **plus** vectors, blobs, multimodal |
| Random-row access? | Slower (Parquet) | **~100× Parquet** (Lance headline, https://lance.org/) |
| Add a derived column? | Heavy (rewrite) | Cheap (data evolution) |
| Graduation? | Databricks / Snowflake / Trino read native | Polaris reads native; broader engines younger |
| Default in v0.5+? | **Yes** | Opt-in via `@nucleus.asset(format="lance")` |

### §4.4 v0.5+ AI Copilot uses LanceDB for semantic queries

Per v4.1 §7.4 (v0.7+ Semantic Knowledge Graph) and §18.4, the Copilot's context layer needs hybrid retrieval (embedding similarity + structural filters). LanceDB indexes the user's project metadata (asset code, schemas, contracts, lineage, run history, glossary) at `<project>/.nucleus/copilot/` (path **NEEDS VERIFICATION** — locks in v0.5 design ADR). Hybrid queries combine vector similarity + FTS + SQL predicates in **one** plan (no separate join). "Semantic knowledge graph" (§7.4) layers a graph index on top; first iteration is plain embedded LanceDB.

**Guardrail**: Copilot's vector store holds ONLY project metadata, never production data. User PII never enters embeddings without explicit `@nucleus.contract(pii=True)` opt-in. **Why not Iceberg-only**: Iceberg has no vector indices; Copilot needs sub-second ANN.

---

## §5. Critical API surface

Cite docs URL alongside each call in source code (Constraint #10).

### §5.1 Lance (`pylance==6.0.0` docs)

```python
import lance
# Docs: https://lance.org/quickstart/ • API: https://lance-format.github.io/lance-python-doc/all-modules.html

# Write — accepts pa.Table, pd.DataFrame, pa.dataset.Dataset, Iterator[pa.RecordBatch]
ds = lance.write_dataset(data, "./my.lance", mode="create")  # "create"|"append"|"overwrite"

# Open / scan / stream
ds = lance.dataset("./my.lance")
ds.scanner(filter="status='paid'", columns=["id","amount"]).to_table()
ds.scanner().to_batches()                        # streaming (preferred >100 MB)

# Indices (scalar + vector) + vector search + time-travel
ds.create_scalar_index("status", index_type="BTREE")
ds.create_scalar_index("body",   index_type="FTS")
ds.create_index(column="embedding", index_type="IVF_PQ",
                num_partitions=256, num_sub_vectors=96)
ds.scanner(nearest=dict(column="embedding", q=query_vec, k=10),
           filter="lang='en'").to_table()
ds.versions(); ds.checkout_version(42)
```

NEEDS VERIFICATION on first integration: exact signatures of `write_dataset`, `create_index`, `scanner`, and the `nearest` kwarg shape — pylance churned across 3.0/4.0/6.0. Pin a real version, then re-verify against *that* version's docs.

### §5.2 LanceDB (`lancedb==0.30.2` docs)

```python
import lancedb  # Docs: https://docs.lancedb.com/

db = lancedb.connect("./my_lancedb")
table = db.create_table("documents",
    data=[{"text": "...", "embedding": [0.1]*768, "lang": "en"}], mode="create")

# Hybrid: vector + filter
table.search(query_vec, vector_column_name="embedding") \
     .where("lang='en'").limit(10).to_pyarrow()

# Full-text (BM25)
table.create_fts_index("text")
table.search("invoice 2024", query_type="fts").limit(20).to_pyarrow()
```

Vocabulary (AGENTS.md §7): wrap at L2 as **assets / contracts / materializations** — not "tables", "indices", "searches".

---

## §6. Exception types we'll translate

Per v4.1 §6.4, every Lance / LanceDB exception translates to a `NucleusError` at L2 before reaching `ctx`. `pylance==6.0.0` docs surface mostly **stdlib exceptions** (`ValueError`, `IOError`, `RuntimeError`); a dedicated `lance.exceptions` module is NOT confirmed. **All rows below are NEEDS VERIFICATION** until v0.5 PoC.

| Likely surface | When | NucleusError target |
|---|---|---|
| `ValueError` on append / merge-insert | Schema mismatch; missing PK with unset `on=` | `NucleusSchemaError` |
| `IOError` from object-store path | S3/MinIO failure, perms | `NucleusStorageError` / `NucleusAuthError` |
| `RuntimeError` on concurrent commit | Two writers race on the same version | `NucleusCommitConflictError` (retry candidate) |
| `LookupError` / `KeyError` | Missing column / dataset | `NucleusAssetNotFoundError` |
| `lance.exceptions.*` (if/when exposed) | TBD | TBD |

> **AI-drift caveat**: confirm import paths, constructors, and `__cause__` chaining by **actually triggering each exception** against pinned versions. Do NOT register translators from class names alone. Log fabrications in `docs/internal/research/ai_hallucinations.md`.

---

## §7. Swap analysis — Tier 0 caveat + separation of concerns

Per AGENTS.md Constraint #9 and v4.1 §9, every Tier 1/2 dep needs swap interface + smoke tests. Lance and LanceDB sit on **different tiers**:

| Component | Tier | Swap target |
|---|---|---|
| **Lance — the format** | **Tier 0 (immortal)** | **None** — open spec, durable substrate (same as Iceberg / Parquet / Arrow / S3 API) |
| **LanceDB — embedded retrieval library** | **Tier 1** | **Qdrant / Weaviate / pgvector / Chroma** — interface + smoke tests per v4.1 §9.3; full adapter on-demand |

`pylance` is the only Python writer the Rust core supports today; the swap interface lives below pylance at the *format* level.

**Why this split matters**: Tier 0 on the *format* makes user vectors/multimodal data durable on object storage regardless of library (same property as Iceberg). Tier 1 on the *embedded library* means a hostile LanceDB Inc. (license pivot, vendor death, perf >2× regression) lets us swap to pgvector or Qdrant **without losing the Lance datasets on disk** — they're an open format. Same "yield to giants" property as Iceberg, applied to multimodal data.

**Swap interface** (v0.5+): `src/nucleus/intelligence/vector_store.py` (Protocol) + `_lancedb_adapter.py` (default) + `tests/smoke/test_vector_store_swap.py` (5-10 smoke tests). Triggers: vendor death, license pivot, perf >2× regression, community demand. Until one fires, no full second adapter is built ("Composability Tax").

---

## §8. Interaction with other Nucleus components

| Boundary | Mechanism | Tier |
|---|---|---|
| ↔ PyArrow (L0) | `lance.write_dataset(arrow_table)` / `ds.to_table()` — zero-copy via Arrow C Data Interface | 0 |
| ↔ Polars (L1) | `pl.from_arrow(ds.to_table())` zero-copy. `pl.scan_lance` — NEEDS VERIFICATION vs `polars==1.18.0` | 1 |
| ↔ DuckDB (L1) | `INSTALL lance; LOAD lance;` — NEEDS VERIFICATION vs `duckdb==1.1.3` | 1 |
| ↔ Iceberg (L0) | **NO direct path.** Coexist via AMA at L2 (§4.3). | N/A |
| ↔ Catalog (L0) | v0.5+: Apache Polaris reads both natively. Filesystem via `lance-namespace` — NEEDS VERIFICATION. | 0 |
| ↔ AMA (L2) | Wraps `lance.write_dataset(...)` + OpenLineage + asset registry. Same shape as PyIceberg path. | 2 |
| ↔ Error Translation (L2) | §6 translators. `scripts/dagster_leak_check.py` extends to `lance.` / `lancedb.` prefixes in v0.5. | 2 |
| ↔ AI Copilot (L3, v0.5+) | Embedded LanceDB at `<project>/.nucleus/copilot/` drives Copilot retrieval (§4.4). | 3 |
| ↔ `ctx` SDK (L4) | `@nucleus.asset(format="lance", ...)` opt-in. Default stays Iceberg. NEEDS VERIFICATION — locks in v0.5 SDK spec. | 4 |
| ↔ MCP server (L4, v0.5+) | `nucleus-mcp-server` (v4.1 §18.4 P4) — vector-indexed lookups hit LanceDB through the same retrieval layer. | 4 |

Arrow is the universal pivot — Lance ↔ Polars/DuckDB/Iceberg never go through pandas (`docs/conventions/engineering.md` §11.4).

---

## §9. Why Lance is Tier 0

Per v4.1 §9.2, Tier 0 requires: open spec, multi-vendor commitment, governance independence, license stability, immortal-grade adoption. Lance qualifies on all but #7:

1. **Open spec** ✓ — file/table/catalog spec at https://lance.org/format/ with protobuf schemas. VLDB 2025 paper: https://arxiv.org/abs/2504.15247.
2. **Multi-vendor read support** ✓ — Apache Polaris (ASF TLP, Feb 2026) reads natively; integrations with DuckDB, Polars, DataFusion, Spark, Trino, PyTorch, Pandas, Ray.
3. **Apache 2.0** ✓ — both libs carry `License :: OSI Approved :: Apache Software License` (PyPI, 2026-05-13). No BSL/SSPL flirt.
4. **Governance independence** ✓ — three-tier PMC / Maintainers / Contributors, ASF-inspired (https://lancedb.com/blog/lance-community-governance/). Repo moved `lancedb/lance` → `lance-format/lance` in 2025-2026, separating the *format* from LanceDB Inc.'s commercial brand.
5. **Multimodal-native by design** ✓ — no other open lakehouse format treats vectors / images / video / audio as first-class. Structurally hard to retrofit.
6. **Zero-copy Arrow interop** ✓ — same memory model as Polars / DuckDB / PyIceberg / Daft. Critical for the all-Arrow data plane.
7. **Linux Foundation alignment** — **NEEDS VERIFICATION.** v4.1 §4 row 4 claims *"Open spec, Linux Foundation aligned"*; as of 2026-05-13 no public LF announcement enumerates Lance (the LF Agentic AI Foundation Dec 2025 lists MCP / goose / AGENTS.md only). Treat as aspirational; **Tier 0 case stands on 1-6 alone.**

---

## §10. Upgrade considerations

When v0.5 first pins these (per Constraint #11): one-component-per-PR; changelog summary; smoke test on Win + macOS + Linux; rollback command; major version → ADR + benchmark + canary. Add `pylance` / `lancedb` / `lance-namespace` rows to `docs/compatibility.md`. **Watch**: file format version evolves separately from library version (v1 → v2.0 → v2.1 → 5.0); on every pylance upgrade, check whether the *file format* default bumped.

**Top 5 risks**:

| # | Risk | Mitigation |
|---|---|---|
| 1 | pylance / lancedb API churn (rapid majors, 2-wk cadence) | Quarterly audit; never chase head; one-component-per-PR |
| 2 | Lance file format drift (v2 → v2.1 → 5.0) | Pin format version per dataset; smoke test old-format read after upgrade |
| 3 | LanceDB Inc. commercial pivot (Enterprise tier → BSL/SSPL risk) | Tier 1 swap to Qdrant / pgvector ready in v0.5 |
| 4 | LF-alignment claim in v4.1 §4 unverified | §9 flagged; downgrade phrasing on next architecture amendment |
| 5 | Cross-library skew (`pylance` / `lancedb` / `lance-namespace`) | Pin all three together; CI smoke test; verify `lance-namespace` floor each upgrade |

---

## §11. Useful links

- **Lance (format)** — Home: https://lance.org/ • Spec: https://lance.org/format/ • Quickstart: https://lance.org/quickstart/ • Migration: https://lance.org/guide/migration/ • GitHub: https://github.com/lance-format/lance • PyPI: https://pypi.org/project/pylance/ • Python API: https://lance-format.github.io/lance-python-doc/all-modules.html • VLDB 2025: https://arxiv.org/abs/2504.15247 • Governance: https://lancedb.com/blog/lance-community-governance/
- **LanceDB (library)** — Docs: https://docs.lancedb.com/ • SDK: https://lancedb.github.io/lancedb/ • GitHub: https://github.com/lancedb/lancedb • PyPI: https://pypi.org/project/lancedb/ • Multimodal lakehouse: https://lancedb.com/blog/multimodal-lakehouse/ • Lance + Iceberg: https://lancedb.com/blog/from-bi-to-ai-lance-and-iceberg/
- **Ecosystem** — Polaris × Lance: https://polaris.apache.org/blog/2026/01/06/apache-polaris-and-lance-bringing-ai-native-storage-to-the-open-multimodal-lakehouse/ <!-- banned-term: AI-native --> • DuckDB Lance extension + Polars `scan_lance`: NEEDS VERIFICATION vs pinned `duckdb==1.1.3` / `polars==1.18.0`

---

*Next review trigger: v0.5 scoping, or the first PR that adds `pylance` / `lancedb` to `pyproject.toml`. Log hallucinated Lance / LanceDB APIs in `docs/internal/research/ai_hallucinations.md`.*
