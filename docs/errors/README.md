# Nucleus Error Reference (v0.1 initial 12)

Every `NucleusError` instance carries a `docs_url` pointing into this directory. The pages here explain what each error means, what likely caused it, and concrete fix steps. One page per `error_code`.

**Scheme**: `NE[L][CCC]` — `NE` = Nucleus Error, `L` ∈ `1..5` = layer prefix, `CCC` = monotonic category. Codes are PERMANENT from first release (no renumbering, no reuse).

Layer prefix map ([ADR-006 §Decision](../decisions/ADR-006-nucleus-error-code-numbering.md)):

- `NE1xxx` — L0 Physics (Iceberg, Parquet, Arrow, S3, network IO)
- `NE2xxx` — L1 Engines (compute, parse/bind/plan, in-engine resource limits)
- `NE3xxx` — L2 Coordination (asset graph, contracts, lineage, translator itself)
- `NE4xxx` — L3 Intelligence (reserved, v0.5+)
- `NE5xxx` — L4 Experience (reserved, v0.5+)

## Initial 12 codes (v0.1)

| Code | Class | Layer | Page |
|---|---|---|---|
| `NE1001` | `NucleusSourceConnectionError` | L0 Physics | [source-connection.md](source-connection.md) — could not reach an external source |
| `NE1002` | `NucleusCommitConflictError` | L0 Physics | [commit-conflict.md](commit-conflict.md) — concurrent write conflicted with yours |
| `NE1003` | `NucleusCommitUnknownError` | L0 Physics | [commit-unknown.md](commit-unknown.md) — commit landed-or-not is unknown |
| `NE1004` | `NucleusSchemaEvolutionError` | L0 Physics | [schema-evolution.md](schema-evolution.md) — schema change violates Iceberg evolution rules |
| `NE1005` | `NucleusIOError` | L0 Physics | [io.md](io.md) — filesystem or object-store read/write failed |
| `NE1006` | `NucleusPermissionError` | L0 Physics | [permission.md](permission.md) — OS or storage permission denied |
| `NE2001` | `NucleusSchemaError` | L1 Engines | [schema.md](schema.md) — data did not match the declared schema |
| `NE2002` | `NucleusSQLSyntaxError` | L1 Engines | [sql-syntax.md](sql-syntax.md) — SQL string failed to parse |
| `NE2003` | `NucleusResourceError` | L1 Engines | [resource.md](resource.md) — exceeded engine resource limit (typically memory) |
| `NE3001` | `NucleusInternalError` | L2 Coordination | [internal.md](internal.md) — translator catch-all; usually means file a bug |
| `NE3002` | `NucleusAssetNotFound` | L2 Coordination | [asset-not-found.md](asset-not-found.md) — asset name not registered in the project |
| `NE3003` | `NucleusAssetNotMaterialized` | L2 Coordination | [not-materialized.md](not-materialized.md) — asset is defined but never computed |

## Reserved ranges

- `NEx900`–`NEx999` (every layer) — internal codes, never user-facing. Surfacing one in a CLI message is a release blocker.
- `NE0xxx` — never allocated. Keeps "uninitialized / null" semantics safe in tooling.

## Adding a new code

Per `docs/specs/nucleus_architecture_v4.1.md` §6.4 and [ADR-006 §Decision](../decisions/ADR-006-nucleus-error-code-numbering.md):

1. Subclass `NucleusError` in `src/nucleus/errors.py`.
2. Assign a unique `error_code: ClassVar[str]` from the correct layer band (next monotonic value, no reservations, no gaps for "round numbers").
3. Override `DEFAULT_DOCS_URL` to the new slug.
4. Add a stub page here matching that slug.
5. CI gate: `scripts/check_error_codes.py` (lands with PoC #1 promotion) enforces uniqueness and format.

## Auto-generation status

These initial 12 are hand-written at v0.1. Per [ADR-006 §Verification plan #2](../decisions/ADR-006-nucleus-error-code-numbering.md), `scripts/generate_error_docs.py` replaces these stubs in v0.2 once the Workbench docs surface lands. Until then, edit by hand.

## Related

- Source: [`src/nucleus/errors.py`](../../src/nucleus/errors.py)
- Translator: [`src/nucleus/coordination/error_translation.py`](../../src/nucleus/coordination/error_translation.py)
- Architecture: [v4.1 §6.4 Error Translation Layer](../specs/nucleus_architecture_v4.1.md)
- ADR: [ADR-006 NucleusError Error Code Numbering Scheme](../decisions/ADR-006-nucleus-error-code-numbering.md)
