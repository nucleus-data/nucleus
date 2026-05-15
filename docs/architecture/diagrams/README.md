# Nucleus Architecture - Excalidraw Diagram Set

Visual companion to [`nucleus_architecture_v4.1.md`](../../../nucleus_architecture_v4.1.md).
Eight self-explanatory diagrams covering every layer of the stack plus the
two cross-cutting concerns (composability + yield-to-giants).

## Reading order

| Audience | Path |
|---|---|
| First-timer (15 min) | `01_overview` -> `07_dataflow_user_journey` |
| Architect deep-dive (~50 min) | `01_overview` -> `02_physics` -> `03_engines` -> `04_coordination` -> `05_intelligence` -> `06_experience` -> `08_composability_yield_to_giants` |
| Skeptic / "why this approach" | `03_engines` (wrap-not-build) -> `08_composability_yield_to_giants` (swap interfaces + graduation paths) |

## Diagram index

| # | File | One-liner | v4.1 sections |
|---|---|---|---|
| 01 | `01_overview.excalidraw` | Full stack at a glance: 5 horizontal layer bands, persona on top, yield-to-giants arrow on the right. | 3.1, 3.2 |
| 02 | `02_physics.excalidraw` | Tier 0 substrate: Iceberg metadata stack (catalog -> metadata.json -> manifest list -> manifest -> data files), Parquet, S3/MinIO/SeaweedFS object stores, Lance v0.5+, snapshot lineage. | 4, ADR-008 |
| 03 | `03_engines.excalidraw` | Wrapped engines (DuckDB / Polars / pyiceberg / dlt / LiteLLM) with their swap targets; Apache Arrow as zero-copy IPC bridge; "no JVM" badge. | 5, Hard Constraint #1 |
| 04 | `04_coordination.excalidraw` | The crown jewel - AMA owns the data path, Dagster hidden behind dotted line, Error Translation Layer turns 5 representative wrapped exceptions into typed NucleusError outputs (NE-codes); side concerns (locks, daemon, expire_snapshots, run ledger). | 6.2, 6.4, 6.5, ADR-024 |
| 05 | `05_intelligence.excalidraw` | AI Copilot v0.2: project context inputs, 5-redaction privacy gate, LiteLLM router fanning out to Anthropic/OpenAI/Azure/Ollama, token budget, error explanation pipeline. | 7, ADR-015, ADR-011 |
| 06 | `06_experience.excalidraw` | 3 equal user-facing surfaces (CLI / Workbench / ctx SDK) all delegating to one Coordination layer; uniform NE-coded error rendering. | 8, nucleus_cli_spec.md, ADR-016 |
| 07 | `07_dataflow_user_journey.excalidraw` | The 30-minute beachhead step-by-step (8 steps left-to-right, then row 2), error branch, behind-the-scenes call-out. | 1.5, 11 |
| 08 | `08_composability_yield_to_giants.excalidraw` | Top: Tier 0 / 1 / 2 stack with swap-on-demand semantics. Bottom: 3 modes of giant integration (Iceberg portability / hybrid compute / federation). | 9, 10, ADR-002 |

## Color legend

| Swatch | Hex | Meaning |
|---|---|---|
| light blue | `#a5d8ff` | Wrapped OSS - DuckDB, Polars, Dagster, dlt, pyiceberg, LiteLLM, Lakekeeper |
| light red | `#ffc9c9` | Built by Nucleus - ctx SDK, AMA, Error Translation, CLI, Workbench, AI Copilot |
| light green | `#b2f2bb` | Storage substrate - S3 / MinIO / SeaweedFS / Iceberg files |
| light yellow | `#ffec99` | User-facing surface - persona, CLI prompt, Workbench browser |
| light purple | `#d0bfff` | Tier 0 immortal - Arrow, Iceberg, Parquet, Lance, OpenLineage, OpenTelemetry |
| neutral grey | `#dee2e6` | Deferred / faded - features earmarked for v0.5+ or alternates |

## How to view / edit

* **Excalidraw web** - drag any `.excalidraw` file onto [`https://excalidraw.com`](https://excalidraw.com).
* **VS Code** - install the [Excalidraw extension](https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor) and open the file in-place.
* **Obsidian** - install the [Excalidraw plugin](https://github.com/zsviczian/obsidian-excalidraw-plugin) and drop the file in the vault.

## Reproducing the set

The diagrams are emitted from a single deterministic generator
(`_generate.py`) so colors, ids, and seeds stay stable across re-runs and
`git diff` remains meaningful. To regenerate after editing the script:

```bash
python docs/architecture/diagrams/_generate.py
```

Then commit the regenerated `.excalidraw` files. Direct editing of the JSON
is also supported - the generator is one of two co-equal authoring paths.

## Vocabulary discipline

These diagrams use Nucleus vocabulary (`asset`, `materialization`, `snapshot`,
`contract`, `check`, `catalog`) and avoid the forbidden vocabulary listed in
`AGENTS.md` Section 7. The `scripts/check_vocabulary.py` guard scans this
directory; only the diagram-text counter-frames retired ADR-002 marketing
angles, and those uses carry inline `banned-term` exemption markers in the
generator source.
