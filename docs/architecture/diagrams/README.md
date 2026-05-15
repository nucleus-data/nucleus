# Nucleus Architecture - Excalidraw Diagram Set

Visual companion to [`nucleus_architecture_v4.1.md`](../../../nucleus_architecture_v4.1.md).
Eight diagrams covering every layer of the stack plus the two cross-cutting
concerns (composability + yield-to-giants). **Each diagram uses the visual
paradigm best suited to its content; we deliberately avoid a one-size-fits-all
template.**

## Per-diagram paradigm

| # | File | Paradigm | Why this paradigm |
|---|---|---|---|
| 01 | `01_overview.excalidraw` | **Layered horizontal bands** | The overview is literally a 5-layer stack; bands are the right shape. Adjacent-band arrows route in a dedicated left-side gap lane to avoid passing through any band's content. |
| 02 | `02_physics.excalidraw` | **Tree (top-down chain) + snapshot timeline** | Iceberg metadata is a nested reference chain (catalog -> metadata.json -> manifest list -> manifest -> data file); snapshot evolution is a separate horizontal axis on the right. |
| 03 | `03_engines.excalidraw` | **Parallel channels + Apache Arrow bridge band** | The 5 wrapped engines are PEERS bridged by Arrow zero-copy IPC; vertical columns equalize them; a horizontal bridge band shows the cross-engine connector. NO JVM and WRAP NOT BUILD live as corner badges. |
| 04 | `04_coordination.excalidraw` | **Two-track horizontal flow** | Every materialization has a success path (top track ending in an Iceberg snapshot) and an error path (bottom track ending in a typed NucleusError). Cross-track dashed elbow arrows show exception capture; AMA + Error Translator are the visual centres of each track. |
| 05 | `05_intelligence.excalidraw` | **Horizontal pipeline + context-injection legs** | The Copilot is a pipeline (user message -> router -> context injector -> LiteLLM -> response). Context inputs come up from below into the injector; provider fanout drops down from LiteLLM. Privacy + token-budget guards sit above the spine. |
| 06 | `06_experience.excalidraw` | **Hub-and-spoke** | 3 co-equal surfaces (CLI, Workbench, ctx SDK) all delegate to ONE Coordination hub. Bidirectional arrows between hub and each spoke; the error-display affordance hangs off the hub as a side panel consumed by all 3 surfaces. |
| 07 | `07_dataflow_user_journey.excalidraw` | **Horizontal timeline** | Time is the primary axis. Tick marks at 0/5/10/15/20/25/30 minutes; 7 milestones placed at their actual minute (non-uniform spacing); each milestone has a mock terminal-output snippet beneath. Error branch is a dashed offshoot from `nucleus run`; graduation is a stretch milestone hanging off the right edge. |
| 08 | `08_composability_yield_to_giants.excalidraw` | **Tier-stack (top half) + 3-mode panel (bottom half)** | Two paired ideas in one frame. Top: vertical tier stack with horizontal swap-interface arrows extending right of Tier 1. Bottom: three stacked mode panels (Iceberg portability, hybrid compute, federation) all fed by the Nucleus Iceberg lake. |

## Reading order

| Audience | Path |
|---|---|
| First-timer (15 min) | `01_overview` -> `07_dataflow_user_journey` |
| Architect deep-dive (~50 min) | `01_overview` -> `02_physics` -> `03_engines` -> `04_coordination` -> `05_intelligence` -> `06_experience` -> `08_composability_yield_to_giants` |
| Skeptic / "why this approach" | `03_engines` (wrap-not-build) -> `08_composability_yield_to_giants` (swap interfaces + graduation paths) |

## Color legend

| Swatch | Hex | Meaning |
|---|---|---|
| light blue | `#a5d8ff` | Wrapped OSS - DuckDB, Polars, Dagster, dlt, pyiceberg, LiteLLM, Lakekeeper |
| light red | `#ffc9c9` | Built by Nucleus - ctx SDK, AMA, Error Translation, CLI, Workbench, AI Copilot |
| light green | `#b2f2bb` | Storage substrate - S3 / MinIO / SeaweedFS / Iceberg files |
| light yellow | `#ffec99` | User-facing surface - persona, CLI prompt, Workbench browser |
| light purple | `#d0bfff` | Tier 0 immortal - Arrow, Iceberg, Parquet, Lance, OpenLineage, OpenTelemetry |
| neutral grey | `#dee2e6` | Deferred / faded - features earmarked for v0.5+ or alternates |

## Arrow discipline

The generator self-checks every arrow against every rectangle and refuses to
write a diagram if any arrow segment passes through a non-endpoint node. The
check is implemented in `_generate.py` as `assert_no_arrow_overlap()` using
Liang-Barsky line clipping with a 4 px margin. When a routing requires going
around a node, callers use the `elbow_arrow(via=[(x1,y1), (x2,y2), ...])`
primitive to specify explicit waypoints. Background "grouping" bands (large
rounded rectangles with low opacity) are exempt because they are by design
underlays.

## How to view / edit

* **Excalidraw web** - drag any `.excalidraw` file onto [`https://excalidraw.com`](https://excalidraw.com).
* **VS Code** - install the [Excalidraw extension](https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor) and open the file in-place.
* **Obsidian** - install the [Excalidraw plugin](https://github.com/zsviczian/obsidian-excalidraw-plugin) and drop the file in the vault.

## Reproducing the set

```bash
python docs/architecture/diagrams/_generate.py
```

The generator is deterministic (frozen timestamp + counter-driven seeds), so
re-running on an unchanged source produces a byte-identical output and `git
diff` stays meaningful.

## Vocabulary discipline

These diagrams use Nucleus vocabulary (`asset`, `materialization`, `snapshot`,
`contract`, `check`, `catalog`) and avoid the forbidden vocabulary listed in
`AGENTS.md` Section 7. The `scripts/check_vocabulary.py` guard scans this
directory; only the diagram-text counter-frames retired ADR-002 marketing
angles, and those uses carry inline `banned-term` exemption markers in the
generator source.
