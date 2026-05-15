"""Deterministic generator for the Nucleus architecture diagram set.

Produces 8 ``.excalidraw`` JSON files plus this directory's ``README.md`` from
a single Python source so that:

* colors stay consistent across the set (palette pinned in ``PALETTE``)
* every element carries the full property bag Excalidraw expects
* arrow / rectangle ``boundElements`` cross-references stay in sync
* IDs / seeds are deterministic (counter-driven), so re-running yields the
  same byte sequence and ``git diff`` stays meaningful

Run from the repo root::

    python docs/architecture/diagrams/_generate.py

Each diagram is a self-contained scene authored in one ``mk_*`` function;
they share only the helper toolbox at the top of this file. Diagram authoring
should stick to ASCII characters in element text per the brief (the
``check_vocabulary.py`` guard scans these files).

Excalidraw JSON shape reference:
    https://github.com/excalidraw/excalidraw/blob/master/dev-docs/docs/codebase/json-schema.mdx
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Palette + constants
# ---------------------------------------------------------------------------

PALETTE: dict[str, str] = {
    "stroke": "#1e1e1e",
    "wrapped": "#a5d8ff",   # light blue: DuckDB / Polars / Dagster / dlt / pyiceberg / LiteLLM
    "built": "#ffc9c9",     # light red: ctx SDK / AMA / Error Translation / CLI / Workbench / Copilot
    "storage": "#b2f2bb",   # light green: Iceberg / Parquet / S3 / MinIO / SeaweedFS
    "user": "#ffec99",      # light yellow: User personas / surfaces seen by humans
    "immortal": "#d0bfff",  # light purple: Tier 0 substrate (Arrow / Iceberg / Parquet / Lance)
    "muted": "#dee2e6",     # neutral grey for deferred / faded items
    "transparent": "transparent",
    "bg": "#ffffff",
}

FONT_BODY = 5      # Excalidraw "Hand-drawn" replaced by sans in v0.18+; matches existing repo file
SIZE_TITLE = 28
SIZE_SUBTITLE = 16
SIZE_LABEL = 16
SIZE_SMALL = 12
SIZE_BADGE = 14

UPDATED_TS = 1747400000000  # frozen timestamp keeps git diffs stable


class IdGen:
    """Deterministic id + seed counter, scoped per diagram."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._n = 0

    def next_seed(self) -> int:
        self._n += 1
        return 100000 + self._n * 11

    def make(self, slug: str) -> str:
        return f"{self._prefix}_{slug}"


# ---------------------------------------------------------------------------
# Element builders
# ---------------------------------------------------------------------------


def _base_props(idg: IdGen, eid: str) -> dict[str, Any]:
    seed = idg.next_seed()
    return {
        "id": eid,
        "angle": 0,
        "strokeColor": PALETTE["stroke"],
        "backgroundColor": PALETTE["transparent"],
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 0,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": seed,
        "version": 1,
        "versionNonce": seed + 1,
        "isDeleted": False,
        "boundElements": [],
        "updated": UPDATED_TS,
        "link": None,
        "locked": False,
    }


def rect(
    idg: IdGen,
    eid: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = "transparent",
    stroke: str = "stroke",
    stroke_width: int = 2,
    rounded: bool = True,
) -> dict[str, Any]:
    """Solid rectangle. Use ``fill`` from PALETTE keys."""
    el = _base_props(idg, eid) | {
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "backgroundColor": PALETTE.get(fill, fill),
        "strokeColor": PALETTE.get(stroke, stroke),
        "strokeWidth": stroke_width,
    }
    if not rounded:
        el["roundness"] = None
    return el


def ellipse(
    idg: IdGen,
    eid: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = "user",
) -> dict[str, Any]:
    el = _base_props(idg, eid) | {
        "type": "ellipse",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "backgroundColor": PALETTE.get(fill, fill),
    }
    el["roundness"] = None
    return el


def text(
    idg: IdGen,
    eid: str,
    x: float,
    y: float,
    body: str,
    *,
    size: int = SIZE_LABEL,
    align: str = "center",
    color: str = "stroke",
    width: int | None = None,
) -> dict[str, Any]:
    """Free-floating text. ``width`` is a rough box width; Excalidraw resizes
    on open via ``autoResize: true`` when the body exceeds the box, so the
    estimate only affects the initial layout."""
    lines = body.split("\n")
    longest = max((len(line) for line in lines), default=1)
    char_w = max(7, int(size * 0.55))
    estimated_w = max(width or 0, longest * char_w)
    h = max(20, int(size * 1.4 * len(lines)))
    el = _base_props(idg, eid) | {
        "type": "text",
        "x": x,
        "y": y,
        "width": estimated_w,
        "height": h,
        "strokeColor": PALETTE.get(color, color),
        "strokeWidth": 1,
        "text": body,
        "fontSize": size,
        "fontFamily": FONT_BODY,
        "textAlign": align,
        "verticalAlign": "top",
        "baseline": int(size * 0.85),
        "containerId": None,
        "originalText": body,
        "lineHeight": 1.25,
        "autoResize": True,
    }
    el["roundness"] = None
    return el


def labeled_box(
    idg: IdGen,
    slug: str,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    *,
    fill: str = "wrapped",
    label_size: int = SIZE_LABEL,
    label_color: str = "stroke",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Returns (rect, label). The label sits centered over the rectangle.

    Caller can append both to the elements list. When you need an arrow
    bound to this box, reference ``rect["id"]``."""
    box = rect(idg, idg.make(f"box_{slug}"), x, y, w, h, fill=fill)
    lines = label.split("\n")
    line_count = len(lines)
    line_h = label_size * 1.4
    total_h = line_count * line_h
    pad = (h - total_h) / 2
    label_y = y + max(8, pad)
    label_w = w - 16
    longest = max((len(line) for line in lines), default=1)
    char_w = max(7, int(label_size * 0.55))
    text_w = min(label_w, max(longest * char_w, 40))
    label_x = x + (w - text_w) / 2
    lbl = text(
        idg,
        idg.make(f"lbl_{slug}"),
        label_x,
        label_y,
        label,
        size=label_size,
        color=label_color,
        width=int(text_w),
    )
    return box, lbl


def arrow(
    idg: IdGen,
    eid: str,
    src: dict[str, Any],
    dst: dict[str, Any],
    *,
    src_anchor: tuple[float, float] | None = None,
    dst_anchor: tuple[float, float] | None = None,
    style: str = "solid",
    color: str = "stroke",
) -> dict[str, Any]:
    """Directed arrow from ``src`` to ``dst``. Anchors default to source's
    right-center and dst's left-center; pass ``src_anchor=(x,y)`` (relative
    to src x,y) to override."""
    sx, sy, sw, sh = src["x"], src["y"], src["width"], src["height"]
    dx, dy, dw, dh = dst["x"], dst["y"], dst["width"], dst["height"]
    if src_anchor is None:
        src_x = sx + sw
        src_y = sy + sh / 2
    else:
        src_x = sx + src_anchor[0]
        src_y = sy + src_anchor[1]
    if dst_anchor is None:
        dst_x = dx
        dst_y = dy + dh / 2
    else:
        dst_x = dx + dst_anchor[0]
        dst_y = dy + dst_anchor[1]
    rel_dx = dst_x - src_x
    rel_dy = dst_y - src_y
    el = _base_props(idg, eid) | {
        "type": "arrow",
        "x": src_x,
        "y": src_y,
        "width": abs(rel_dx),
        "height": abs(rel_dy),
        "strokeColor": PALETTE.get(color, color),
        "strokeStyle": style,
        "points": [[0, 0], [rel_dx, rel_dy]],
        "lastCommittedPoint": None,
        "startBinding": {"elementId": src["id"], "focus": 0, "gap": 4},
        "endBinding": {"elementId": dst["id"], "focus": 0, "gap": 4},
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "elbowed": False,
    }
    el["roundness"] = None
    src.setdefault("boundElements", []).append({"id": eid, "type": "arrow"})
    dst.setdefault("boundElements", []).append({"id": eid, "type": "arrow"})
    return el


def line(
    idg: IdGen,
    eid: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    style: str = "solid",
    color: str = "stroke",
    stroke_width: int = 2,
) -> dict[str, Any]:
    """Free-floating line (no bindings). Used for grouping markers / dividers."""
    el = _base_props(idg, eid) | {
        "type": "line",
        "x": x1,
        "y": y1,
        "width": x2 - x1,
        "height": y2 - y1,
        "strokeColor": PALETTE.get(color, color),
        "strokeStyle": style,
        "strokeWidth": stroke_width,
        "points": [[0, 0], [x2 - x1, y2 - y1]],
        "lastCommittedPoint": None,
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": None,
    }
    el["roundness"] = None
    return el


# ---------------------------------------------------------------------------
# Common scene fragments
# ---------------------------------------------------------------------------


def title_block(idg: IdGen, x: float, y: float, title: str, subtitle: str) -> list[dict[str, Any]]:
    return [
        text(idg, idg.make("title"), x, y, title, size=SIZE_TITLE, align="left"),
        text(
            idg,
            idg.make("subtitle"),
            x,
            y + 36,
            subtitle,
            size=SIZE_SUBTITLE,
            color="#495057",
            align="left",
        ),
    ]


def section_label(idg: IdGen, slug: str, x: float, y: float, label: str) -> dict[str, Any]:
    """Corner annotation for v4.1 section reference."""
    return text(
        idg,
        idg.make(f"sec_{slug}"),
        x,
        y,
        label,
        size=SIZE_SMALL,
        color="#868e96",
        align="left",
    )


def legend_block(idg: IdGen, x: float, y: float) -> list[dict[str, Any]]:
    """Standard color legend at bottom-left of every diagram."""
    items = [
        ("wrapped", "wrapped OSS (DuckDB / Polars / Dagster / pyiceberg / dlt / LiteLLM)"),
        ("built", "built by Nucleus (ctx SDK / AMA / Error Translation / CLI / Workbench / Copilot)"),
        ("storage", "storage substrate (S3 / MinIO / SeaweedFS / Iceberg files)"),
        ("user", "user-facing surface (CLI prompt / Workbench / persona)"),
        ("immortal", "Tier 0 immortal (Arrow / Iceberg / Parquet / Lance / OpenLineage)"),
    ]
    out: list[dict[str, Any]] = [
        text(idg, idg.make("legend_title"), x, y, "Legend", size=SIZE_BADGE, align="left"),
    ]
    for i, (kind, desc) in enumerate(items):
        row_y = y + 24 + i * 26
        sw = rect(idg, idg.make(f"legend_sw_{kind}"), x, row_y, 20, 20, fill=kind)
        lbl = text(
            idg,
            idg.make(f"legend_lbl_{kind}"),
            x + 30,
            row_y + 2,
            desc,
            size=SIZE_SMALL,
            color="#343a40",
            align="left",
        )
        out.extend([sw, lbl])
    return out


# ---------------------------------------------------------------------------
# Diagram 01 - Overview
# ---------------------------------------------------------------------------


def mk_overview() -> dict[str, Any]:
    idg = IdGen("d01")
    elems: list[dict[str, Any]] = []

    elems.extend(title_block(
        idg,
        40,
        30,
        "Nucleus - Full Stack Overview",
        "5 layers, bottom-up: Physics -> Engines -> Coordination -> Intelligence -> Experience",
    ))
    elems.append(section_label(idg, "overview", 40, 80, "v4.1 Section 3.1 (locked numbering)"))

    persona_x, persona_y = 1000, 100
    persona = ellipse(idg, idg.make("persona"), persona_x, persona_y, 460, 60, fill="user")
    persona_lbl = text(
        idg,
        idg.make("persona_lbl"),
        persona_x + 60,
        persona_y + 18,
        "5-engineer startup data team (greenfield, 100GB-5TB, MacBooks)",
        size=SIZE_LABEL,
        align="left",
    )
    elems.extend([persona, persona_lbl])

    layer_x = 60
    layer_w = 1700
    layer_h = 170
    bands = [
        ("L4 EXPERIENCE", "user", 200),
        ("L3 INTELLIGENCE (differentiator, v0.2+)", "built", 390),
        ("L2 COORDINATION (THE wrap-not-build crown jewel)", "built", 580),
        ("L1 ENGINES (wrapped, swappable)", "wrapped", 770),
        ("L0 PHYSICS (Tier 0 immortal)", "immortal", 960),
    ]
    band_rects: dict[str, dict[str, Any]] = {}
    for label, fill, y in bands:
        b = rect(
            idg,
            idg.make(f"band_{label.split()[0]}"),
            layer_x,
            y,
            layer_w,
            layer_h,
            fill=fill,
            stroke_width=1,
        )
        band_rects[label] = b
        lbl = text(
            idg,
            idg.make(f"bandlbl_{label.split()[0]}"),
            layer_x + 14,
            y + 8,
            label,
            size=SIZE_BADGE,
            align="left",
            color="#212529",
        )
        elems.extend([b, lbl])

    inset_y = {200: 230, 390: 420, 580: 610, 770: 800, 960: 990}

    cli_box, cli_lbl = labeled_box(
        idg, "exp_cli", 100, inset_y[200], 320, 110,
        "nucleus CLI\n(init / up / run / ingest / query / chat / list / runs / schedule / workbench)",
        fill="user",
    )
    wb_box, wb_lbl = labeled_box(
        idg, "exp_wb", 470, inset_y[200], 320, 110,
        "Workbench\n(FastAPI + React: assets / catalog / query / chat)",
        fill="user",
    )
    sdk_box, sdk_lbl = labeled_box(
        idg, "exp_sdk", 840, inset_y[200], 320, 110,
        "ctx SDK\n@nucleus.asset / @nucleus.check / ctx.sql / ctx.copy_from",
        fill="built",
    )
    notebook_box, notebook_lbl = labeled_box(
        idg, "exp_marimo", 1210, inset_y[200], 320, 110,
        "Marimo notebooks\n(v0.3+, optional surface)",
        fill="user",
    )
    elems.extend([cli_box, cli_lbl, wb_box, wb_lbl, sdk_box, sdk_lbl, notebook_box, notebook_lbl])

    copilot_box, copilot_lbl = labeled_box(
        idg, "ai_copilot", 100, inset_y[390], 380, 110,
        "AI Copilot (nucleus chat)\nProject context (4KB cap, 5 redactions)",
        fill="built",
    )
    litellm_box, litellm_lbl = labeled_box(
        idg, "ai_litellm", 530, inset_y[390], 320, 110,
        "LiteLLM router\nProvider-agnostic (BYOK)",
        fill="wrapped",
    )
    providers_box, providers_lbl = labeled_box(
        idg, "ai_providers", 900, inset_y[390], 320, 110,
        "Anthropic | OpenAI |\nAzure OpenAI | Ollama (local)",
        fill="wrapped",
    )
    schemactx_box, schemactx_lbl = labeled_box(
        idg, "ai_schema", 1370, inset_y[390], 170, 110,
        "Schema +\nlineage\n(v0.5+)",
        fill="muted",
        label_size=SIZE_SMALL,
    )
    elems.extend([copilot_box, copilot_lbl, litellm_box, litellm_lbl,
                  providers_box, providers_lbl, schemactx_box, schemactx_lbl])

    ama_box, ama_lbl = labeled_box(
        idg, "co_ama", 100, inset_y[580], 360, 110,
        "Asset Materialization\nAdapter (AMA, ~500 LOC)",
        fill="built",
    )
    err_box, err_lbl = labeled_box(
        idg, "co_err", 480, inset_y[580], 280, 110,
        "Error Translation\nLayer (NE-codes)",
        fill="built",
    )
    ledger_box, ledger_lbl = labeled_box(
        idg, "co_ledger", 780, inset_y[580], 220, 110,
        "Run Ledger\n(NDJSON)",
        fill="built",
    )
    sched_box, sched_lbl = labeled_box(
        idg, "co_sched", 1020, inset_y[580], 220, 110,
        "Scheduling\ndaemon",
        fill="built",
    )
    locks_box, locks_lbl = labeled_box(
        idg, "co_locks", 1260, inset_y[580], 130, 110,
        "Locks\n(advisory)",
        fill="built",
    )
    dagster_box, dagster_lbl = labeled_box(
        idg, "co_dagster", 1410, inset_y[580], 130, 110,
        "Dagster\n(hidden)",
        fill="wrapped",
    )
    elems.extend([ama_box, ama_lbl, err_box, err_lbl, ledger_box, ledger_lbl,
                  sched_box, sched_lbl, locks_box, locks_lbl, dagster_box, dagster_lbl])

    duckdb_box, duckdb_lbl = labeled_box(idg, "en_duck", 100, inset_y[770], 260, 110,
                                          "DuckDB\n(SQL, default)", fill="wrapped")
    polars_box, polars_lbl = labeled_box(idg, "en_polars", 380, inset_y[770], 260, 110,
                                          "Polars\n(DataFrame)", fill="wrapped")
    pyice_box, pyice_lbl = labeled_box(idg, "en_pyice", 660, inset_y[770], 260, 110,
                                        "pyiceberg\n(catalog + commit)", fill="wrapped")
    dlt_box, dlt_lbl = labeled_box(idg, "en_dlt", 940, inset_y[770], 260, 110,
                                    "dlt\n(connectors v0.3+)", fill="wrapped")
    arrow_box, arrow_lbl = labeled_box(idg, "en_arrow", 1220, inset_y[770], 320, 110,
                                        "Apache Arrow\n(zero-copy IPC bridge)", fill="immortal")
    elems.extend([duckdb_box, duckdb_lbl, polars_box, polars_lbl, pyice_box, pyice_lbl,
                  dlt_box, dlt_lbl, arrow_box, arrow_lbl])

    iceberg_box, iceberg_lbl = labeled_box(idg, "ph_ice", 100, inset_y[960], 280, 110,
                                            "Iceberg metadata\n(snapshots + manifests)", fill="immortal")
    parquet_box, parquet_lbl = labeled_box(idg, "ph_pq", 400, inset_y[960], 220, 110,
                                            "Parquet\nfiles", fill="immortal")
    s3_box, s3_lbl = labeled_box(idg, "ph_s3", 640, inset_y[960], 320, 110,
                                  "S3 / MinIO / SeaweedFS\n(object store)", fill="storage")
    lance_box, lance_lbl = labeled_box(idg, "ph_lance", 980, inset_y[960], 220, 110,
                                        "Lance\n(multimodal, v0.5+)", fill="muted")
    ol_box, ol_lbl = labeled_box(idg, "ph_ol", 1220, inset_y[960], 320, 110,
                                  "OpenLineage + OpenTelemetry\n(observability protocols)", fill="immortal")
    elems.extend([iceberg_box, iceberg_lbl, parquet_box, parquet_lbl, s3_box, s3_lbl,
                  lance_box, lance_lbl, ol_box, ol_lbl])

    elems.append(arrow(idg, idg.make("ar_persona_cli"), persona, cli_box,
                       src_anchor=(50, 60), dst_anchor=(160, 0)))
    elems.append(arrow(idg, idg.make("ar_cli_ama"), cli_box, ama_box,
                       src_anchor=(160, 110), dst_anchor=(180, 0)))
    elems.append(arrow(idg, idg.make("ar_wb_ama"), wb_box, ama_box,
                       src_anchor=(160, 110), dst_anchor=(180, 0)))
    elems.append(arrow(idg, idg.make("ar_sdk_ama"), sdk_box, ama_box,
                       src_anchor=(160, 110), dst_anchor=(180, 0)))
    elems.append(arrow(idg, idg.make("ar_ama_err"), ama_box, err_box,
                       src_anchor=(360, 55), dst_anchor=(0, 55)))
    elems.append(arrow(idg, idg.make("ar_ama_pyice"), ama_box, pyice_box,
                       src_anchor=(180, 110), dst_anchor=(130, 0)))
    elems.append(arrow(idg, idg.make("ar_pyice_iceberg"), pyice_box, iceberg_box,
                       src_anchor=(130, 110), dst_anchor=(140, 0)))
    elems.append(arrow(idg, idg.make("ar_iceberg_s3"), iceberg_box, s3_box,
                       src_anchor=(280, 55), dst_anchor=(0, 55)))
    elems.append(arrow(idg, idg.make("ar_parquet_s3"), parquet_box, s3_box,
                       src_anchor=(220, 55), dst_anchor=(0, 55)))
    elems.append(arrow(idg, idg.make("ar_copilot_litellm"), copilot_box, litellm_box,
                       src_anchor=(380, 55), dst_anchor=(0, 55)))
    elems.append(arrow(idg, idg.make("ar_litellm_providers"), litellm_box, providers_box,
                       src_anchor=(320, 55), dst_anchor=(0, 55)))
    elems.append(arrow(idg, idg.make("ar_polars_arrow"), polars_box, arrow_box,
                       src_anchor=(260, 55), dst_anchor=(0, 55)))
    elems.append(arrow(idg, idg.make("ar_duckdb_arrow"), duckdb_box, arrow_box,
                       src_anchor=(260, 80), dst_anchor=(0, 80)))

    giants_box, giants_lbl = labeled_box(
        idg, "giants", 1400, 1190, 380, 100,
        "YIELD TO GIANTS\nDatabricks / Snowflake / Polaris / Trino\n(Iceberg portability, zero migration)",
        fill="wrapped",
        label_size=SIZE_SMALL,
    )
    elems.extend([giants_box, giants_lbl])
    elems.append(arrow(idg, idg.make("ar_iceberg_giants"), iceberg_box, giants_box,
                       src_anchor=(280, 0), dst_anchor=(0, 50), color="#1864ab"))
    elems.append(text(idg, idg.make("giants_note"), 1400, 1300,
                      "Mode 1 graduation - same Iceberg lake,\nzero application code change.",
                      size=SIZE_SMALL, color="#1864ab", align="left"))

    elems.extend(legend_block(idg, 40, 1190))

    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 02 - Physics
# ---------------------------------------------------------------------------


def mk_physics() -> dict[str, Any]:
    idg = IdGen("d02")
    elems: list[dict[str, Any]] = []
    elems.extend(title_block(
        idg, 40, 30,
        "Layer 0 - Physics: Tier 0 Immortal Substrate",
        "Iceberg metadata stack + Parquet data files + S3 object store + Lance (v0.5+ multimodal)",
    ))
    elems.append(section_label(idg, "physics", 40, 80, "v4.1 Section 4 + ADR-008 (storage substrate)"))

    badge_x, badge_y = 1320, 30
    badge_box = rect(idg, idg.make("badge_box"), badge_x, badge_y, 360, 60, fill="immortal")
    badge_lbl = text(idg, idg.make("badge_lbl"), badge_x + 14, badge_y + 18,
                     "Tier 0 immortal: never swap; multi-vendor;\nApache / CNCF / LF backed.",
                     size=SIZE_SMALL, align="left")
    elems.extend([badge_box, badge_lbl])

    col_x = 80
    spacing = 130
    catalog_box, catalog_lbl = labeled_box(
        idg, "ph_catalog", col_x, 160, 360, 110,
        "pyiceberg Catalog\n(SqlCatalog v0.1, RestCatalog v0.3+)",
        fill="wrapped",
    )
    elems.extend([catalog_box, catalog_lbl])

    md_box, md_lbl = labeled_box(
        idg, "ph_metadata", col_x, 160 + spacing, 360, 110,
        "metadata.json\nschema, partition spec, snapshot list",
        fill="immortal",
    )
    elems.extend([md_box, md_lbl])

    ml_box, ml_lbl = labeled_box(
        idg, "ph_manifest_list", col_x, 160 + spacing * 2, 360, 110,
        "manifest list (.avro)\npointer to per-snapshot manifests",
        fill="immortal",
    )
    elems.extend([ml_box, ml_lbl])

    mf_box, mf_lbl = labeled_box(
        idg, "ph_manifest", col_x, 160 + spacing * 3, 360, 110,
        "manifest file (.avro)\ndata file paths + statistics",
        fill="immortal",
    )
    elems.extend([mf_box, mf_lbl])

    df_box, df_lbl = labeled_box(
        idg, "ph_data", col_x, 160 + spacing * 4, 360, 110,
        "Parquet data files\n(columnar, immutable, S3 objects)",
        fill="immortal",
    )
    elems.extend([df_box, df_lbl])

    elems.append(arrow(idg, idg.make("ar_cat_md"), catalog_box, md_box,
                       src_anchor=(180, 110), dst_anchor=(180, 0)))
    elems.append(arrow(idg, idg.make("ar_md_ml"), md_box, ml_box,
                       src_anchor=(180, 110), dst_anchor=(180, 0)))
    elems.append(arrow(idg, idg.make("ar_ml_mf"), ml_box, mf_box,
                       src_anchor=(180, 110), dst_anchor=(180, 0)))
    elems.append(arrow(idg, idg.make("ar_mf_df"), mf_box, df_box,
                       src_anchor=(180, 110), dst_anchor=(180, 0)))

    obj_x = 540
    obj_box, obj_lbl = labeled_box(
        idg, "ph_object_store", obj_x, 760, 380, 130,
        "S3 / MinIO / SeaweedFS\n(S3-API substrate)\nAll metadata + data live as objects",
        fill="storage",
    )
    elems.extend([obj_box, obj_lbl])
    elems.append(arrow(idg, idg.make("ar_df_obj"), df_box, obj_box,
                       src_anchor=(360, 55), dst_anchor=(0, 65)))

    snap_y = 200
    snap_w = 200
    snap_h = 90
    snaps = []
    for i in range(3):
        sx = 540 + i * 280
        s_box, s_lbl = labeled_box(
            idg, f"snap_{i+1}", sx, snap_y, snap_w, snap_h,
            f"snapshot-{i+1}\n@ t{i+1}",
            fill="immortal",
            label_size=SIZE_SMALL,
        )
        snaps.append(s_box)
        elems.extend([s_box, s_lbl])
    for i in range(2):
        ar = arrow(idg, idg.make(f"ar_snap_{i+1}"), snaps[i], snaps[i + 1])
        elems.append(ar)
        ann_x = 540 + i * 280 + 200
        ann = text(idg, idg.make(f"ar_snap_ann_{i+1}"),
                   ann_x + 5, snap_y + snap_h + 10,
                   "atomic commit\n(catalog)",
                   size=SIZE_SMALL, color="#1864ab", align="left")
        elems.append(ann)

    write_x = 540
    write_y = 360
    write_box, write_lbl = labeled_box(
        idg, "write_flow", write_x, write_y, 760, 100,
        "WRITE PATH (per snapshot, all-or-nothing)\n"
        "1) write Parquet data file -> 2) write manifest -> 3) write manifest list -> 4) catalog atomic commit -> snapshot+1",
        fill="muted",
        label_size=SIZE_SMALL,
    )
    elems.extend([write_box, write_lbl])

    lance_x = 1000
    lance_y = 760
    lance_box, lance_lbl = labeled_box(
        idg, "ph_lance", lance_x, lance_y, 380, 130,
        "Lance (v0.5+)\nmultimodal + vector tables\n(images, embeddings, tensors)",
        fill="muted",
    )
    elems.extend([lance_box, lance_lbl])

    elems.append(text(idg, idg.make("note_lance"), lance_x, lance_y + 140,
                      "Lance lives next to Iceberg, not on top of it.\nDifferent table format, same S3 substrate.",
                      size=SIZE_SMALL, color="#495057", align="left"))

    proto_x = 540
    proto_y = 540
    proto_box, proto_lbl = labeled_box(
        idg, "ph_proto", proto_x, proto_y, 760, 100,
        "OBSERVABILITY PROTOCOLS (Tier 0)\nOpenLineage events emitted per materialization | OpenTelemetry traces / metrics / logs",
        fill="immortal",
        label_size=SIZE_SMALL,
    )
    elems.extend([proto_box, proto_lbl])

    elems.extend(legend_block(idg, 40, 940))
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 03 - Engines
# ---------------------------------------------------------------------------


def mk_engines() -> dict[str, Any]:
    idg = IdGen("d03")
    elems: list[dict[str, Any]] = []
    elems.extend(title_block(
        idg, 40, 30,
        "Layer 1 - Engines: Wrap, Not Build",
        "All engines wrapped behind ctx SDK; clean swap interface + smoke tests in CI per v4.1 Section 9.3",
    ))
    elems.append(section_label(idg, "engines", 40, 80, "v4.1 Section 5 + Hard Constraint #1 (no JVM in core path)"))

    badge_x, badge_y = 1380, 30
    badge_box = rect(idg, idg.make("badge_box"), badge_x, badge_y, 300, 60, fill="immortal")
    badge_lbl = text(idg, idg.make("badge_lbl"), badge_x + 14, badge_y + 18,
                     "Constraint #1: no JVM in the\nalways-on hot path.",
                     size=SIZE_SMALL, align="left")
    elems.extend([badge_box, badge_lbl])

    engines = [
        ("duckdb", "DuckDB (SQL)\nC++, MIT\niceberg_scan + httpfs", "DataFusion (Apache, Rust)"),
        ("polars", "Polars (DataFrame)\nRust, MIT\nLazy / Eager + streaming", "DataFusion DF (Apache)"),
        ("pyiceberg", "pyiceberg (catalog ops)\nPython, Apache 2.0\nappend / overwrite / expire", "iceberg-go / iceberg-rust"),
        ("dlt", "dlt (ingestion v0.3+)\nPython, Apache 2.0\n100+ source connectors", "Sling / Singer / custom"),
        ("litellm", "LiteLLM (LLM router)\nPython, MIT\nOpenAI/Anthropic/Azure/Ollama", "direct provider SDKs"),
    ]
    box_w = 320
    box_h = 130
    gap = 30
    start_x = 40
    start_y = 180
    engine_boxes: dict[str, dict[str, Any]] = {}
    for i, (slug, label, swap) in enumerate(engines):
        x = start_x + i * (box_w + gap)
        b, l = labeled_box(idg, f"en_{slug}", x, start_y, box_w, box_h,
                           label, fill="wrapped", label_size=SIZE_SMALL)
        engine_boxes[slug] = b
        elems.extend([b, l])
        swap_y = start_y + box_h + 20
        swap_label = f"swap target:\n{swap}"
        swap_box, swap_lbl = labeled_box(idg, f"swap_{slug}", x + 30, swap_y, box_w - 60, 80,
                                          swap_label, fill="muted", label_size=SIZE_SMALL)
        elems.extend([swap_box, swap_lbl])
        elems.append(arrow(idg, idg.make(f"ar_swap_{slug}"), engine_boxes[slug], swap_box,
                            src_anchor=(box_w / 2, box_h),
                            dst_anchor=((box_w - 60) / 2, 0),
                            style="dashed", color="#868e96"))
        elems.append(text(idg, idg.make(f"ar_swap_lbl_{slug}"),
                          x + box_w / 2 - 12, swap_y - 18,
                          "swap",
                          size=SIZE_SMALL, color="#868e96", align="left"))

    arrow_y = 460
    arrow_box, arrow_lbl = labeled_box(idg, "arrow", 40, arrow_y, 1690, 110,
                                        "Apache Arrow (Tier 0 immortal)\nzero-copy columnar IPC bridge between every engine - "
                                        "DuckDB, Polars, pyiceberg, LiteLLM all speak Arrow natively",
                                        fill="immortal", label_size=SIZE_SMALL)
    elems.extend([arrow_box, arrow_lbl])
    for slug in ["duckdb", "polars", "pyiceberg"]:
        eb = engine_boxes[slug]
        elems.append(arrow(idg, idg.make(f"ar_eng_arrow_{slug}"), eb, arrow_box,
                           src_anchor=(box_w / 2, box_h),
                           dst_anchor=(eb["x"] - 40 + box_w / 2, 0),
                           color="#0b7285"))

    iceberg_y = 620
    iceberg_box, iceberg_lbl = labeled_box(idg, "iceberg", 40, iceberg_y, 1690, 110,
                                            "Apache Iceberg (Tier 0 immortal)\nstructured table format - written by pyiceberg, read by DuckDB iceberg_scan",
                                            fill="immortal", label_size=SIZE_SMALL)
    elems.extend([iceberg_box, iceberg_lbl])

    rules_x = 40
    rules_y = 780
    rules_box = rect(idg, idg.make("rules_box"), rules_x, rules_y, 1690, 130, fill="muted")
    rules_lbl = text(idg, idg.make("rules_lbl"), rules_x + 14, rules_y + 14,
                     "Wrap-not-build discipline (v4.1 Section 5):\n"
                     " 1. Read official docs before integration (AGENTS.md Section 11.12)\n"
                     " 2. Exact-pin in pyproject.toml (Constraint #11): duckdb==1.1.3, polars==1.18.0, pyiceberg==0.11.1, dagster==1.9.5, litellm==1.83.14\n"
                     " 3. One-component-per-PR upgrades; major versions require ADR\n"
                     " 4. Each Tier 1 engine: clean swap interface + 5-10 smoke tests in CI; full adapter built ON-DEMAND (Composability Tax avoided)",
                     size=SIZE_SMALL, color="#212529", align="left")
    elems.extend([rules_box, rules_lbl])

    elems.extend(legend_block(idg, 40, 940))
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 04 - Coordination (the crown jewel)
# ---------------------------------------------------------------------------


def mk_coordination() -> dict[str, Any]:
    idg = IdGen("d04")
    elems: list[dict[str, Any]] = []
    elems.extend(title_block(
        idg, 40, 30,
        "Layer 2 - Coordination: AMA + Error Translation Layer",
        "The wrap-not-build crown jewel - hides Dagster, owns the data path, mandatory error translation",
    ))
    elems.append(section_label(idg, "coord", 40, 80,
                               "v4.1 Sections 6.2 (AMA) + 6.4 (Error Translation, mandatory release blocker) + 6.5 (replaceability)"))

    cli_box, cli_lbl = labeled_box(idg, "cli_call", 40, 160, 200, 90,
                                    "nucleus run\nasset_key", fill="user")
    sdk_box, sdk_lbl = labeled_box(idg, "sdk_call", 40, 280, 200, 90,
                                    "ctx SDK\nnucleus.materialize", fill="built")
    elems.extend([cli_box, cli_lbl, sdk_box, sdk_lbl])

    ama_box, ama_lbl = labeled_box(idg, "ama", 320, 220, 460, 200,
        "ASSET MATERIALIZATION ADAPTER (~500 LOC)\n"
        "1. validate output vs contract (sdk/contracts.py)\n"
        "2. enforce partition constraints\n"
        "3. delegate atomic write to pyiceberg + catalog\n"
        "4. emit OpenLineage event (lineage.py)\n"
        "5. update run ledger + freshness + cost",
        fill="built",
        label_size=SIZE_SMALL,
    )
    elems.extend([ama_box, ama_lbl])
    elems.append(arrow(idg, idg.make("ar_cli_ama"), cli_box, ama_box,
                       src_anchor=(200, 45), dst_anchor=(0, 60)))
    elems.append(arrow(idg, idg.make("ar_sdk_ama"), sdk_box, ama_box,
                       src_anchor=(200, 45), dst_anchor=(0, 140)))

    body_box, body_lbl = labeled_box(idg, "asset_body", 850, 230, 280, 90,
                                      "asset function body\n(user code)", fill="user")
    elems.extend([body_box, body_lbl])
    elems.append(arrow(idg, idg.make("ar_ama_body"), ama_box, body_box,
                       src_anchor=(460, 60), dst_anchor=(0, 45)))

    pyice_box, pyice_lbl = labeled_box(idg, "pyiceberg", 850, 340, 280, 90,
                                        "pyiceberg\ncatalog.commit_table()", fill="wrapped")
    elems.extend([pyice_box, pyice_lbl])
    elems.append(arrow(idg, idg.make("ar_ama_pyice"), ama_box, pyice_box,
                       src_anchor=(460, 140), dst_anchor=(0, 45)))

    iceberg_box, iceberg_lbl = labeled_box(idg, "iceberg_snap", 1180, 230, 280, 90,
                                            "Iceberg snapshot\ncommitted (atomic)",
                                            fill="immortal")
    elems.extend([iceberg_box, iceberg_lbl])
    elems.append(arrow(idg, idg.make("ar_pyice_iceberg"), pyice_box, iceberg_box,
                       src_anchor=(280, 45), dst_anchor=(0, 70)))

    ledger_box, ledger_lbl = labeled_box(idg, "run_ledger", 1180, 340, 280, 90,
        "Run Ledger\n.nucleus/runs/runs.ndjson", fill="built")
    elems.extend([ledger_box, ledger_lbl])
    elems.append(arrow(idg, idg.make("ar_ama_ledger"), ama_box, ledger_box,
                       src_anchor=(460, 180), dst_anchor=(0, 45)))

    dagster_box, dagster_lbl = labeled_box(idg, "dagster_hidden", 320, 460, 460, 110,
        "Dagster (embedded substrate, hidden behind ctx)\n"
        "Asset graph topology + sensors + schedules + retries",
        fill="wrapped", label_size=SIZE_SMALL)
    elems.extend([dagster_box, dagster_lbl])
    elems.append(line(idg, idg.make("ln_dagster_hide"), 320, 450, 780, 450,
                      style="dashed", color="#868e96", stroke_width=1))
    elems.append(text(idg, idg.make("dagster_note"), 320, 580,
                      "scripts/dagster_leak_check.py guards: zero 'dagster.' strings in user-facing output (v4.1 Section 6.5)",
                      size=SIZE_SMALL, color="#868e96", align="left"))

    err_y = 720
    err_box, err_lbl = labeled_box(idg, "err_translator", 320, err_y, 460, 270,
        "ERROR TRANSLATION LAYER\ncoordination/error_translation.py\n"
        "Every external exception -> typed NucleusError",
        fill="built", label_size=SIZE_SMALL)
    elems.extend([err_box, err_lbl])

    src_x = 40
    src_y = err_y
    sources = [
        ("dagster_err", "dagster.DagsterStepExecutionError", "wrapped"),
        ("duckdb_err", "duckdb.OutOfMemoryException", "wrapped"),
        ("pyice_err", "pyiceberg.CommitFailedException", "wrapped"),
        ("polars_err", "polars.SchemaError", "wrapped"),
        ("py_err", "stdlib FileExistsError (race)", "muted"),
    ]
    src_boxes = []
    for i, (slug, label, fill) in enumerate(sources):
        b, l = labeled_box(idg, slug, src_x, src_y + i * 55, 250, 50,
                           label, fill=fill, label_size=SIZE_SMALL)
        src_boxes.append(b)
        elems.extend([b, l])
        elems.append(arrow(idg, idg.make(f"ar_src_{slug}"), b, err_box,
                           src_anchor=(250, 25), dst_anchor=(0, 30 + i * 25), color="#c92a2a"))

    out_y = err_y
    outputs = [
        ("ne1", "NucleusInternalError (NE3000)\n[asset:fct_orders]\nuser_message + fix_hint + docs_url"),
        ("ne2", "NucleusResourceError (NE2007)\nout-of-memory; suggest partition or compute=databricks"),
        ("ne3", "NucleusCommitConflictError (NE3001)\nconcurrent write; suggest retry or schedule check"),
        ("ne4", "NucleusSchemaError (NE3003)\ncontract violation; suggest schema sync"),
        ("ne5", "NucleusConcurrentRunError (NE3008)\nadvisory lock conflict per ADR-024"),
    ]
    for i, (slug, label) in enumerate(outputs):
        b, l = labeled_box(idg, slug, 850, out_y + i * 55, 580, 50,
                           label, fill="built", label_size=SIZE_SMALL)
        elems.extend([b, l])
        elems.append(arrow(idg, idg.make(f"ar_out_{slug}"), err_box, b,
                           src_anchor=(460, 30 + i * 25), dst_anchor=(0, 25), color="#2b8a3e"))

    rules_y = 1010
    rules_box = rect(idg, idg.make("rules_box"), 40, rules_y, 1690, 130, fill="muted")
    rules_lbl = text(idg, idg.make("rules_lbl"), 54, rules_y + 14,
        "Side concerns wired into the AMA write path:\n"
        "  - Locks (coordination/locks.py): per-asset advisory FileLock prevents racing nucleus run invocations (P0-2 / ADR-024 / NE3008)\n"
        "  - Scheduling daemon (coordination/daemon.py): cron + sensor evaluation; nucleus-mini-scheduler-ready per v4.1 Section 6.7\n"
        "  - DuckDB memory_limit guard (P0-1 / ADR-024 / NE2007): 60% RAM cap injected at connection init - silent OOM mitigation\n"
        "  - expire_old_snapshots maintenance (P0-3 / ADR-024): runs after every successful commit; prevents catalog bloat",
        size=SIZE_SMALL, color="#212529", align="left")
    elems.extend([rules_box, rules_lbl])

    elems.extend(legend_block(idg, 40, 1170))
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 05 - Intelligence
# ---------------------------------------------------------------------------


def mk_intelligence() -> dict[str, Any]:
    idg = IdGen("d05")
    elems: list[dict[str, Any]] = []
    elems.extend(title_block(
        idg, 40, 30,
        "Layer 3 - Intelligence: AI Copilot (v0.2 chat MVP)",
        # Diagram subtitle deliberately counter-frames the retired ADR-002 angles below.
        "AI-assisted by design (NOT AI-first / AI-native): we are USERS of LLMs, never hosts",  # <!-- banned-term: AI-first --> <!-- banned-term: AI-native -->
    ))
    elems.append(section_label(idg, "intel", 40, 80,
                               "v4.1 Section 7 (staging) + ADR-015 (chat MVP) + ADR-011 (privacy)"))

    badge_x, badge_y = 1240, 30
    badge_box = rect(idg, idg.make("badge_box"), badge_x, badge_y, 440, 60, fill="muted")
    badge_lbl = text(idg, idg.make("badge_lbl"), badge_x + 14, badge_y + 12,
        # Counter-frames the retired ADR-002 angle below.
        "Pillar #3 (engineering, not marketing).\nNot a category pivot to 'AI-native data platform'.",  # <!-- banned-term: AI-native -->
        size=SIZE_SMALL, align="left")
    elems.extend([badge_box, badge_lbl])

    copilot_x = 600
    copilot_y = 230
    copilot_box, copilot_lbl = labeled_box(idg, "copilot", copilot_x, copilot_y, 440, 200,
        "AI COPILOT\n"
        "intelligence/copilot.py - chat() entrypoint\n"
        "Single-turn synchronous (v0.2 MVP)\n"
        "Output: CopilotReply{ text, suggested_command, tokens, cost_usd }",
        fill="built", label_size=SIZE_SMALL)
    elems.extend([copilot_box, copilot_lbl])

    inputs = [
        ("schema", "Project metadata\n(nucleus_project.yaml)"),
        ("registry", "Asset registry\n(decorators inventory)"),
        ("err", "Recent NucleusErrors\n(NE-codes + messages)"),
        ("lineage", "Lineage graph\n(v0.5+, faded)"),
    ]
    for i, (slug, label) in enumerate(inputs):
        b, l = labeled_box(idg, f"in_{slug}", 60, 200 + i * 110, 280, 90,
                           label, fill="muted" if slug == "lineage" else "user",
                           label_size=SIZE_SMALL)
        elems.extend([b, l])
        elems.append(arrow(idg, idg.make(f"ar_in_{slug}"), b, copilot_box,
                           src_anchor=(280, 45),
                           dst_anchor=(0, 50 + i * 30), color="#1864ab"))

    redact_box, redact_lbl = labeled_box(idg, "redact", 60, 670, 280, 130,
        "Privacy gate (5 redactions)\n"
        " 1. SQL strings -> <SQL_REDACTED>\n"
        " 2. Row counts dropped\n"
        " 3. user/host -> <USER>/<HOST>\n"
        " 4. abs paths -> <PROJECT>\n"
        " 5. stack vars stripped\nHard cap 4 KB",
        fill="built", label_size=SIZE_SMALL)
    elems.extend([redact_box, redact_lbl])
    elems.append(arrow(idg, idg.make("ar_redact_copilot"), redact_box, copilot_box,
                       src_anchor=(280, 65),
                       dst_anchor=(0, 180), color="#5f3dc4"))

    litellm_x = 600
    litellm_y = 480
    litellm_box, litellm_lbl = labeled_box(idg, "litellm", litellm_x, litellm_y, 440, 110,
        "LiteLLM (provider router)\n"
        "litellm.completion(model=..., messages=[...])\n"
        "Pin: litellm==1.83.14",
        fill="wrapped", label_size=SIZE_SMALL)
    elems.extend([litellm_box, litellm_lbl])
    elems.append(arrow(idg, idg.make("ar_copilot_litellm"), copilot_box, litellm_box,
                       src_anchor=(220, 200), dst_anchor=(220, 0)))

    providers = [
        ("anthropic", "Anthropic\nclaude-3-5-haiku"),
        ("openai", "OpenAI\ngpt-4o-mini"),
        ("azure", "Azure OpenAI\n(BYOK)"),
        ("ollama", "Ollama (local)\nllama3.1:8b - offline"),
    ]
    pv_w = 220
    pv_gap = 20
    pv_total = len(providers) * pv_w + (len(providers) - 1) * pv_gap
    pv_start_x = litellm_x + 220 - pv_total / 2
    pv_y = litellm_y + 180
    for i, (slug, label) in enumerate(providers):
        x = pv_start_x + i * (pv_w + pv_gap)
        b, l = labeled_box(idg, f"pv_{slug}", x, pv_y, pv_w, 80,
                           label, fill="wrapped", label_size=SIZE_SMALL)
        elems.extend([b, l])
        elems.append(arrow(idg, idg.make(f"ar_litellm_{slug}"), litellm_box, b,
                           src_anchor=(220, 110), dst_anchor=(pv_w / 2, 0)))

    budget_box, budget_lbl = labeled_box(idg, "budget", 1080, 230, 480, 200,
        "Token budget enforcement (ADR-015 Section 4)\n"
        "Pre-flight cost ceiling check BEFORE HTTP call:\n"
        "  default 2000 in / 1000 out / 0.10 USD per turn\n"
        "  override via nucleus_project.yaml copilot.pricing\n"
        "On exceed: NucleusBudgetExceededError (NE5012)\n"
        "Opt-in gate per ADR-011: NO outbound bytes\n"
        "until user creates .nucleus/copilot_opt_in",
        fill="built", label_size=SIZE_SMALL)
    elems.extend([budget_box, budget_lbl])

    explain_y = 800
    explain_box, explain_lbl = labeled_box(idg, "explain_pipe", 60, explain_y, 1620, 130,
        "ERROR EXPLANATION PIPELINE (v0.2+)\n"
        "NucleusError (NE-code, user_message, fix_hint, cause) ->  Copilot prompt builder ->  LiteLLM ->  human-language explanation rendered to CLI / Workbench\n"
        "Same translator outputs feed both 'just print to user' and 'ask Copilot to expand'.",
        fill="built", label_size=SIZE_SMALL)
    elems.extend([explain_box, explain_lbl])

    staging_y = 960
    staging_box = rect(idg, idg.make("staging_box"), 60, staging_y, 1620, 100, fill="muted")
    staging_lbl = text(idg, idg.make("staging_lbl"), 74, staging_y + 14,
        "Realistic staging (v4.1 Section 7.2 - Amendment 2 vs over-promised v4.0):\n"
        "  v0.1 = none  |  v0.2 = inline chat (this diagram)  |  v0.3 = schema-aware completion  |  "
        "v0.5 = lineage-aware refactoring + ctx.agent runtime + nucleus-mcp-server  |  v0.7 = doc generation + semantic graph queries",
        size=SIZE_SMALL, color="#212529", align="left")
    elems.extend([staging_box, staging_lbl])

    elems.extend(legend_block(idg, 40, 1100))
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 06 - Experience
# ---------------------------------------------------------------------------


def mk_experience() -> dict[str, Any]:
    idg = IdGen("d06")
    elems: list[dict[str, Any]] = []
    elems.extend(title_block(
        idg, 40, 30,
        "Layer 4 - Experience: 3 Equal Surfaces",
        "CLI + Workbench + ctx SDK all delegate to one Coordination layer; one mental model",
    ))
    elems.append(section_label(idg, "exp", 40, 80,
                               "v4.1 Section 8 + nucleus_cli_spec.md + nucleus_ctx_sdk_spec.md + ADR-016 (Workbench)"))

    persona_box, persona_lbl = labeled_box(idg, "persona", 600, 100, 480, 60,
        "User: data engineer in 5-engineer startup", fill="user")
    elems.extend([persona_box, persona_lbl])

    cli_x, wb_x, sdk_x = 60, 640, 1220
    col_w = 520
    col_y = 200
    col_h = 540

    cli_box, cli_lbl = labeled_box(idg, "cli", cli_x, col_y, col_w, col_h,
        "nucleus CLI\n"
        "(operator surface)", fill="user", label_size=SIZE_SUBTITLE)
    elems.extend([cli_box, cli_lbl])

    cli_cmds = [
        "nucleus init my-warehouse",
        "nucleus up   /  down",
        "nucleus run <asset_key>",
        "nucleus ingest postgres://... --table T --as raw.T",
        "nucleus query \"SELECT ... FROM raw.T LIMIT 10\"",
        "nucleus list",
        "nucleus runs (ledger)",
        "nucleus schedule (cron + sensors)",
        "nucleus chat \"why did fct_orders fail?\"",
        "nucleus workbench",
        "nucleus snapshot (Iceberg branches/tags)",
        "nucleus version  /  --help",
    ]
    for i, cmd in enumerate(cli_cmds):
        elems.append(text(idg, idg.make(f"cli_cmd_{i}"),
                          cli_x + 24, col_y + 70 + i * 32,
                          cmd, size=SIZE_SMALL, color="#212529", align="left"))

    wb_box, wb_lbl = labeled_box(idg, "wb", wb_x, col_y, col_w, col_h,
        "Workbench (v0.2+)\n"
        "(browser surface)", fill="user", label_size=SIZE_SUBTITLE)
    elems.extend([wb_box, wb_lbl])

    wb_lines = [
        "FastAPI backend (workbench/app.py)",
        "  - /api/health, /api/version",
        "  - /api/assets [list + single]",
        "  - /api/runs [+ SSE log stream]",
        "  - /api/query [POST: ctx.sql + DuckDB]",
        "  - /api/chat [POST: AI Copilot]",
        "  - /api/catalog, /api/schedules, /api/dashboard, /api/search",
        "",
        "React + Vite + Tailwind frontend",
        "  - asset graph view",
        "  - catalog browser",
        "  - query editor (Monaco)",
        "  - chat panel (Copilot)",
    ]
    for i, ln in enumerate(wb_lines):
        elems.append(text(idg, idg.make(f"wb_ln_{i}"),
                          wb_x + 24, col_y + 70 + i * 30,
                          ln, size=SIZE_SMALL, color="#212529", align="left"))

    sdk_box, sdk_lbl = labeled_box(idg, "sdk", sdk_x, col_y, col_w, col_h,
        "ctx SDK (Python)\n"
        "(developer surface)", fill="built", label_size=SIZE_SUBTITLE)
    elems.extend([sdk_box, sdk_lbl])

    sdk_lines = [
        "@nucleus.asset(key, deps, partitions, schedule)",
        "@nucleus.check(asset, severity)",
        "nucleus.materialize(asset_key)",
        "  -> MaterializationResult",
        "",
        "ctx.read(asset_key)         -> LazyFrame",
        "ctx.sql(\"... {{ ref('a') }}...\")",
        "ctx.copy_from(source, target=...)",
        "  - postgres / mysql / sqlite",
        "  - csv / parquet / json",
        "  - s3 / gcs / snowflake",
        "",
        "errors all subclass NucleusError",
    ]
    for i, ln in enumerate(sdk_lines):
        elems.append(text(idg, idg.make(f"sdk_ln_{i}"),
                          sdk_x + 24, col_y + 70 + i * 30,
                          ln, size=SIZE_SMALL, color="#212529", align="left"))

    elems.append(arrow(idg, idg.make("ar_persona_cli"), persona_box, cli_box,
                       src_anchor=(50, 60), dst_anchor=(col_w / 2, 0)))
    elems.append(arrow(idg, idg.make("ar_persona_wb"), persona_box, wb_box,
                       src_anchor=(240, 60), dst_anchor=(col_w / 2, 0)))
    elems.append(arrow(idg, idg.make("ar_persona_sdk"), persona_box, sdk_box,
                       src_anchor=(430, 60), dst_anchor=(col_w / 2, 0)))

    coord_y = 800
    coord_box, coord_lbl = labeled_box(idg, "coord", 60, coord_y, 1680, 100,
        "L2 COORDINATION (single source of truth for asset materialization)\n"
        "AMA + Error Translation + Run Ledger + Locks + Scheduling daemon",
        fill="built", label_size=SIZE_SUBTITLE)
    elems.extend([coord_box, coord_lbl])

    elems.append(arrow(idg, idg.make("ar_cli_coord"), cli_box, coord_box,
                       src_anchor=(col_w / 2, col_h), dst_anchor=(260, 0)))
    elems.append(arrow(idg, idg.make("ar_wb_coord"), wb_box, coord_box,
                       src_anchor=(col_w / 2, col_h), dst_anchor=(840, 0)))
    elems.append(arrow(idg, idg.make("ar_sdk_coord"), sdk_box, coord_box,
                       src_anchor=(col_w / 2, col_h), dst_anchor=(1420, 0)))

    err_y = 940
    err_box, err_lbl = labeled_box(idg, "err_render", 60, err_y, 1680, 130,
        "ERROR RENDERING (uniform across all 3 surfaces - per nucleus_cli_spec.md Section 5.4)\n"
        "  [NE2007] NucleusResourceError: Out of memory while processing 'sales.fct_orders' (~5GB).\n"
        "           fix_hint: add a partition filter, increase machine memory, or use compute=databricks.\n"
        "           docs:    nucleus.dev/errors/resource\n"
        "Same NE-code. Same user_message. Same fix_hint. No DuckDB or Dagster classnames anywhere.",
        fill="built", label_size=SIZE_SMALL)
    elems.extend([err_box, err_lbl])

    elems.extend(legend_block(idg, 40, 1110))
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 07 - User journey (30-min beachhead)
# ---------------------------------------------------------------------------


def mk_user_journey() -> dict[str, Any]:
    idg = IdGen("d07")
    elems: list[dict[str, Any]] = []
    elems.extend(title_block(
        idg, 40, 30,
        "30-Minute Beachhead Journey - First BI-Ready Iceberg Table",
        "v0.1 success metric: 5-engineer startup team, MacBooks, git clone -> first BI-ready Iceberg table in <30 min",
    ))
    elems.append(section_label(idg, "journey", 40, 80,
                               "v4.1 Section 1.5 (beachhead) + Section 11 (local-first promise)"))

    steps = [
        ("step1", "1. pip install\nnucleus[core]", "user", "~30s"),
        ("step2", "2. nucleus init\nmy-warehouse", "user", "~5s"),
        ("step3", "3. nucleus up\n(Docker: SeaweedFS + catalog + warehouse)", "wrapped", "~10s"),
        ("step4", "4. edit assets/example.py\n@nucleus.asset def hello(ctx)", "built", "~5min"),
        ("step5", "5. nucleus run hello\nAMA -> pyiceberg -> snapshot", "built", "~15s"),
        ("step6", "6. nucleus query\n'SELECT * FROM hello LIMIT 10'", "user", "~5s"),
        ("step7", "7. nucleus workbench\nopen http://localhost:8765", "user", "~5s"),
        ("step8", "8. (future) point Databricks\nat same Iceberg lake", "wrapped", "0min"),
    ]

    step_w = 200
    step_h = 130
    gap = 40
    row1_y = 180
    row2_y = 380
    step_boxes: list[dict[str, Any]] = []
    for i, (slug, label, fill, t) in enumerate(steps):
        col = i % 4
        row = i // 4
        x = 60 + col * (step_w + gap)
        y = row1_y if row == 0 else row2_y
        b, l = labeled_box(idg, slug, x, y, step_w, step_h, label,
                           fill=fill, label_size=SIZE_SMALL)
        step_boxes.append(b)
        elems.extend([b, l])
        elems.append(text(idg, idg.make(f"{slug}_t"), x + 5, y + step_h + 6,
                          t, size=SIZE_SMALL, color="#1864ab", align="left"))

    for i in range(len(steps) - 1):
        if i == 3:
            elems.append(arrow(idg, idg.make(f"ar_step_{i}_{i+1}"),
                               step_boxes[3], step_boxes[4],
                               src_anchor=(step_w / 2, step_h),
                               dst_anchor=(step_w / 2, 0)))
        else:
            elems.append(arrow(idg, idg.make(f"ar_step_{i}_{i+1}"),
                               step_boxes[i], step_boxes[i + 1]))

    total_box = rect(idg, idg.make("total_box"), 1020, 380, 220, 130, fill="immortal")
    total_lbl = text(idg, idg.make("total_lbl"), 1040, 410,
        "TOTAL\n< 30 min\n(beachhead\npromise met)",
        size=SIZE_LABEL, color="#1864ab", align="left")
    elems.extend([total_box, total_lbl])

    err_y = 600
    err_branch_x = 800
    err_box, err_lbl = labeled_box(idg, "err_branch", err_branch_x - 220, err_y, 480, 110,
        "ERROR BRANCH (any step)\nWrapped exception -> Error Translation -> NucleusError\n"
        "[NE5018] FileExistsError race during nucleus init",
        fill="built", label_size=SIZE_SMALL)
    elems.extend([err_box, err_lbl])
    elems.append(arrow(idg, idg.make("ar_step5_err"), step_boxes[4], err_box,
                       src_anchor=(step_w / 2, step_h),
                       dst_anchor=(220, 0), color="#c92a2a", style="dashed"))
    elems.append(text(idg, idg.make("err_caption"),
                      err_branch_x - 220, err_y + 120,
                      "Same path on any failure: same NE-code, same fix_hint - never a Dagster classname.",
                      size=SIZE_SMALL, color="#c92a2a", align="left"))

    detail_y = 760
    detail_box = rect(idg, idg.make("detail_box"), 40, detail_y, 1700, 220, fill="muted")
    detail_lbl = text(idg, idg.make("detail_lbl"), 54, detail_y + 14,
        "What happens behind the scenes (per v4.1 Section 11.1 + ADR-008 storage):\n"
        "  step 3: docker compose up brings SeaweedFS (default per ADR-008) + Lakekeeper-or-filesystem-catalog + nucleus warehouse;\n"
        "          MinIO is preserved as alt via docker-compose.minio.yml. Health-poll until S3 endpoint responds.\n"
        "  step 4: @nucleus.asset registers the function in an in-process dict; no Dagster import in user code (Constraint #1 + Section 6.5).\n"
        "  step 5: Asset Materialization Adapter validates contract -> acquires advisory lock (P0-2) ->\n"
        "          pyiceberg catalog.commit_table() (ADR-001 atomic) -> emit OpenLineage event ->\n"
        "          append to .nucleus/runs/runs.ndjson -> expire_old_snapshots (P0-3).\n"
        "  step 6: ctx.sql() jinja-resolves {{ ref('hello') }} -> DuckDB iceberg_scan -> Arrow result -> Rich table to terminal.\n"
        "  step 8: Mode 1 graduation - same s3://warehouse + same Iceberg metadata; Databricks reads it natively. Zero migration.",
        size=SIZE_SMALL, color="#212529", align="left")
    elems.extend([detail_box, detail_lbl])

    elems.extend(legend_block(idg, 40, 1010))
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 08 - Composability + Yield-to-Giants
# ---------------------------------------------------------------------------


def mk_composability_yield() -> dict[str, Any]:
    idg = IdGen("d08")
    elems: list[dict[str, Any]] = []
    elems.extend(title_block(
        idg, 40, 30,
        "Composability Constitution + Yield to Giants",
        "Tier 0 immortal | Tier 1 swap-on-demand | Tier 2 wrapped | + 3 modes of integration with cloud giants",
    ))
    elems.append(section_label(idg, "comp", 40, 80,
                               "v4.1 Sections 9 (composability) + 10 (yield to giants) + ADR-002 (positioning)"))

    section_h_top = 580

    section_top = rect(idg, idg.make("sec_top"), 40, 100, 1700, section_h_top,
                       fill="transparent", stroke_width=1, rounded=False)
    section_top_lbl = text(idg, idg.make("sec_top_lbl"), 60, 110,
                           "COMPOSABILITY (v4.1 Section 9.3 - swap interface + smoke tests, full adapter ON-DEMAND)",
                           size=SIZE_SUBTITLE, color="#212529", align="left")
    elems.extend([section_top, section_top_lbl])

    tier0 = [
        ("Apache Arrow", "in-memory columnar"),
        ("Apache Iceberg", "structured tables"),
        ("Apache Parquet", "column file format"),
        ("Lance", "multimodal (v0.5+)"),
        ("S3 API", "object protocol"),
        ("OpenLineage", "lineage protocol"),
        ("OpenTelemetry", "obs protocol"),
    ]
    t0_y = 160
    t0_w = 230
    t0_gap = 10
    t0_total = len(tier0) * t0_w + (len(tier0) - 1) * t0_gap
    t0_start_x = (1700 - t0_total) / 2 + 40
    elems.append(text(idg, idg.make("t0_lbl"), 60, t0_y - 4,
                      "Tier 0 - immortal (never swap)",
                      size=SIZE_BADGE, color="#212529", align="left"))
    for i, (name, sub) in enumerate(tier0):
        x = t0_start_x + i * (t0_w + t0_gap)
        b, l = labeled_box(idg, f"t0_{i}", x, t0_y + 22, t0_w, 90,
                           f"{name}\n{sub}", fill="immortal", label_size=SIZE_SMALL)
        elems.extend([b, l])

    swap_y = 320
    elems.append(text(idg, idg.make("t1_lbl"), 60, swap_y - 4,
                      "Tier 1 - first-class default + clean swap interface (full adapter built ON-DEMAND when trigger fires)",
                      size=SIZE_BADGE, color="#212529", align="left"))
    swaps = [
        ("DuckDB", "DataFusion (Apache, Rust)", "wrapped"),
        ("Polars", "DataFusion DF (Apache)", "wrapped"),
        ("Dagster (hidden)", "nucleus-mini-scheduler (in-house)", "wrapped"),
        ("pyiceberg + Lakekeeper / SqlCatalog", "Apache Polaris (ASF TLP)", "wrapped"),
    ]
    sw_w = 380
    sw_gap = 30
    sw_total = len(swaps) * sw_w + (len(swaps) - 1) * sw_gap
    sw_start_x = (1700 - sw_total) / 2 + 40
    for i, (default, target, fill) in enumerate(swaps):
        x = sw_start_x + i * (sw_w + sw_gap)
        d, l = labeled_box(idg, f"def_{i}", x, swap_y + 22, sw_w / 2 - 20, 90,
                          default, fill=fill, label_size=SIZE_SMALL)
        t, tl = labeled_box(idg, f"swp_{i}", x + sw_w / 2 + 20, swap_y + 22, sw_w / 2 - 20, 90,
                          target, fill="muted", label_size=SIZE_SMALL)
        elems.extend([d, l, t, tl])
        elems.append(line(idg, idg.make(f"swap_line_{i}"),
                          x + sw_w / 2 - 20, swap_y + 22 + 45,
                          x + sw_w / 2 + 20, swap_y + 22 + 45, color="#868e96"))
        elems.append(text(idg, idg.make(f"swap_lbl_{i}"),
                          x + sw_w / 2 - 18, swap_y + 22 + 22,
                          "<-->\nswap\non demand", size=SIZE_SMALL,
                          color="#868e96", align="center", width=42))

    t2_y = 470
    elems.append(text(idg, idg.make("t2_lbl"), 60, t2_y - 4,
                      "Tier 2 - wrapped capabilities (fully replaceable)",
                      size=SIZE_BADGE, color="#212529", align="left"))
    tier2 = [
        ("Connectors\nctx.copy_from / dlt v0.3+",  "Sling / Singer / custom"),
        ("Transformations\nnative ctx.sql + Jinja", "dbt-duckdb / SQLMesh"),
        ("Notebooks\nMarimo (v0.3+)", "Jupyter / none"),
        ("LLM provider router\nLiteLLM", "direct provider SDKs"),
        ("Streaming (v1.5+)\nBenthos / Redpanda", "Kafka native / Flink"),
    ]
    t2_w = 320
    t2_gap = 14
    t2_total = len(tier2) * t2_w + (len(tier2) - 1) * t2_gap
    t2_start_x = (1700 - t2_total) / 2 + 40
    for i, (default, target) in enumerate(tier2):
        x = t2_start_x + i * (t2_w + t2_gap)
        b, l = labeled_box(idg, f"t2_{i}", x, t2_y + 22, t2_w, 80,
                           default, fill="wrapped", label_size=SIZE_SMALL)
        elems.extend([b, l])
        elems.append(text(idg, idg.make(f"t2_swap_{i}"),
                          x + 8, t2_y + 22 + 90,
                          f"swap: {target}",
                          size=SIZE_SMALL, color="#495057", align="left"))

    section_bot_y = 720
    section_bot = rect(idg, idg.make("sec_bot"), 40, section_bot_y, 1700, 360,
                       fill="transparent", stroke_width=1, rounded=False)
    section_bot_lbl = text(idg, idg.make("sec_bot_lbl"), 60, section_bot_y + 10,
        "YIELD TO GIANTS (v4.1 Section 10 - we do NOT compete; we integrate via 3 modes)",
        size=SIZE_SUBTITLE, color="#212529", align="left")
    elems.extend([section_bot, section_bot_lbl])

    nucleus_box, nucleus_lbl = labeled_box(idg, "nuc_lake", 80, section_bot_y + 60, 380, 110,
        "Nucleus Iceberg lake\n(s3://warehouse + catalog)\nsource of truth",
        fill="built", label_size=SIZE_SMALL)
    elems.extend([nucleus_box, nucleus_lbl])

    mode1_y = section_bot_y + 60
    db_box, db_lbl = labeled_box(idg, "mode1_db", 600, mode1_y, 320, 90,
                                  "Databricks", fill="wrapped")
    sf_box, sf_lbl = labeled_box(idg, "mode1_sf", 940, mode1_y, 320, 90,
                                  "Snowflake / Polaris / Trino / R2", fill="wrapped",
                                  label_size=SIZE_SMALL)
    elems.extend([db_box, db_lbl, sf_box, sf_lbl])

    elems.append(arrow(idg, idg.make("ar_mode1_db"), nucleus_box, db_box,
                       src_anchor=(380, 55), dst_anchor=(0, 45), color="#1864ab"))
    elems.append(arrow(idg, idg.make("ar_mode1_sf"), nucleus_box, sf_box,
                       src_anchor=(380, 75), dst_anchor=(0, 65), color="#1864ab"))
    elems.append(text(idg, idg.make("mode1_lbl"), 480, mode1_y + 30,
                      "Mode 1: Iceberg portability\n(zero migration to giants)",
                      size=SIZE_SMALL, color="#1864ab", align="center", width=180))

    mode2_y = section_bot_y + 200
    dispatch_box, dispatch_lbl = labeled_box(idg, "mode2_box", 600, mode2_y, 660, 70,
        "Mode 2: Hybrid compute   @nucleus.sql_asset(compute='databricks')\n"
        "Heavy assets dispatched to Databricks/Snowflake/MotherDuck; result committed back to Iceberg",
        fill="muted", label_size=SIZE_SMALL)
    elems.extend([dispatch_box, dispatch_lbl])
    elems.append(arrow(idg, idg.make("ar_mode2"), nucleus_box, dispatch_box,
                       src_anchor=(380, 90), dst_anchor=(0, 35), color="#1864ab"))

    mode3_y = section_bot_y + 290
    fed_box, fed_lbl = labeled_box(idg, "mode3_box", 600, mode3_y, 660, 50,
        "Mode 3: Federation (v2.0+) - Iceberg REST catalog cross-account",
        fill="muted", label_size=SIZE_SMALL)
    elems.extend([fed_box, fed_lbl])

    note_x = 1320
    note_y = section_bot_y + 60
    note_box = rect(idg, idg.make("note_box"), note_x, note_y, 380, 280, fill="muted")
    note_lbl = text(idg, idg.make("note_lbl"), note_x + 14, note_y + 12,
        "Why this strategy wins:\n"
        "  - acquisition-friendly: giants see\n"
        "    Nucleus as feeder, not threat\n"
        "  - no data lock-in: Iceberg portability\n"
        "    removes the #1 procurement objection\n"
        "  - smaller scope: we don't build\n"
        "    distributed compute\n"
        "  - customer trust: 'if we outgrow you,\n"
        "    we can leave' -> users stay longer",
        size=SIZE_SMALL, color="#212529", align="left")
    elems.extend([note_box, note_lbl])

    elems.extend(legend_block(idg, 40, 1100))
    return _wrap(elems)


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------


README = """# Nucleus Architecture - Excalidraw Diagram Set

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
"""


# ---------------------------------------------------------------------------
# Wrap + write
# ---------------------------------------------------------------------------


def _wrap(elements: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://nucleus-data.io/architecture",
        "elements": elements,
        "appState": {
            "viewBackgroundColor": PALETTE["bg"],
            "gridSize": None,
        },
        "files": {},
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    here = Path(__file__).resolve().parent
    diagrams = [
        ("01_overview.excalidraw", mk_overview),
        ("02_physics.excalidraw", mk_physics),
        ("03_engines.excalidraw", mk_engines),
        ("04_coordination.excalidraw", mk_coordination),
        ("05_intelligence.excalidraw", mk_intelligence),
        ("06_experience.excalidraw", mk_experience),
        ("07_dataflow_user_journey.excalidraw", mk_user_journey),
        ("08_composability_yield_to_giants.excalidraw", mk_composability_yield),
    ]
    for filename, fn in diagrams:
        payload = fn()
        _write(here / filename, payload)
        n_elems = len(payload["elements"])
        size_kb = (here / filename).stat().st_size / 1024
        print(f"  wrote {filename:48s}  {n_elems:>3} elements  {size_kb:>5.1f} KB")
    (here / "README.md").write_text(README, encoding="utf-8")
    print(f"  wrote README.md")


if __name__ == "__main__":
    main()
