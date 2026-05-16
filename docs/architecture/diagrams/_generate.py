"""Deterministic generator for the Nucleus architecture diagram set.

Per founder critique 2026-05-15: the previous generator used a single
"labeled_box + straight_arrow" template across all 8 diagrams. Two consequences:

  1. Arrows routed in straight lines through other rectangles ("overlap")
  2. All 8 diagrams felt like the same drawing repeated 8 times

This rewrite enforces TWO disciplines:

  * **Per-diagram concept analysis.** Every ``mk_*`` function opens with a
    block comment naming (a) the concept the diagram is trying to convey,
    (b) the structural pattern that fits that concept, and (c) the chosen
    visual paradigm. The 8 paradigms are deliberately heterogeneous: layered
    bands (01), tree (02), parallel channels with a bridge band (03),
    two-track flow (04), pipeline + context injection (05), hub-and-spoke
    (06), horizontal timeline (07), tier-stack + mode panels (08).

  * **Arrow discipline.** No arrow ever passes through the bounding box of
    a non-endpoint rectangle. The generator self-checks via
    ``assert_no_arrow_overlap()`` after every diagram is built; the script
    aborts with a precise (arrow_id, rect_id) failure report if any arrow
    crosses an unrelated node. To make compliance practical, the new
    primitive ``elbow_arrow()`` accepts explicit waypoints that route the
    arrow around obstacles via right-angle bends.

Run from the repo root::

    python docs/architecture/diagrams/_generate.py

Each diagram is a self-contained scene authored in one ``mk_*`` function;
they share only the helper toolbox at the top of this file. Diagram authoring
should stick to ASCII characters in element text per the brief
(``check_vocabulary.py`` scans these files).

Excalidraw JSON shape reference:
    https://github.com/excalidraw/excalidraw/blob/master/dev-docs/docs/codebase/json-schema.mdx
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Palette + constants (UNCHANGED from the previous pass; only paradigms changed)
# ---------------------------------------------------------------------------

PALETTE: dict[str, str] = {
    "stroke": "#1e1e1e",
    "wrapped": "#a5d8ff",  # light blue: DuckDB / Polars / Dagster / dlt / pyiceberg / LiteLLM
    "built": "#ffc9c9",  # light red: ctx SDK / AMA / Error Translation / CLI / Workbench / Copilot
    "storage": "#b2f2bb",  # light green: Iceberg / Parquet / S3 / MinIO / SeaweedFS
    "user": "#ffec99",  # light yellow: User personas / surfaces seen by humans
    "immortal": "#d0bfff",  # light purple: Tier 0 substrate (Arrow / Iceberg / Parquet / Lance)
    "muted": "#dee2e6",  # neutral grey for deferred / faded items
    "transparent": "transparent",
    "bg": "#ffffff",
}

FONT_BODY = 5  # Excalidraw "Hand-drawn" font index; matches existing repo files
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
# Geometry helpers
# ---------------------------------------------------------------------------


def box_anchor(box: dict[str, Any], side: str, frac: float = 0.5) -> tuple[float, float]:
    """Absolute (x, y) anchor on a rectangle's edge.

    side in {top, right, bottom, left}; frac is 0..1 along that edge."""
    x, y, w, h = box["x"], box["y"], box["width"], box["height"]
    if side == "top":
        return (x + w * frac, y)
    if side == "right":
        return (x + w, y + h * frac)
    if side == "bottom":
        return (x + w * frac, y + h)
    if side == "left":
        return (x, y + h * frac)
    raise ValueError(f"unknown side: {side!r}")


def _segment_crosses_rect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    rect_xywh: tuple[float, float, float, float],
    margin: float = 6.0,
) -> bool:
    """True if segment p1->p2 enters the inset rect (margin shrinks rect on all sides).

    Uses Liang-Barsky line clipping. Pure tangent / corner touches are excluded
    by the margin: if you want an arrow to graze a node's edge, set the segment
    endpoints exactly on that edge (within margin) and the test will pass."""
    rx, ry, rw, rh = rect_xywh
    x_min = rx + margin
    y_min = ry + margin
    x_max = rx + rw - margin
    y_max = ry + rh - margin
    if x_max <= x_min or y_max <= y_min:
        return False
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1
    p = [-dx, dx, -dy, dy]
    q = [x1 - x_min, x_max - x1, y1 - y_min, y_max - y1]
    u1, u2 = 0.0, 1.0
    for i in range(4):
        if p[i] == 0:
            if q[i] < 0:
                return False
        else:
            t = q[i] / p[i]
            if p[i] < 0:
                if t > u2:
                    return False
                u1 = max(u1, t)
            else:
                if t < u1:
                    return False
                u2 = min(u2, t)
    return u1 < u2


def assert_no_arrow_overlap(
    diagram_name: str,
    elements: list[dict[str, Any]],
    allow_pairs: set[tuple[str, str]] | None = None,
) -> None:
    """Walk every arrow segment; assert it does not enter any non-endpoint rect.

    A rect is exempt if (a) it is the start- or end-binding target of the arrow,
    (b) the (arrow_id, rect_id) pair is in ``allow_pairs``, or (c) the rect is
    a low-opacity "background band" (opacity < 100 AND the rect is wider than
    400 px). Raises AssertionError listing every offending pair."""
    issues: list[str] = []
    rects = [e for e in elements if e["type"] == "rectangle"]
    arrows = [e for e in elements if e["type"] == "arrow"]
    allow_pairs = allow_pairs or set()
    for arr in arrows:
        ax, ay = arr["x"], arr["y"]
        pts = arr.get("points", [])
        if len(pts) < 2:
            continue
        sb = arr.get("startBinding")
        eb = arr.get("endBinding")
        bound_ids = {b["elementId"] for b in (sb, eb) if b}
        for i in range(len(pts) - 1):
            p1 = (ax + pts[i][0], ay + pts[i][1])
            p2 = (ax + pts[i + 1][0], ay + pts[i + 1][1])
            for r in rects:
                if r["id"] in bound_ids:
                    continue
                if r.get("opacity", 100) < 100 and r["width"] >= 400:
                    continue
                if (arr["id"], r["id"]) in allow_pairs:
                    continue
                if _segment_crosses_rect(
                    p1, p2, (r["x"], r["y"], r["width"], r["height"]), margin=4.0
                ):
                    issues.append(
                        f"  arrow {arr['id']!s} segment {i} crosses rect {r['id']!s} "
                        f"at ({r['x']:.0f},{r['y']:.0f}, {r['width']:.0f}x{r['height']:.0f})"
                    )
    if issues:
        msg = (
            f"\n[{diagram_name}] arrow-overlap discipline violated "
            f"({len(issues)} crossings):\n" + "\n".join(issues)
        )
        raise AssertionError(msg)


# ---------------------------------------------------------------------------
# Element builders (rect / ellipse / text / labeled_box / line) — UNCHANGED
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
    opacity: int = 100,
) -> dict[str, Any]:
    el = _base_props(idg, eid) | {
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "backgroundColor": PALETTE.get(fill, fill),
        "strokeColor": PALETTE.get(stroke, stroke),
        "strokeWidth": stroke_width,
        "opacity": opacity,
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
# NEW PRIMITIVE: elbow_arrow
# ---------------------------------------------------------------------------


def elbow_arrow(
    idg: IdGen,
    eid: str,
    *,
    start: tuple[float, float],
    end: tuple[float, float],
    via: list[tuple[float, float]] | tuple[tuple[float, float], ...] = (),
    color: str = "stroke",
    style: str = "solid",
    stroke_width: int = 2,
    end_arrowhead: str | None = "arrow",
    start_arrowhead: str | None = None,
    label: str | None = None,
    label_offset: tuple[int, int] = (8, -16),
    bind_start: dict[str, Any] | None = None,
    bind_end: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Multi-segment arrow that routes through explicit waypoints.

    ``start`` and ``end`` are absolute scene coordinates; ``via`` is a list of
    intermediate absolute waypoints. The arrow is drawn ``start -> via[0] ->
    via[1] -> ... -> end``. Pass an empty ``via`` to get a pure straight
    arrow (still uses this primitive's no-binding variant by default).

    Bindings are OPTIONAL. Pass ``bind_start=src_box`` to make Excalidraw
    keep the start point glued to the source rectangle if the user moves it
    interactively; the via points stay fixed.

    Returns ``[arrow]`` or ``[arrow, label_text_element]`` if ``label`` is set.
    """
    sx, sy = start
    ex, ey = end
    via_list = [tuple(v) for v in via]
    abs_pts = [(sx, sy), *via_list, (ex, ey)]
    rel_pts = [[ax - sx, ay - sy] for ax, ay in abs_pts]
    xs = [p[0] for p in rel_pts]
    ys = [p[1] for p in rel_pts]
    el = _base_props(idg, eid) | {
        "type": "arrow",
        "x": sx,
        "y": sy,
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
        "strokeColor": PALETTE.get(color, color),
        "strokeStyle": style,
        "strokeWidth": stroke_width,
        "points": rel_pts,
        "lastCommittedPoint": None,
        "startBinding": (
            {"elementId": bind_start["id"], "focus": 0, "gap": 4}
            if bind_start is not None
            else None
        ),
        "endBinding": (
            {"elementId": bind_end["id"], "focus": 0, "gap": 4} if bind_end is not None else None
        ),
        "startArrowhead": start_arrowhead,
        "endArrowhead": end_arrowhead,
        "elbowed": False,
    }
    el["roundness"] = None
    if bind_start is not None:
        bind_start.setdefault("boundElements", []).append({"id": eid, "type": "arrow"})
    if bind_end is not None:
        bind_end.setdefault("boundElements", []).append({"id": eid, "type": "arrow"})
    out = [el]
    if label:
        # Place label at the midpoint of the longest segment (so it lands on the
        # most visually obvious portion of the route, not on a tiny stub).
        best_len = -1.0
        best_mid = ((sx + ex) / 2, (sy + ey) / 2)
        for i in range(len(abs_pts) - 1):
            (x1, y1), (x2, y2) = abs_pts[i], abs_pts[i + 1]
            seg_len = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            if seg_len > best_len:
                best_len = seg_len
                best_mid = ((x1 + x2) / 2, (y1 + y2) / 2)
        lbl_x = best_mid[0] + label_offset[0]
        lbl_y = best_mid[1] + label_offset[1]
        out.append(
            text(
                idg,
                idg.make(f"alabel_{eid.split('_', 1)[-1]}"),
                lbl_x,
                lbl_y,
                label,
                size=SIZE_SMALL,
                color="#495057",
                align="left",
            )
        )
    return out


# ---------------------------------------------------------------------------
# Common scene fragments (title, section ref, badges, legend, background bands)
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


def badge(
    idg: IdGen,
    slug: str,
    x: float,
    y: float,
    w: float,
    h: float,
    body: str,
    *,
    fill: str = "immortal",
) -> list[dict[str, Any]]:
    """Small colored badge with one or two short lines (e.g. 'NO JVM' / 'WRAP NOT BUILD')."""
    b = rect(idg, idg.make(f"badge_{slug}"), x, y, w, h, fill=fill, stroke_width=1)
    lbl = text(
        idg,
        idg.make(f"badgelbl_{slug}"),
        x + 14,
        y + max(8, (h - SIZE_BADGE * 1.4 * body.count("\n") - SIZE_BADGE) / 2),
        body,
        size=SIZE_BADGE,
        color="stroke",
        align="left",
    )
    return [b, lbl]


def background_band(
    idg: IdGen,
    slug: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = "muted",
    opacity: int = 35,
    label: str | None = None,
) -> list[dict[str, Any]]:
    """Faded large rounded rectangle used to visually group related nodes.

    Background bands are exempt from the arrow-overlap check because their
    purpose is to underlay a region of the canvas; arrows are *expected* to
    pass over them. They are detected by the check via opacity < 100 AND
    width >= 400 px."""
    b = rect(
        idg,
        idg.make(f"bgband_{slug}"),
        x,
        y,
        w,
        h,
        fill=fill,
        stroke_width=1,
        rounded=True,
        opacity=opacity,
    )
    out = [b]
    if label:
        lbl = text(
            idg,
            idg.make(f"bgband_lbl_{slug}"),
            x + 14,
            y + 10,
            label,
            size=SIZE_SMALL,
            color="#495057",
            align="left",
        )
        out.append(lbl)
    return out


def legend_block(idg: IdGen, x: float, y: float) -> list[dict[str, Any]]:
    items = [
        ("wrapped", "wrapped OSS (DuckDB / Polars / Dagster / pyiceberg / dlt / LiteLLM)"),
        (
            "built",
            "built by Nucleus (ctx SDK / AMA / Error Translation / CLI / Workbench / Copilot)",
        ),
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
#
# CONCEPT:    "see the whole 5-layer stack + user + storage + graduation in
#             one frame" (v4.1 Section 3.1 / 3.2 layered architecture).
#
# STRUCTURE:  This is the ONE diagram where the content IS literally a stack
#             of equal-priority horizontal layers. Other diagrams that look
#             like layered bands are imposters; this one is the real thing.
#
# PARADIGM:   Layered horizontal bands. 5 bands stacked vertically with a
#             ~50 px gap between bands so that adjacent-band arrows have a
#             dedicated routing lane. Persona ellipse sits ABOVE the stack,
#             yield-to-giants box hangs off the right edge to convey
#             "graduation = exit out of the local frame", with its connector
#             arrow drawn off the right side of the Iceberg row (clear of
#             every other band).
# ---------------------------------------------------------------------------


def mk_overview() -> dict[str, Any]:
    idg = IdGen("d01")
    elems: list[dict[str, Any]] = []

    elems.extend(
        title_block(
            idg,
            40,
            30,
            "Nucleus - Full Stack Overview",
            "Five horizontal layers; persona on top, storage at the bottom, graduation arrow on the right",
        )
    )
    elems.append(section_label(idg, "overview", 40, 80, "v4.1 Section 3.1 (locked numbering)"))

    persona_x, persona_y = 540, 110
    persona = ellipse(idg, idg.make("persona"), persona_x, persona_y, 720, 60, fill="user")
    persona_lbl = text(
        idg,
        idg.make("persona_lbl"),
        persona_x + 30,
        persona_y + 18,
        "5-engineer startup data team (greenfield, 100GB-5TB, MacBooks)",
        size=SIZE_LABEL,
        align="left",
    )
    elems.extend([persona, persona_lbl])

    # Five band slots with explicit gaps so arrows have a routing lane in between.
    band_x = 80
    band_w = 1500
    band_h = 130
    gap = 56
    band_y0 = 220
    bands_meta = [
        ("L4_EXPERIENCE", "L4  EXPERIENCE  (CLI + Workbench + ctx SDK + Marimo)", "user"),
        ("L3_INTELLIGENCE", "L3  INTELLIGENCE  (AI Copilot v0.2+, ctx.agent v0.5+)", "built"),
        (
            "L2_COORDINATION",
            "L2  COORDINATION  (AMA + Error Translation + Run Ledger + Locks + Daemon - the wrap-not-build crown jewel)",
            "built",
        ),
        (
            "L1_ENGINES",
            "L1  ENGINES  (DuckDB + Polars + pyiceberg + dlt + LiteLLM ; all wrapped, all swappable)",
            "wrapped",
        ),
        (
            "L0_PHYSICS",
            "L0  PHYSICS  (Apache Arrow + Iceberg + Parquet + S3 / MinIO / SeaweedFS + OpenLineage / OpenTelemetry)",
            "immortal",
        ),
    ]
    band_rects: dict[str, dict[str, Any]] = {}
    for i, (slug, label_text, fill) in enumerate(bands_meta):
        y = band_y0 + i * (band_h + gap)
        b = rect(
            idg, idg.make(f"band_{slug}"), band_x, y, band_w, band_h, fill=fill, stroke_width=2
        )
        band_rects[slug] = b
        elems.append(b)
        elems.append(
            text(
                idg,
                idg.make(f"bandlbl_{slug}"),
                band_x + 22,
                y + 16,
                label_text,
                size=SIZE_BADGE,
                color="#212529",
                align="left",
            )
        )

    # Each band gets a short bullet line below the title to anchor the content
    band_bullets = {
        "L4_EXPERIENCE": "init / up / run / ingest / query / chat / list / runs / schedule / workbench   |   FastAPI + React app   |   @nucleus.asset / @nucleus.check / ctx.sql / ctx.copy_from",
        "L3_INTELLIGENCE": "Project context (4 KB cap, 5 redactions per ADR-011)   |   LiteLLM router (Anthropic / OpenAI / Azure / Ollama)   |   Token budget guard (NE5012)",
        "L2_COORDINATION": "AMA (~500 LOC) wraps Dagster   |   Error Translation Layer (24 NE-codes)   |   Run Ledger NDJSON   |   Advisory locks (NE3008)   |   Scheduling daemon (cron + sensors)",
        "L1_ENGINES": "DuckDB <-> DataFusion   |   Polars <-> DataFusion DF   |   pyiceberg <-> iceberg-rust   |   dlt <-> Sling   |   LiteLLM <-> direct provider SDKs",
        "L0_PHYSICS": "Iceberg metadata.json + manifest list + manifest + Parquet data   |   S3 API substrate   |   OpenLineage events emitted per materialization",
    }
    for slug, bullet in band_bullets.items():
        b = band_rects[slug]
        elems.append(
            text(
                idg,
                idg.make(f"bandbody_{slug}"),
                b["x"] + 22,
                b["y"] + 56,
                bullet,
                size=SIZE_SMALL,
                color="#212529",
                align="left",
            )
        )

    # Adjacent-band arrows route in the LEFT gap lane (x ~= 40-70). The arrow
    # leaves each band on its left edge, drops into the gap below, and enters
    # the next band on its left edge. Zero overlap with the band labels.
    arrows_left_lane_x = 50
    for i in range(len(bands_meta) - 1):
        upper = band_rects[bands_meta[i][0]]
        lower = band_rects[bands_meta[i + 1][0]]
        start = box_anchor(upper, "left", frac=0.7)
        end = box_anchor(lower, "left", frac=0.3)
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_band_{i}"),
                start=start,
                end=end,
                via=[(arrows_left_lane_x, start[1]), (arrows_left_lane_x, end[1])],
                color="#1864ab",
            )
        )

    # Persona connects to the top experience band via a short straight arrow on
    # the centre line - clear of all band labels.
    exp_band = band_rects["L4_EXPERIENCE"]
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_persona_exp"),
            start=(persona_x + 360, persona_y + 60),
            end=(exp_band["x"] + exp_band["width"] / 2, exp_band["y"]),
            color="#5f3dc4",
        )
    )

    # Yield-to-giants box hangs off the right of the L0 PHYSICS band; the arrow
    # exits the right side of L0 PHYSICS and enters the giants box on its left
    # - both anchors are on the right side of the canvas, no obstructions.
    giants_box, giants_lbl = labeled_box(
        idg,
        "giants",
        band_x + band_w + 60,
        band_y0 + 4 * (band_h + gap) + 20,
        320,
        90,
        "YIELD TO GIANTS\nDatabricks / Snowflake / Polaris / Trino / R2\n(Iceberg portability, zero migration)",
        fill="wrapped",
        label_size=SIZE_SMALL,
    )
    elems.extend([giants_box, giants_lbl])
    physics_band = band_rects["L0_PHYSICS"]
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_physics_giants"),
            start=box_anchor(physics_band, "right", frac=0.5),
            end=box_anchor(giants_box, "left", frac=0.5),
            color="#1864ab",
            label="Mode 1\ngraduation",
            label_offset=(8, -28),
        )
    )

    elems.extend(legend_block(idg, 40, band_y0 + 5 * (band_h + gap) + 40))
    assert_no_arrow_overlap("01_overview", elems)
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 02 - Physics
# ---------------------------------------------------------------------------
#
# CONCEPT:    "how an Iceberg table is physically stored". Iceberg metadata
#             is fundamentally a NESTED reference chain: catalog points to
#             metadata.json, which points to a manifest list, which points
#             to manifests, which point to Parquet files on S3.
#
# STRUCTURE:  This is a tree (single-parent chain). It also has a SECONDARY
#             axis: snapshots evolve over time (S1 -> S2 -> S3) where each
#             new snapshot adds a new metadata.json + manifest list while
#             reusing prior data files. So we draw the tree on the LEFT and
#             a horizontal snapshot timeline on the RIGHT, sharing the
#             metadata.json node visually.
#
# PARADIGM:   Tree (top-down chain) on the left + horizontal snapshot timeline
#             on the right + an S3/MinIO substrate band running underneath
#             both, anchoring the "all of this lives as objects on S3" idea.
# ---------------------------------------------------------------------------


def mk_physics() -> dict[str, Any]:
    idg = IdGen("d02")
    elems: list[dict[str, Any]] = []

    elems.extend(
        title_block(
            idg,
            40,
            30,
            "Layer 0 - Physics: Iceberg Metadata Tree + Snapshot Evolution",
            "Catalog -> metadata.json -> manifest list -> manifests -> Parquet files; new snapshot = new metadata head, same data files",
        )
    )
    elems.append(
        section_label(idg, "physics", 40, 80, "v4.1 Section 4 + ADR-008 (storage substrate)")
    )

    elems.extend(
        badge(
            idg,
            "tier0",
            1340,
            40,
            360,
            60,
            "Tier 0 immortal: never swap;\nApache / CNCF / LF-backed standards.",
            fill="immortal",
        )
    )

    # --- LEFT SIDE: vertical metadata tree -----------------------------------
    tree_x = 220
    tree_w = 360
    nodes_meta = [
        (
            "catalog",
            130,
            "pyiceberg Catalog\n(SqlCatalog v0.1 / RestCatalog v0.3+)\nholds the latest metadata pointer",
            "wrapped",
        ),
        ("metadata", 280, "metadata.json\nschema, partition spec, snapshot list", "immortal"),
        (
            "manifest_list",
            430,
            "manifest list (.avro)\npointers to per-snapshot manifests",
            "immortal",
        ),
        ("manifest", 580, "manifest file (.avro)\ndata file paths + column statistics", "immortal"),
        ("data", 730, "Parquet data files\n(columnar, immutable, S3 objects)", "immortal"),
    ]
    tree_boxes: dict[str, dict[str, Any]] = {}
    for slug, y, label_text, fill in nodes_meta:
        b, l = labeled_box(
            idg,
            f"tree_{slug}",
            tree_x,
            y,
            tree_w,
            100,
            label_text,
            fill=fill,
            label_size=SIZE_SMALL,
        )
        tree_boxes[slug] = b
        elems.extend([b, l])

    # Straight downward arrows between adjacent tree nodes (no obstructions).
    chain = ["catalog", "metadata", "manifest_list", "manifest", "data"]
    for i in range(len(chain) - 1):
        upper = tree_boxes[chain[i]]
        lower = tree_boxes[chain[i + 1]]
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_chain_{chain[i]}"),
                start=box_anchor(upper, "bottom", frac=0.5),
                end=box_anchor(lower, "top", frac=0.5),
                color="#1864ab",
            )
        )

    # --- RIGHT SIDE: snapshot timeline (S1 -> S2 -> S3) ----------------------
    snap_y = 240
    snap_w = 200
    snap_h = 100
    snap_gap = 60
    snap_xs = [700, 700 + snap_w + snap_gap, 700 + 2 * (snap_w + snap_gap)]
    snaps: list[dict[str, Any]] = []
    for i, sx in enumerate(snap_xs):
        b, l = labeled_box(
            idg,
            f"snap_{i + 1}",
            sx,
            snap_y,
            snap_w,
            snap_h,
            f"snapshot-{i + 1}\n@ t{i + 1}\n{['initial load', '+1 commit', '+1 commit'][i]}",
            fill="immortal",
            label_size=SIZE_SMALL,
        )
        snaps.append(b)
        elems.extend([b, l])
    for i in range(2):
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_snap_{i + 1}"),
                start=box_anchor(snaps[i], "right", frac=0.5),
                end=box_anchor(snaps[i + 1], "left", frac=0.5),
                color="#2b8a3e",
                label="atomic\ncatalog\ncommit",
                label_offset=(0, -36),
            )
        )

    # The metadata.json node is the visual hinge between the tree and the
    # snapshot timeline. Rather than draw 3 advisory arrows back into the
    # metadata box (which would have to cross either the tree or the snapshot
    # row, both of which would violate the overlap discipline), we use a
    # text note: the conceptual link is clear from the labels.
    elems.append(
        text(
            idg,
            idg.make("snap_md_note"),
            700,
            snap_y + snap_h + 30,
            "each snapshot is a NEW metadata.json head + a NEW manifest list;\n"
            "the underlying Parquet data files are REUSED across snapshots (immutable).",
            size=SIZE_SMALL,
            color="#495057",
            align="left",
        )
    )

    # --- BOTTOM: write-path strip + S3 substrate band -----------------------
    write_box, write_lbl = labeled_box(
        idg,
        "write_flow",
        220,
        870,
        880,
        80,
        "WRITE PATH (per snapshot, all-or-nothing per ADR-001)\n"
        "1) write Parquet data file -> 2) write manifest -> 3) write manifest list -> 4) catalog atomic commit -> snapshot+1",
        fill="muted",
        label_size=SIZE_SMALL,
    )
    elems.extend([write_box, write_lbl])

    s3_box, s3_lbl = labeled_box(
        idg,
        "s3",
        220,
        980,
        880,
        110,
        "S3 / MinIO / SeaweedFS  (S3-API substrate)\n"
        "Every metadata.avro / metadata.json / manifest / Parquet file lives here as an object",
        fill="storage",
        label_size=SIZE_SMALL,
    )
    elems.extend([s3_box, s3_lbl])
    # Route data -> S3 via the LEFT lane (x=180) so the arrow goes around the
    # write_flow strip rather than through it. Lane is at x=180, well clear of
    # the tree's left edge (tree_x=220).
    data_box = tree_boxes["data"]
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_data_s3"),
            start=(data_box["x"], data_box["y"] + data_box["height"] / 2),
            end=box_anchor(s3_box, "left", frac=0.5),
            via=[
                (180, data_box["y"] + data_box["height"] / 2),
                (180, s3_box["y"] + s3_box["height"] / 2),
            ],
            color="#2b8a3e",
            label="all files\n= S3 objects",
            label_offset=(-72, -10),
        )
    )

    # --- Lance sidebar (v0.5+) ---------------------------------------------
    lance_box, lance_lbl = labeled_box(
        idg,
        "lance",
        1180,
        870,
        360,
        110,
        "Lance (v0.5+)\nmultimodal + vector tables (images,\nembeddings, tensors)",
        fill="muted",
        label_size=SIZE_SMALL,
    )
    elems.extend([lance_box, lance_lbl])
    elems.append(
        text(
            idg,
            idg.make("lance_note"),
            1180,
            990,
            "Lance lives next to Iceberg, NOT on top of it.\nDifferent table format, same S3 substrate.",
            size=SIZE_SMALL,
            color="#495057",
            align="left",
        )
    )

    # Observability protocols strip (Tier 0 standard)
    proto_box, proto_lbl = labeled_box(
        idg,
        "proto",
        220,
        1110,
        1320,
        70,
        "OBSERVABILITY PROTOCOLS (Tier 0)   |   "
        "OpenLineage events emitted per materialization   |   OpenTelemetry traces / metrics / logs",
        fill="immortal",
        label_size=SIZE_SMALL,
    )
    elems.extend([proto_box, proto_lbl])

    elems.extend(legend_block(idg, 40, 1110))
    assert_no_arrow_overlap("02_physics", elems)
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 03 - Engines
# ---------------------------------------------------------------------------
#
# CONCEPT:    "the 5 wrapped engines coexist as parallel components, bridged
#             by Apache Arrow zero-copy IPC". The story is composability:
#             every engine is replaceable, and they all speak the same
#             columnar IPC.
#
# STRUCTURE:  Five peer columns + one cross-cutting bridge band. Each column
#             has the same internal shape (engine box + swap target box +
#             dashed swap connector); the bridge is a thick horizontal band
#             that the columns "plug into". This visually equalizes the 5
#             engines and emphasizes the bridge as the lateral connector.
#
# PARADIGM:   Parallel channels (5 vertical columns) + horizontal Apache
#             Arrow bridge band crossing all columns + corner badges
#             (NO JVM top-left, WRAP NOT BUILD top-right).
# ---------------------------------------------------------------------------


def mk_engines() -> dict[str, Any]:
    idg = IdGen("d03")
    elems: list[dict[str, Any]] = []

    elems.extend(
        title_block(
            idg,
            40,
            30,
            "Layer 1 - Engines: Wrap, Not Build",
            "Five wrapped engines plug into one Apache Arrow zero-copy bridge; each has a swap target",
        )
    )
    elems.append(
        section_label(
            idg,
            "engines",
            40,
            80,
            "v4.1 Section 5 + Hard Constraints #1 and #4 + Composability Constitution",
        )
    )

    # Two corner badges drive the message before the eye reaches the columns.
    elems.extend(
        badge(idg, "no_jvm", 40, 110, 280, 60, "NO JVM\nin the always-on hot path", fill="immortal")
    )
    elems.extend(
        badge(
            idg,
            "wrap",
            1420,
            110,
            320,
            60,
            "WRAP NOT BUILD\n5 engines, 0 forks, 0 patches",
            fill="immortal",
        )
    )

    # --- 5 parallel engine columns ------------------------------------------
    engines = [
        ("duckdb", "DuckDB", "C++ / MIT", "iceberg_scan + httpfs", "DataFusion (Apache, Rust)"),
        ("polars", "Polars", "Rust / MIT", "Lazy + Eager + streaming", "DataFusion DF (Apache)"),
        (
            "pyiceberg",
            "pyiceberg",
            "Python / Apache 2",
            "append / overwrite / expire",
            "iceberg-rust / iceberg-go",
        ),
        ("dlt", "dlt", "Python / Apache 2", "100+ source connectors", "Sling / Singer / custom"),
        (
            "litellm",
            "LiteLLM",
            "Python / MIT",
            "OpenAI / Anthropic / Azure / Ollama",
            "direct provider SDKs",
        ),
    ]
    col_w = 300
    col_gap = 36
    n = len(engines)
    total_w = n * col_w + (n - 1) * col_gap
    start_x = (1800 - total_w) / 2
    engine_y = 220
    engine_h = 130
    swap_y = engine_y + engine_h + 70
    swap_h = 90

    engine_boxes: dict[str, dict[str, Any]] = {}
    swap_boxes: dict[str, dict[str, Any]] = {}
    for i, (slug, name, lic, cap, swap) in enumerate(engines):
        cx = start_x + i * (col_w + col_gap)
        eb, el_lbl = labeled_box(
            idg,
            f"en_{slug}",
            cx,
            engine_y,
            col_w,
            engine_h,
            f"{name}\n{lic}\n{cap}",
            fill="wrapped",
            label_size=SIZE_SMALL,
        )
        engine_boxes[slug] = eb
        elems.extend([eb, el_lbl])
        sb, sb_lbl = labeled_box(
            idg,
            f"swap_{slug}",
            cx + 30,
            swap_y,
            col_w - 60,
            swap_h,
            f"swap target:\n{swap}",
            fill="muted",
            label_size=SIZE_SMALL,
        )
        swap_boxes[slug] = sb
        elems.extend([sb, sb_lbl])
        # Dashed downward swap connector with explicit "<-->" symbol annotation
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_swap_{slug}"),
                start=box_anchor(eb, "bottom", frac=0.5),
                end=box_anchor(sb, "top", frac=0.5),
                color="#868e96",
                style="dashed",
                end_arrowhead="arrow",
                start_arrowhead="arrow",
                label="<-->\nswap on demand",
                label_offset=(-44, -32),
            )
        )

    # --- Apache Arrow zero-copy bridge band ---------------------------------
    bridge_y = swap_y + swap_h + 60
    bridge_box, bridge_lbl = labeled_box(
        idg,
        "arrow_bridge",
        start_x,
        bridge_y,
        total_w,
        110,
        "Apache Arrow  (Tier 0 immortal)\n"
        "zero-copy columnar IPC bridge - DuckDB, Polars, pyiceberg, LiteLLM all speak Arrow natively",
        fill="immortal",
        label_size=SIZE_SMALL,
    )
    elems.extend([bridge_box, bridge_lbl])
    # Each engine gets a vertical "plug" arrow into the bridge from underneath
    # the swap box - the swap box is OFFSET inward (cx+30 .. cx+col_w-30) so
    # a vertical arrow at the column edge (cx + 5 or cx + col_w - 5) is clear.
    plug_x_offsets = [col_w * 0.18, col_w * 0.82]  # left and right of column
    for i, (slug, *_rest) in enumerate(engines):
        cx = start_x + i * (col_w + col_gap)
        sb = swap_boxes[slug]
        plug_x = cx + plug_x_offsets[0]
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_plug_{slug}"),
                start=(plug_x, sb["y"] + sb["height"]),
                end=(plug_x, bridge_y),
                color="#0b7285",
            )
        )

    # --- Iceberg substrate band underneath the bridge -----------------------
    iceberg_y = bridge_y + 130 + 50
    iceberg_box, iceberg_lbl = labeled_box(
        idg,
        "iceberg_strip",
        start_x,
        iceberg_y,
        total_w,
        90,
        "Apache Iceberg  (Tier 0 immortal)\n"
        "structured table format - written by pyiceberg, read by DuckDB iceberg_scan",
        fill="immortal",
        label_size=SIZE_SMALL,
    )
    elems.extend([iceberg_box, iceberg_lbl])
    # The bridge -> Iceberg vertical connection lives at the centre column -
    # explicitly the pyiceberg column - so it visually says "pyiceberg writes to
    # Iceberg via the Arrow bridge".
    pyice_eb = engine_boxes["pyiceberg"]
    pyice_x = pyice_eb["x"] + pyice_eb["width"] / 2
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_bridge_iceberg"),
            start=(pyice_x, bridge_y + 110),
            end=(pyice_x, iceberg_y),
            color="#1864ab",
            label="commit",
            label_offset=(8, -22),
        )
    )

    # --- Discipline footer (rules of engagement) ----------------------------
    rules_y = iceberg_y + 110 + 30
    rules_box = rect(idg, idg.make("rules_box"), start_x, rules_y, total_w, 130, fill="muted")
    rules_lbl = text(
        idg,
        idg.make("rules_lbl"),
        start_x + 14,
        rules_y + 14,
        "Wrap-not-build discipline (v4.1 Section 5):\n"
        " 1. Read official docs before integration (AGENTS.md Section 11.12)\n"
        " 2. Exact-pin in pyproject.toml (Constraint #11): duckdb==1.1.3, polars==1.18.0, pyiceberg==0.11.1, dagster==1.9.5, litellm==1.83.14\n"
        " 3. One-component-per-PR upgrades; major versions require an ADR\n"
        " 4. Each Tier 1 engine: clean swap interface + 5-10 smoke tests in CI; full adapter built ON-DEMAND (Composability Tax avoided)",
        size=SIZE_SMALL,
        color="#212529",
        align="left",
    )
    elems.extend([rules_box, rules_lbl])

    elems.extend(legend_block(idg, 40, rules_y + 150))
    assert_no_arrow_overlap("03_engines", elems)
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 04 - Coordination
# ---------------------------------------------------------------------------
#
# CONCEPT:    "every nucleus run goes through TWO paths: a success path that
#             ends in an Iceberg snapshot, and an error path that translates
#             every wrapped exception into a typed NucleusError. Both paths
#             converge on the AMA - the wrap-not-build crown jewel."
#
# STRUCTURE:  Two parallel horizontal flows that share the AMA + Error
#             Translator as visual centres. The success path on top, the
#             error path on bottom. A dashed cross-track elbow shows how an
#             exception during materialization is caught and routed into
#             the error track.
#
# PARADIGM:   Two-track horizontal flow (success on top, error on bottom)
#             with a side panel for cross-cutting concerns (locks, daemon,
#             expire_snapshots, memory_limit) on the right.
# ---------------------------------------------------------------------------


def mk_coordination() -> dict[str, Any]:
    idg = IdGen("d04")
    elems: list[dict[str, Any]] = []

    elems.extend(
        title_block(
            idg,
            40,
            30,
            "Layer 2 - Coordination: AMA + Error Translation Layer",
            "Two tracks share AMA: success ends in an Iceberg snapshot; failure ends in a typed NucleusError",
        )
    )
    elems.append(
        section_label(
            idg,
            "coord",
            40,
            80,
            "v4.1 Sections 6.2 (AMA) + 6.4 (Error Translation, mandatory release blocker) + 6.5 (replaceability)",
        )
    )

    # --- TOP TRACK: success path --------------------------------------------
    top_y = 180
    top_h = 80
    bg_top = background_band(
        idg,
        "track_top",
        60,
        top_y - 30,
        1490,
        top_h + 60,
        fill="storage",
        opacity=18,
        label="SUCCESS TRACK   nucleus run -> AMA -> commit -> ledger",
    )
    elems.extend(bg_top)
    success_steps = [
        ("user_call", 90, "nucleus run\n(or ctx SDK)", "user", 180),
        ("ama", 330, "ASSET MATERIALIZATION\nADAPTER (~500 LOC)", "built", 260),
        ("asset_fn", 650, "asset function\n(user code body)", "user", 180),
        ("pyice", 870, "pyiceberg\n.commit_table()", "wrapped", 200),
        ("snapshot", 1110, "Iceberg snapshot\nCOMMITTED", "immortal", 200),
        ("ledger", 1340, "Run Ledger\nappend NDJSON", "built", 180),
    ]
    success_boxes: dict[str, dict[str, Any]] = {}
    for slug, sx, label_text, fill, w in success_steps:
        h = 100 if slug == "ama" else top_h
        y = top_y - 12 if slug == "ama" else top_y
        b, l = labeled_box(
            idg, f"top_{slug}", sx, y, w, h, label_text, fill=fill, label_size=SIZE_SMALL
        )
        success_boxes[slug] = b
        elems.extend([b, l])
    # Straight horizontal arrows along the success track (boxes are aligned, no overlap risk)
    pairs = [
        ("user_call", "ama"),
        ("ama", "asset_fn"),
        ("asset_fn", "pyice"),
        ("pyice", "snapshot"),
        ("snapshot", "ledger"),
    ]
    for s, d in pairs:
        sb = success_boxes[s]
        db = success_boxes[d]
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_top_{s}_{d}"),
                start=box_anchor(sb, "right", frac=0.5),
                end=box_anchor(db, "left", frac=0.5),
                color="#2b8a3e",
            )
        )

    # --- BOTTOM TRACK: error path -------------------------------------------
    bot_y = 540
    bot_h = 60
    err_count = 5
    err_step = 80
    err_track_top = bot_y - 30
    err_track_h = err_count * err_step + 60
    bg_bot = background_band(
        idg,
        "track_bot",
        60,
        err_track_top,
        1490,
        err_track_h,
        fill="built",
        opacity=14,
        label="ERROR TRACK   any wrapped exception -> Error Translation -> typed NucleusError",
    )
    elems.extend(bg_bot)
    sources = [
        ("dagster_err", "dagster.DagsterStepExecutionError", "wrapped"),
        ("duckdb_err", "duckdb.OutOfMemoryException", "wrapped"),
        ("pyice_err", "pyiceberg.CommitFailedException", "wrapped"),
        ("polars_err", "polars.SchemaError", "wrapped"),
        ("py_err", "stdlib FileExistsError (race)", "muted"),
    ]
    src_boxes: list[dict[str, Any]] = []
    for i, (slug, label_text, fill) in enumerate(sources):
        b, l = labeled_box(
            idg,
            f"src_{slug}",
            90,
            bot_y + i * err_step,
            280,
            bot_h,
            label_text,
            fill=fill,
            label_size=SIZE_SMALL,
        )
        src_boxes.append(b)
        elems.extend([b, l])

    # Error translator big box (the centre of the bottom track)
    err_box, err_lbl = labeled_box(
        idg,
        "err_translator",
        460,
        bot_y - 10,
        320,
        err_count * err_step + 20,
        "ERROR TRANSLATION LAYER\ncoordination/error_translation.py\n"
        "Every external exception ->\ntyped NucleusError(NE-code,\nuser_message, fix_hint, docs_url)",
        fill="built",
        label_size=SIZE_SMALL,
    )
    elems.extend([err_box, err_lbl])

    # 5 incoming arrows from sources to err_box (left edge), each at the right height
    for i, sb in enumerate(src_boxes):
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_err_in_{i}"),
                start=box_anchor(sb, "right", frac=0.5),
                end=(err_box["x"], err_box["y"] + 30 + i * err_step),
                color="#c92a2a",
            )
        )

    # 5 NE-code outputs on the right side of the error translator
    outputs = [
        (
            "ne1",
            "NucleusInternalError (NE3000)\n[asset:fct_orders] user_message + fix_hint + docs_url",
        ),
        (
            "ne2",
            "NucleusResourceError (NE2007)\nout-of-memory; suggest partition or compute=databricks",
        ),
        (
            "ne3",
            "NucleusCommitConflictError (NE3001)\nconcurrent write; suggest retry or schedule check",
        ),
        ("ne4", "NucleusSchemaError (NE3003)\ncontract violation; suggest schema sync"),
        ("ne5", "NucleusConcurrentRunError (NE3008)\nadvisory lock conflict per ADR-024"),
    ]
    out_boxes: list[dict[str, Any]] = []
    for i, (slug, label_text) in enumerate(outputs):
        b, l = labeled_box(
            idg,
            slug,
            870,
            bot_y + i * err_step,
            660,
            bot_h,
            label_text,
            fill="built",
            label_size=SIZE_SMALL,
        )
        out_boxes.append(b)
        elems.extend([b, l])
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_err_out_{i}"),
                start=(err_box["x"] + err_box["width"], err_box["y"] + 30 + i * err_step),
                end=box_anchor(b, "left", frac=0.5),
                color="#2b8a3e",
            )
        )

    # --- CROSS-TRACK: dashed elbow showing exception capture ----------------
    # When the asset function or pyiceberg.commit_table raises, the success
    # track bails out and the exception drops to the error track. Routing must
    # avoid crossing OTHER source boxes - so we route around the LEFT side of
    # the source-box column via x=70 (outside the source-box left edge x=90).
    cross_lane_y = 470  # horizontal routing lane between the two tracks
    cross_left_lane_x = 70  # vertical lane to the LEFT of the source-box column
    for src_slug, src_idx in [("asset_fn", 1), ("pyice", 2)]:
        sb = success_boxes[src_slug]
        target = src_boxes[src_idx]
        s_x = sb["x"] + sb["width"] / 2
        target_y = target["y"] + target["height"] / 2
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_cross_{src_slug}"),
                start=(s_x, sb["y"] + sb["height"]),
                end=(target["x"], target_y),
                via=[
                    (s_x, cross_lane_y),
                    (cross_left_lane_x, cross_lane_y),
                    (cross_left_lane_x, target_y),
                ],
                color="#c92a2a",
                style="dashed",
                label="raise -> caught",
                label_offset=(8, -18),
            )
        )

    # --- SIDE PANEL: cross-cutting concerns wired into AMA ------------------
    side_x = 1570
    side_y = 180
    side_box = rect(
        idg, idg.make("side_panel"), side_x, side_y, 220, 480, fill="muted", stroke_width=1
    )
    elems.append(side_box)
    elems.append(
        text(
            idg,
            idg.make("side_lbl"),
            side_x + 14,
            side_y + 12,
            "AMA wires in:\n\n"
            "Locks\n  per-asset advisory FileLock\n  ADR-024 / NE3008\n\n"
            "Scheduling daemon\n  cron + sensors\n  v4.1 Section 6.7\n\n"
            "memory_limit guard\n  60% RAM cap on DuckDB\n  P0-1 / NE2007\n\n"
            "expire_old_snapshots\n  after every commit\n  P0-3 / ADR-024",
            size=SIZE_SMALL,
            color="#212529",
            align="left",
        )
    )

    # Dagster-hidden marker (the box BELOW the success track - stays inside
    # the success-track background band because it's part of the success path)
    dagster_x = 330
    dagster_y = 320
    dagster_box, dagster_lbl = labeled_box(
        idg,
        "dagster_hidden",
        dagster_x,
        dagster_y,
        260,
        70,
        "Dagster (substrate, hidden)\nasset graph + sensors + retries",
        fill="wrapped",
        label_size=SIZE_SMALL,
    )
    elems.extend([dagster_box, dagster_lbl])
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_ama_dagster"),
            start=box_anchor(success_boxes["ama"], "bottom", frac=0.5),
            end=box_anchor(dagster_box, "top", frac=0.5),
            color="#868e96",
            style="dashed",
            end_arrowhead=None,
            stroke_width=1,
        )
    )
    elems.append(
        text(
            idg,
            idg.make("dagster_note"),
            dagster_x + 270,
            dagster_y + 22,
            "scripts/dagster_leak_check.py\nguards: zero 'dagster.' strings\nin user-facing output (Section 6.5)",
            size=SIZE_SMALL,
            color="#868e96",
            align="left",
        )
    )

    elems.extend(legend_block(idg, 60, 1010))
    assert_no_arrow_overlap("04_coordination", elems)
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 05 - Intelligence
# ---------------------------------------------------------------------------
#
# CONCEPT:    "a user message becomes an LLM call enriched with project
#             context, then returns a user-facing response". The story is
#             that we are USERS of LLMs (not hosts); the value-add is the
#             context injection (schema / lineage / errors) and the privacy
#             gate, not the LLM itself.
#
# STRUCTURE:  A linear horizontal pipeline with side-injectors. The
#             pipeline is the spine; context inputs come up from below into
#             the Context Injector node; provider fanout drops down from
#             LiteLLM. This makes the "context injection" the visual
#             centerpiece, as it should be (it is the differentiator).
#
# PARADIGM:   Horizontal pipeline with vertical context-injection legs and
#             provider fanout legs. Token-budget guard sits above the spine;
#             stance annotation sits below in the bottom corner.
# ---------------------------------------------------------------------------


def mk_intelligence() -> dict[str, Any]:
    idg = IdGen("d05")
    elems: list[dict[str, Any]] = []

    elems.extend(
        title_block(
            idg,
            40,
            30,
            "Layer 3 - Intelligence: Pipeline + Context Injection (v0.2 chat MVP)",
            # Counter-frames the retired ADR-002 angles below.
            "AI-assisted by design (NOT AI-first / NOT AI-native): we are USERS of LLMs, never hosts",  # <!-- banned-term: AI-first --> <!-- banned-term: AI-native -->
        )
    )
    elems.append(
        section_label(
            idg,
            "intel",
            40,
            80,
            "v4.1 Section 7 (staging) + ADR-015 (chat MVP) + ADR-011 (privacy)",
        )
    )

    elems.extend(
        badge(
            idg,
            "stance",
            1280,
            40,
            460,
            60,
            # Counter-frames the retired ADR-002 angle below.
            "Pillar #3 (engineering, not marketing).\nNot a category pivot to 'AI-native data platform'.",  # <!-- banned-term: AI-native -->
            fill="muted",
        )
    )

    # --- Horizontal pipeline (spine) ---------------------------------------
    spine_y = 320
    spine_h = 100
    spine_steps = [
        ("user_msg", 80, "User message\n'why did fct_orders fail?'", "user", 220),
        ("router", 340, "Router\nintelligence/copilot.py", "built", 220),
        (
            "inject",
            600,
            "CONTEXT INJECTOR\n(redact + inline schema /\nrecent NE-codes)",
            "built",
            280,
        ),
        ("litellm", 940, "LiteLLM\n(provider router)", "wrapped", 220),
        (
            "response",
            1200,
            "Response transform\nCopilotReply{ text,\nsuggested_command, cost }",
            "built",
            240,
        ),
        ("user_out", 1500, "User\n(CLI / Workbench)", "user", 220),
    ]
    spine_boxes: dict[str, dict[str, Any]] = {}
    for slug, sx, label_text, fill, w in spine_steps:
        b, l = labeled_box(
            idg, f"sp_{slug}", sx, spine_y, w, spine_h, label_text, fill=fill, label_size=SIZE_SMALL
        )
        spine_boxes[slug] = b
        elems.extend([b, l])
    spine_pairs = [
        ("user_msg", "router"),
        ("router", "inject"),
        ("inject", "litellm"),
        ("litellm", "response"),
        ("response", "user_out"),
    ]
    for s, d in spine_pairs:
        sb = spine_boxes[s]
        db = spine_boxes[d]
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_sp_{s}_{d}"),
                start=box_anchor(sb, "right", frac=0.5),
                end=box_anchor(db, "left", frac=0.5),
                color="#1864ab",
            )
        )

    # --- Context-injection legs (3 inputs from BELOW the inject node) ------
    # ctx-inputs sit in their own y band (460-540) DIRECTLY below the spine;
    # providers sit further down (620-720), separated by a 60 px clear lane at
    # y=580-590 used for provider elbow routing. ctx-input rightmost edge
    # (x ~= 930) is comfortably to the LEFT of the provider column starts
    # (x >= 940 anchored to LiteLLM) so vertical legs never cross.
    inject_box = spine_boxes["inject"]
    litellm_box = spine_boxes["litellm"]
    ctx_inputs_y = 460
    ctx_inputs_h = 80
    ctx_inputs_w = 200
    ctx_inputs = [
        ("schema", inject_box["x"] + 50, "Project schema\nnucleus_project.yaml +\nasset registry"),
        (
            "lineage",
            inject_box["x"] + inject_box["width"] / 2,
            "Lineage graph\n(v0.5+, faded\nfor v0.2)",
        ),
        ("err", inject_box["x"] + inject_box["width"] - 50, "Recent NE-codes\nfrom Run Ledger"),
    ]
    for slug, lane_x, body in ctx_inputs:
        ctx_box, ctx_lbl = labeled_box(
            idg,
            f"ctx_{slug}",
            lane_x - ctx_inputs_w / 2,
            ctx_inputs_y,
            ctx_inputs_w,
            ctx_inputs_h,
            body,
            fill=("muted" if slug == "lineage" else "user"),
            label_size=SIZE_SMALL,
        )
        elems.extend([ctx_box, ctx_lbl])
        # Short vertical leg from ctx box top up to inject box bottom
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_ctx_{slug}"),
                start=(lane_x, ctx_inputs_y),
                end=(lane_x, inject_box["y"] + inject_box["height"]),
                color="#5f3dc4",
            )
        )

    # --- Provider fanout (4 providers in a single row BELOW the ctx-band) ---
    # Each provider routes UP to the LiteLLM bottom edge via the y=590 clean
    # lane. Anthropic anchored at x=683 lands well to the right of the
    # rightmost ctx-input box edge (~ x=820), so no vertical leg crosses any
    # ctx-input box.
    pv_y = 620
    pv_h = 100
    providers = [
        ("anthropic", "Anthropic\nclaude-3-5-haiku"),
        ("openai", "OpenAI\ngpt-4o-mini"),
        ("azure", "Azure OpenAI\n(BYOK)"),
        ("ollama", "Ollama (local)\nllama3.1:8b - offline"),
    ]
    pv_w = 170
    pv_gap = 18
    pv_total = len(providers) * pv_w + (len(providers) - 1) * pv_gap
    pv_start_x = litellm_box["x"] + litellm_box["width"] / 2 - pv_total / 2
    pv_lane_y = 590
    # Compute 4 evenly-spaced target xs along LiteLLM's bottom edge so each
    # provider has a unique landing spot.
    litellm_bottom_xs = [
        litellm_box["x"] + litellm_box["width"] * frac for frac in (0.18, 0.40, 0.62, 0.84)
    ]
    for i, (slug, body) in enumerate(providers):
        px = pv_start_x + i * (pv_w + pv_gap)
        b, l = labeled_box(
            idg, f"pv_{slug}", px, pv_y, pv_w, pv_h, body, fill="wrapped", label_size=SIZE_SMALL
        )
        elems.extend([b, l])
        provider_center_x = px + pv_w / 2
        target_x = litellm_bottom_xs[i]
        litellm_bottom_y = litellm_box["y"] + litellm_box["height"]
        # 4-point elbow: provider top -> up to lane -> across to target -> up to LiteLLM bottom
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_pv_{slug}"),
                start=(provider_center_x, pv_y),
                end=(target_x, litellm_bottom_y),
                via=[(provider_center_x, pv_lane_y), (target_x, pv_lane_y)],
                color="#0b7285",
            )
        )

    # --- Token budget guard (ABOVE litellm) ---------------------------------
    budget_x = litellm_box["x"] - 40
    budget_y = 130
    budget_w = 300
    budget_h = 130
    budget_box, budget_lbl = labeled_box(
        idg,
        "budget",
        budget_x,
        budget_y,
        budget_w,
        budget_h,
        "Token budget guard\n(ADR-015 Section 4)\n"
        "default 2000 in / 1000 out / 0.10 USD\nNE5012 on exceed",
        fill="built",
        label_size=SIZE_SMALL,
    )
    elems.extend([budget_box, budget_lbl])
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_budget_litellm"),
            start=(budget_x + budget_w / 2, budget_y + budget_h),
            end=(budget_x + budget_w / 2, litellm_box["y"]),
            color="#5f3dc4",
            style="dashed",
            label="enforce",
            label_offset=(6, -16),
        )
    )

    # --- Privacy opt-in gate (ABOVE user_msg / router) ---------------------
    privacy_x = 80
    privacy_y = 130
    privacy_w = 480
    privacy_h = 130
    privacy_box, privacy_lbl = labeled_box(
        idg,
        "privacy",
        privacy_x,
        privacy_y,
        privacy_w,
        privacy_h,
        "Privacy gate (ADR-011 + ADR-015 Section 5)\n"
        "5 redactions: SQL strings, row counts, user/host, abs paths, stack vars\n"
        "Hard cap 4 KB outbound | NO bytes leave laptop until user opt-in",
        fill="built",
        label_size=SIZE_SMALL,
    )
    elems.extend([privacy_box, privacy_lbl])
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_privacy_inject"),
            start=(privacy_x + privacy_w / 2, privacy_y + privacy_h),
            end=(inject_box["x"] + inject_box["width"] / 2, inject_box["y"]),
            via=[
                (privacy_x + privacy_w / 2, inject_box["y"] - 40),
                (inject_box["x"] + inject_box["width"] / 2, inject_box["y"] - 40),
            ],
            color="#5f3dc4",
            style="dashed",
            label="apply\nbefore inject",
            label_offset=(8, -28),
        )
    )

    # --- Conversation persistence (BELOW user_msg) -------------------------
    persist_x = 80
    persist_y = pv_y
    persist_box, persist_lbl = labeled_box(
        idg,
        "persist",
        persist_x,
        persist_y,
        220,
        90,
        "Conversation history\n.nucleus/copilot/turns.ndjson\n(append-only, redacted)",
        fill="built",
        label_size=SIZE_SMALL,
    )
    elems.extend([persist_box, persist_lbl])
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_user_persist"),
            start=(
                spine_boxes["user_msg"]["x"] + spine_boxes["user_msg"]["width"] / 2,
                spine_boxes["user_msg"]["y"] + spine_h,
            ),
            end=(persist_x + 110, persist_y),
            color="#868e96",
            style="dashed",
            end_arrowhead="arrow",
        )
    )

    # --- Staging strip (footer with v0.2 / v0.3 / v0.5 / v0.7) -------------
    staging_y = pv_y + 130
    staging_box = rect(idg, idg.make("staging_box"), 60, staging_y, 1700, 100, fill="muted")
    elems.append(staging_box)
    elems.append(
        text(
            idg,
            idg.make("staging_lbl"),
            74,
            staging_y + 14,
            "Realistic staging (v4.1 Section 7.2 - Amendment 2 vs over-promised v4.0):\n"
            "  v0.1 = none  |  v0.2 = inline chat (this diagram)  |  v0.3 = schema-aware completion  |  "
            "v0.5 = lineage-aware refactoring + ctx.agent runtime + nucleus-mcp-server  |  v0.7 = doc generation + semantic graph queries",
            size=SIZE_SMALL,
            color="#212529",
            align="left",
        )
    )

    elems.extend(legend_block(idg, 60, staging_y + 130))
    assert_no_arrow_overlap("05_intelligence", elems)
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 06 - Experience
# ---------------------------------------------------------------------------
#
# CONCEPT:    "three equal-tier surfaces (CLI, Workbench, ctx SDK) all
#             access the same Coordination layer". The story is unification:
#             one mental model, three equally-valid front doors.
#
# STRUCTURE:  This is a hub-and-spoke. The hub is the Coordination layer
#             (centre, slightly elongated horizontally to convey its role
#             as the platform brain); the spokes are the 3 surfaces
#             radiating out at canonical angles (top, lower-left, lower-right).
#
# PARADIGM:   Hub-and-spoke. Center node is wide horizontally; 3 spokes; the
#             error-display affordance hangs off the side as a panel that
#             all 3 surfaces consume. Bidirectional arrows between hub and
#             each spoke.
# ---------------------------------------------------------------------------


def mk_experience() -> dict[str, Any]:
    idg = IdGen("d06")
    elems: list[dict[str, Any]] = []

    elems.extend(
        title_block(
            idg,
            40,
            30,
            "Layer 4 - Experience: 3 Equal Surfaces, 1 Coordination Hub",
            "CLI + Workbench + ctx SDK are co-equal front doors; all delegate to one Coordination layer",
        )
    )
    elems.append(
        section_label(
            idg,
            "exp",
            40,
            80,
            "v4.1 Section 8 + docs/specs/nucleus_cli_spec.md + docs/specs/nucleus_ctx_sdk_spec.md + ADR-016 (Workbench)",
        )
    )

    # --- Persona ellipse ---------------------------------------------------
    persona_x = 760
    persona_y = 110
    persona = ellipse(idg, idg.make("persona"), persona_x, persona_y, 380, 60, fill="user")
    persona_lbl = text(
        idg,
        idg.make("persona_lbl"),
        persona_x + 28,
        persona_y + 18,
        "User: data engineer in 5-engineer startup",
        size=SIZE_LABEL,
        align="left",
    )
    elems.extend([persona, persona_lbl])

    # --- HUB (Coordination layer) - centre, elongated horizontally ----------
    hub_x = 600
    hub_y = 540
    hub_w = 700
    hub_h = 200
    hub_box, hub_lbl = labeled_box(
        idg,
        "hub",
        hub_x,
        hub_y,
        hub_w,
        hub_h,
        "L2 COORDINATION  (single source of truth)\n"
        "AMA + Error Translation + Run Ledger +\nLocks + Scheduling daemon",
        fill="built",
        label_size=SIZE_SUBTITLE,
    )
    elems.extend([hub_box, hub_lbl])

    # --- 3 SPOKES at top / lower-left / lower-right -----------------------
    # ctx SDK on top (developer surface), CLI lower-left, Workbench lower-right.
    spokes_meta = [
        # (slug, x, y, w, h, label_lines, fill, side_to_hub_anchor)
        (
            "sdk",
            700,
            220,
            500,
            230,
            "ctx SDK (Python)   developer surface\n\n"
            "@nucleus.asset(key, deps, partitions, schedule)\n"
            "@nucleus.check(asset, severity)\n"
            "nucleus.materialize(asset_key) -> MaterializationResult\n"
            "ctx.read(asset_key) -> LazyFrame\n"
            "ctx.sql(\"... {{ ref('a') }} ...\")\n"
            "ctx.copy_from(source, target=...) - postgres / s3 / parquet ...",
            "built",
            "bottom",
        ),
        (
            "cli",
            60,
            820,
            600,
            280,
            "nucleus CLI   operator surface\n\n"
            "nucleus init my-warehouse\n"
            "nucleus up   /   nucleus down\n"
            "nucleus run <asset_key>\n"
            "nucleus ingest postgres://... --table T --as raw.T\n"
            'nucleus query "SELECT ... FROM raw.T LIMIT 10"\n'
            "nucleus list   /   nucleus runs (ledger)\n"
            'nucleus chat "why did fct_orders fail?"\n'
            "nucleus workbench   /   nucleus snapshot",
            "user",
            "top",
        ),
        (
            "wb",
            1240,
            820,
            600,
            280,
            "Workbench (v0.2+)   browser surface\n\n"
            "FastAPI backend (workbench/app.py)\n"
            "  /api/health  /api/version  /api/assets\n"
            "  /api/runs (with SSE log stream)\n"
            "  /api/query (POST: ctx.sql + DuckDB)\n"
            "  /api/chat (POST: AI Copilot)\n\n"
            "React + Vite + Tailwind frontend\n"
            "  asset graph view, catalog, query editor, chat",
            "user",
            "top",
        ),
    ]
    spoke_boxes: dict[str, dict[str, Any]] = {}
    for slug, sx, sy, sw, sh, body, fill, side in spokes_meta:
        b = rect(idg, idg.make(f"spoke_{slug}"), sx, sy, sw, sh, fill=fill)
        elems.append(b)
        elems.append(
            text(
                idg,
                idg.make(f"spoke_lbl_{slug}"),
                sx + 18,
                sy + 12,
                body,
                size=SIZE_SMALL,
                color="#212529",
                align="left",
            )
        )
        spoke_boxes[slug] = b

    # Bidirectional arrows: spoke <-> hub. Each spoke connects to a different
    # face of the hub: SDK to top, CLI to lower-left, WB to lower-right.
    sdk_box = spoke_boxes["sdk"]
    cli_box = spoke_boxes["cli"]
    wb_box = spoke_boxes["wb"]

    # SDK <-> hub (vertical above hub)
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_sdk_hub_down"),
            start=box_anchor(sdk_box, "bottom", frac=0.5),
            end=box_anchor(hub_box, "top", frac=0.5),
            color="#1864ab",
        )
    )
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_sdk_hub_up"),
            start=(hub_box["x"] + hub_box["width"] * 0.55, hub_box["y"]),
            end=(sdk_box["x"] + sdk_box["width"] * 0.55, sdk_box["y"] + sdk_box["height"]),
            color="#2b8a3e",
        )
    )

    # CLI <-> hub (lower-left); arrow leaves hub from its bottom-left corner
    cli_anchor = box_anchor(cli_box, "top", frac=0.7)
    cli_to_hub_via = [(cli_anchor[0], cli_anchor[1] - 40), (hub_box["x"] + 80, cli_anchor[1] - 40)]
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_cli_hub_up"),
            start=cli_anchor,
            end=(hub_box["x"] + 80, hub_box["y"] + hub_box["height"]),
            via=cli_to_hub_via,
            color="#1864ab",
        )
    )
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_cli_hub_dn"),
            start=(hub_box["x"] + 120, hub_box["y"] + hub_box["height"]),
            end=(cli_anchor[0] + 40, cli_anchor[1]),
            via=[
                (hub_box["x"] + 120, cli_anchor[1] - 60),
                (cli_anchor[0] + 40, cli_anchor[1] - 60),
            ],
            color="#2b8a3e",
        )
    )

    # WB <-> hub (lower-right)
    wb_anchor = box_anchor(wb_box, "top", frac=0.3)
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_wb_hub_up"),
            start=wb_anchor,
            end=(hub_box["x"] + hub_box["width"] - 80, hub_box["y"] + hub_box["height"]),
            via=[
                (wb_anchor[0], wb_anchor[1] - 40),
                (hub_box["x"] + hub_box["width"] - 80, wb_anchor[1] - 40),
            ],
            color="#1864ab",
        )
    )
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_wb_hub_dn"),
            start=(hub_box["x"] + hub_box["width"] - 120, hub_box["y"] + hub_box["height"]),
            end=(wb_anchor[0] + 40, wb_anchor[1]),
            via=[
                (hub_box["x"] + hub_box["width"] - 120, wb_anchor[1] - 60),
                (wb_anchor[0] + 40, wb_anchor[1] - 60),
            ],
            color="#2b8a3e",
        )
    )

    # Persona -> SDK (hint: persona drives all 3, but we only draw to the
    # nearest spoke to avoid clutter; the visual is "user touches surfaces")
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_persona_sdk"),
            start=(persona_x + 190, persona_y + 60),
            end=(sdk_box["x"] + sdk_box["width"] / 2, sdk_box["y"]),
            color="#5f3dc4",
            style="dashed",
            end_arrowhead="arrow",
        )
    )

    # --- ERROR-DISPLAY SIDE PANEL (consumed by all 3 surfaces) -------------
    err_panel_x = 60
    err_panel_y = 220
    err_panel = rect(idg, idg.make("err_panel"), err_panel_x, err_panel_y, 560, 230, fill="built")
    elems.append(err_panel)
    elems.append(
        text(
            idg,
            idg.make("err_panel_lbl"),
            err_panel_x + 18,
            err_panel_y + 14,
            "ERROR DISPLAY  (uniform across all 3 surfaces)\n"
            "  per docs/specs/nucleus_cli_spec.md Section 5.4\n\n"
            "[NE2007] NucleusResourceError:\n"
            "  Out of memory while processing 'sales.fct_orders'\n"
            "  fix_hint: add a partition filter, increase memory,\n"
            "            or use compute=databricks\n"
            "  docs:    nucleus.dev/errors/resource\n\n"
            "Same NE-code. Same user_message. Same fix_hint.\n"
            "No DuckDB / Dagster / pyiceberg classnames - ever.",
            size=SIZE_SMALL,
            color="#212529",
            align="left",
        )
    )
    # The relationship "errors flow OUT of Coordination IN to all 3 surfaces"
    # is conveyed by the text annotation below; we deliberately do NOT draw
    # an arrow from the error panel to the hub (any such line would have to
    # cross the SDK spoke or another node) - the hub-and-spoke paradigm reads
    # cleanly without it.
    elems.append(
        text(
            idg,
            idg.make("err_panel_hint"),
            err_panel_x + 18,
            err_panel_y + 240,
            "Coordination produces NucleusError; CLI / Workbench / ctx SDK\n"
            "all render it identically. Same NE-code, same fix_hint, every surface.",
            size=SIZE_SMALL,
            color="#868e96",
            align="left",
        )
    )

    elems.extend(legend_block(idg, 1480, 1130))
    assert_no_arrow_overlap("06_experience", elems)
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 07 - User journey (30-min beachhead)
# ---------------------------------------------------------------------------
#
# CONCEPT:    "a 5-engineer startup goes from `git clone` to BI-ready
#             Iceberg table in <30 minutes, plus a graduation-to-Databricks
#             stretch milestone". Time is the primary axis.
#
# STRUCTURE:  Time-on-X-axis is non-negotiable for this content. The
#             previous version laid 8 boxes out in a 4x2 grid and lost the
#             "time pressure" feeling. A timeline restores it.
#
# PARADIGM:   Horizontal timeline with tick marks at 0/5/10/15/20/25/30
#             minutes; 7 milestone markers placed at the ACTUAL minute
#             they're expected to occur (so the spacing is non-uniform);
#             vertical leader lines from axis tick down to milestone box;
#             one mock terminal-output snippet beneath each milestone;
#             error branch as a dashed offshoot from `nucleus run`;
#             graduation milestone hangs off the right edge.
# ---------------------------------------------------------------------------


def mk_user_journey() -> dict[str, Any]:
    idg = IdGen("d07")
    elems: list[dict[str, Any]] = []

    elems.extend(
        title_block(
            idg,
            40,
            30,
            "30-Minute Beachhead Journey - First BI-Ready Iceberg Table",
            "v0.1 success metric: 5-engineer startup, MacBooks, git clone -> first BI-ready Iceberg table in <30 minutes",
        )
    )
    elems.append(
        section_label(
            idg,
            "journey",
            40,
            80,
            "v4.1 Section 1.5 (beachhead) + Section 11 (local-first promise)",
        )
    )

    # --- TIMELINE AXIS ------------------------------------------------------
    axis_y = 200
    axis_x0 = 100
    axis_x1 = 1620
    elems.append(
        line(
            idg,
            idg.make("axis"),
            axis_x0,
            axis_y,
            axis_x1,
            axis_y,
            stroke_width=3,
        )
    )
    # Arrowhead on the right end (drawn as an arrow with a tiny tail to mimic axis)
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("axis_arrowhead"),
            start=(axis_x1 - 4, axis_y),
            end=(axis_x1 + 60, axis_y),
            color="stroke",
            stroke_width=3,
        )
    )
    elems.append(
        text(
            idg,
            idg.make("axis_lbl"),
            axis_x1 + 70,
            axis_y - 10,
            "time",
            size=SIZE_LABEL,
            color="stroke",
            align="left",
        )
    )

    # Tick marks at 0, 5, 10, 15, 20, 25, 30 min. Map minute -> x linearly.
    def x_at(minutes: float) -> float:
        return axis_x0 + (axis_x1 - axis_x0) * (minutes / 30.0)

    for tick_min in (0, 5, 10, 15, 20, 25, 30):
        tx = x_at(tick_min)
        elems.append(
            line(
                idg,
                idg.make(f"tick_{tick_min}"),
                tx,
                axis_y - 10,
                tx,
                axis_y + 10,
                stroke_width=2,
            )
        )
        elems.append(
            text(
                idg,
                idg.make(f"tick_lbl_{tick_min}"),
                tx - 18,
                axis_y - 36,
                f"00:{tick_min:02d}",
                size=SIZE_SMALL,
                color="#495057",
                align="left",
            )
        )

    # --- 7 MILESTONES at their actual minute ------------------------------
    # (slug, minute, top label, fill, terminal snippet)
    milestones = [
        (
            "install",
            1,
            "1. pip install\nnucleus[core]",
            "user",
            "$ pip install nucleus-data[core]\n  ... 24 packages installed",
        ),
        (
            "init",
            2,
            "2. nucleus init\nmy-warehouse",
            "user",
            "$ nucleus init my-warehouse\n  scaffolded assets/ + nucleus_project.yaml",
        ),
        (
            "up",
            5,
            "3. nucleus up\n(SeaweedFS + catalog)",
            "wrapped",
            "$ nucleus up\n  warehouse ready in 5.8s",
        ),
        (
            "write",
            10,
            "4. write\n@nucleus.asset",
            "built",
            "# assets/example.py\n@nucleus.asset\ndef hello(ctx): ...",
        ),
        (
            "run",
            18,
            "5. nucleus run\nhello",
            "built",
            "$ nucleus run hello\n  snapshot 1 committed (0.4s)",
        ),
        (
            "query",
            22,
            "6. nucleus query\n'SELECT * ...'",
            "user",
            '$ nucleus query "SELECT * FROM hello LIMIT 10"\n  10 rows in 18ms',
        ),
        (
            "wb",
            25,
            "7. nucleus\nworkbench",
            "user",
            "$ nucleus workbench\n  serving http://localhost:8765",
        ),
    ]

    # Milestones alternate between two y bands BELOW the axis. Even-index
    # milestones (install, up, run, wb) go in the CLOSER row; odd-index
    # (init, write, query) go in the FARTHER row. This guarantees no two
    # adjacent milestones in time share the same y band, so boxes never
    # overlap even when minutes are close (e.g. install @ 1 vs init @ 2).
    milestone_w = 190
    milestone_h = 95
    snippet_h = 70
    snippet_pad = 14
    row_close_y = axis_y + 50  # row 1 (closer to axis): even-index
    row_far_y = axis_y + 320  # row 2 (farther from axis): odd-index
    milestone_boxes: dict[str, dict[str, Any]] = {}
    for i, (slug, minute, label_text, fill, snippet) in enumerate(milestones):
        is_close = i % 2 == 0
        my = row_close_y if is_close else row_far_y
        mx = x_at(minute) - milestone_w / 2
        snip_y = my + milestone_h + snippet_pad
        leader_x = x_at(minute)
        # Dashed leader line from the axis tick all the way down to milestone top
        elems.append(
            line(
                idg,
                idg.make(f"leader_{slug}"),
                leader_x,
                axis_y + 10,
                leader_x,
                my,
                style="dashed",
                color="#868e96",
                stroke_width=1,
            )
        )
        b, l = labeled_box(
            idg,
            f"ms_{slug}",
            mx,
            my,
            milestone_w,
            milestone_h,
            label_text,
            fill=fill,
            label_size=SIZE_SMALL,
        )
        milestone_boxes[slug] = b
        elems.extend([b, l])
        snip_box = rect(
            idg,
            idg.make(f"snip_box_{slug}"),
            mx,
            snip_y,
            milestone_w,
            snippet_h,
            fill="muted",
            stroke_width=1,
        )
        elems.append(snip_box)
        elems.append(
            text(
                idg,
                idg.make(f"snip_lbl_{slug}"),
                mx + 8,
                snip_y + 6,
                snippet,
                size=SIZE_SMALL,
                color="#212529",
                align="left",
            )
        )
        durations = {
            "install": "~30s",
            "init": "~5s",
            "up": "~10s",
            "write": "~5min",
            "run": "~15s",
            "query": "~5s",
            "wb": "~5s",
        }
        dur_y = snip_y + snippet_h + 4
        elems.append(
            text(
                idg,
                idg.make(f"dur_{slug}"),
                mx + 8,
                dur_y,
                f"step time: {durations[slug]}",
                size=SIZE_SMALL,
                color="#1864ab",
                align="left",
            )
        )

    # --- GRADUATION milestone (right-edge stretch goal beyond 30:00) -------
    # Graduation aligns with the row-close (even-index) row since the last
    # actual milestone (wb, idx=6) sits there.
    grad_box, grad_lbl = labeled_box(
        idg,
        "grad",
        axis_x1 + 100,
        row_close_y - 20,
        280,
        milestone_h + 40,
        "(stretch)\nGraduate to Databricks\nvia Iceberg portability\nMode 1 - zero migration",
        fill="immortal",
        label_size=SIZE_SMALL,
    )
    elems.extend([grad_box, grad_lbl])
    last_ms = milestone_boxes["wb"]
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_wb_grad"),
            start=box_anchor(last_ms, "right", frac=0.5),
            end=box_anchor(grad_box, "left", frac=0.5),
            color="#1864ab",
            style="dashed",
            label="later",
            label_offset=(8, -22),
        )
    )

    # --- ERROR BRANCH (offshoot from `nucleus run` -> NE-translated -> resume) ---
    # The error branch box sits BELOW the far-row dur text. Distance budget:
    #   row_far_y (520) + milestone_h (95) + snippet_pad (14) + snippet_h (70)
    #   + dur text (~24) ~= 723. Use err_branch_y = 770 for a clean lane.
    run_ms = milestone_boxes["run"]
    next_ms = milestone_boxes["query"]
    err_branch_x = run_ms["x"] - 60
    err_branch_y = 770
    err_box, err_lbl = labeled_box(
        idg,
        "err_branch",
        err_branch_x,
        err_branch_y,
        540,
        90,
        "ERROR BRANCH (any wrapped exception)\n"
        "[NE3001] NucleusCommitConflictError -> fix_hint: retry or check schedule",
        fill="built",
        label_size=SIZE_SMALL,
    )
    elems.extend([err_box, err_lbl])
    # Dashed elbow from `nucleus run` snippet+dur DOWN to err_box top.
    # run is in row_close (y=250), so its dur ends at 250+95+14+70+4+22 = 455.
    # Route lane y=735 sits below all far-row content (ends ~720) and above
    # err_box top (770). Vertical legs at x=run-center are clear of all far-row
    # milestone boxes whose centers are at very different x.
    run_dur_bottom = run_ms["y"] + milestone_h + snippet_pad + snippet_h + 28
    err_lane_y = 735
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_run_err"),
            start=(run_ms["x"] + run_ms["width"] / 2, run_dur_bottom),
            end=(err_box["x"] + 60, err_branch_y),
            via=[(run_ms["x"] + run_ms["width"] / 2, err_lane_y), (err_box["x"] + 60, err_lane_y)],
            color="#c92a2a",
            style="dashed",
            label="raise",
            label_offset=(8, -16),
        )
    )
    # Resume arrow back UP to the `query` milestone.  Routes:
    #   err_box right -> right exit -> UP to lane y=475 (between row_close
    #   bottom ~455 and row_far top 520) -> left to query center x ->
    #   DOWN into query's TOP edge.
    resume_lane_y = 480
    query_center_x = next_ms["x"] + next_ms["width"] / 2
    elems.extend(
        elbow_arrow(
            idg,
            idg.make("ar_err_resume"),
            start=box_anchor(err_box, "right", frac=0.5),
            end=(query_center_x, next_ms["y"]),
            via=[
                (err_box["x"] + err_box["width"] + 60, err_branch_y + 45),
                (err_box["x"] + err_box["width"] + 60, resume_lane_y),
                (query_center_x, resume_lane_y),
            ],
            color="#2b8a3e",
            style="dashed",
            label="fix, resume",
            label_offset=(8, -18),
        )
    )

    # --- DETAIL FOOTER -----------------------------------------------------
    detail_y = err_branch_y + 120
    detail_box = rect(idg, idg.make("detail_box"), 60, detail_y, 1700, 200, fill="muted")
    elems.append(detail_box)
    elems.append(
        text(
            idg,
            idg.make("detail_lbl"),
            74,
            detail_y + 14,
            "What happens behind the scenes (per v4.1 Section 11.1 + ADR-008 storage):\n"
            "  step 3: docker compose up brings SeaweedFS (default per ADR-008) + Lakekeeper-or-filesystem-catalog + nucleus warehouse;\n"
            "          MinIO is preserved as alternate via docker-compose.minio.yml. Health-poll until S3 endpoint responds.\n"
            "  step 4: @nucleus.asset registers the function in an in-process dict; no Dagster import in user code (Constraint #1 + Section 6.5).\n"
            "  step 5: AMA validates contract -> acquires advisory lock (P0-2) -> pyiceberg catalog.commit_table() (ADR-001 atomic) ->\n"
            "          emit OpenLineage event -> append to .nucleus/runs/runs.ndjson -> expire_old_snapshots (P0-3).\n"
            "  step 6: ctx.sql() jinja-resolves {{ ref('hello') }} -> DuckDB iceberg_scan -> Arrow result -> Rich table to terminal.\n"
            "  graduation: Mode 1 - same s3://warehouse + same Iceberg metadata; Databricks reads it natively. Zero migration.",
            size=SIZE_SMALL,
            color="#212529",
            align="left",
        )
    )

    elems.extend(legend_block(idg, 60, detail_y + 220))
    assert_no_arrow_overlap("07_dataflow_user_journey", elems)
    return _wrap(elems)


# ---------------------------------------------------------------------------
# Diagram 08 - Composability + Yield-to-Giants
# ---------------------------------------------------------------------------
#
# CONCEPT:    "two paired stories: WE OWN ONLY 1 LAYER OF THE STACK
#             (Tier 0 immortal foundation, Tier 1 with swap interfaces, Tier
#             2 wrap), AND we INTEGRATE WITH GIANTS via 3 modes (Iceberg
#             portability, hybrid compute, federation)".
#
# STRUCTURE:  Two distinct ideas in one frame. Top half = vertical tier
#             stack with each Tier 1 component getting a horizontal <->
#             swap arrow extending right. Bottom half = three side-by-side
#             panels, one per integration mode.
#
# PARADIGM:   Tier-stack (vertical, top half) + 3-mode panel (horizontal,
#             bottom half), separated by a horizontal divider line + an
#             "integrate, don't compete" header for the bottom section.
# ---------------------------------------------------------------------------


def mk_composability_yield() -> dict[str, Any]:
    idg = IdGen("d08")
    elems: list[dict[str, Any]] = []

    elems.extend(
        title_block(
            idg,
            40,
            30,
            "Composability Constitution + Yield to Giants",
            "Top: 3-tier composability stack with swap interfaces. Bottom: 3 modes of integration with cloud giants.",
        )
    )
    elems.append(
        section_label(
            idg,
            "comp",
            40,
            80,
            "v4.1 Sections 9 (composability) + 10 (yield to giants) + ADR-002 (positioning)",
        )
    )

    # ===================== TOP HALF: tier stack ==========================
    elems.append(
        text(
            idg,
            idg.make("tier_header"),
            60,
            110,
            "COMPOSABILITY STACK   (v4.1 Section 9.3 - swap interface + smoke tests, full adapter ON-DEMAND)",
            size=SIZE_SUBTITLE,
            color="#212529",
            align="left",
        )
    )

    # Tier 2 at top (wrapped capabilities)
    tier_x = 60
    tier_w = 940  # leaves room for swap-target side strip
    tier_h = 130
    tier_gap = 30

    t2_y = 150
    t2_box, t2_lbl = labeled_box(
        idg,
        "t2",
        tier_x,
        t2_y,
        tier_w,
        tier_h,
        "Tier 2 - WRAPPED capabilities (fully replaceable)\n"
        "Connectors: ctx.copy_from / dlt v0.3+   |   Transformations: native ctx.sql + Jinja\n"
        "Notebooks: Marimo (v0.3+)              |   LLM router: LiteLLM   |   Streaming (v1.5+): Benthos / Redpanda",
        fill="wrapped",
        label_size=SIZE_SMALL,
    )
    elems.extend([t2_box, t2_lbl])

    # Tier 1 in middle (with swap interfaces - these get <-> arrows to swap targets)
    t1_y = t2_y + tier_h + tier_gap
    t1_box, t1_lbl = labeled_box(
        idg,
        "t1",
        tier_x,
        t1_y,
        tier_w,
        tier_h,
        "Tier 1 - first-class default + clean swap interface\n"
        "DuckDB   |   Polars   |   Dagster (hidden)   |   pyiceberg + Lakekeeper / SqlCatalog\n"
        "(swap targets shown to the right; full adapter built ON-DEMAND when trigger fires)",
        fill="wrapped",
        label_size=SIZE_SMALL,
    )
    elems.extend([t1_box, t1_lbl])

    # Swap-target column on the right side of T1, one box per Tier 1 component
    swap_x = tier_x + tier_w + 80
    swap_w = 260
    swap_h = 50
    swaps = [
        ("DuckDB", "DataFusion (Apache, Rust)"),
        ("Polars", "DataFusion DF (Apache)"),
        ("Dagster", "nucleus-mini-scheduler"),
        ("pyiceberg", "Apache Polaris (ASF TLP)"),
    ]
    swap_total_h = len(swaps) * swap_h + (len(swaps) - 1) * 12
    swap_y0 = t1_y + (tier_h - swap_total_h) / 2
    for i, (default, target) in enumerate(swaps):
        sy = swap_y0 + i * (swap_h + 12)
        sb, sl = labeled_box(
            idg,
            f"swap_t1_{i}",
            swap_x,
            sy,
            swap_w,
            swap_h,
            f"swap: {target}",
            fill="muted",
            label_size=SIZE_SMALL,
        )
        elems.extend([sb, sl])
        # <-> arrow from T1 right edge to swap target left edge, at component-row height
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_swap_t1_{i}"),
                start=(t1_box["x"] + t1_box["width"], sy + swap_h / 2),
                end=(swap_x, sy + swap_h / 2),
                color="#868e96",
                style="dashed",
                start_arrowhead="arrow",
                end_arrowhead="arrow",
                label=f"{default} <->",
                label_offset=(0, -16),
            )
        )

    # Tier 0 at bottom (immortal foundations)
    t0_y = t1_y + tier_h + tier_gap
    t0_box, t0_lbl = labeled_box(
        idg,
        "t0",
        tier_x,
        t0_y,
        tier_w,
        tier_h,
        "Tier 0 - IMMORTAL foundations (never swap)\n"
        "Apache Arrow   |   Apache Iceberg   |   Apache Parquet   |   Lance (v0.5+)\n"
        "S3 API   |   OpenLineage   |   OpenTelemetry",
        fill="immortal",
        label_size=SIZE_SMALL,
    )
    elems.extend([t0_box, t0_lbl])

    # Note next to T0 (no swap target column)
    elems.append(
        text(
            idg,
            idg.make("t0_note"),
            swap_x,
            t0_y + 30,
            "Tier 0 has no\nswap target.\nThese are the\nlaws of physics.",
            size=SIZE_SMALL,
            color="#5f3dc4",
            align="left",
        )
    )

    # ===================== DIVIDER ========================================
    div_y = t0_y + tier_h + 50
    elems.append(
        line(
            idg,
            idg.make("divider"),
            60,
            div_y,
            1740,
            div_y,
            style="dashed",
            color="#868e96",
            stroke_width=2,
        )
    )

    # ===================== BOTTOM HALF: 3-mode panel =====================
    bottom_header_y = div_y + 14
    elems.append(
        text(
            idg,
            idg.make("yield_header"),
            60,
            bottom_header_y,
            "YIELD TO GIANTS   (v4.1 Section 10 - we do NOT compete; we INTEGRATE via 3 modes)",
            size=SIZE_SUBTITLE,
            color="#212529",
            align="left",
        )
    )

    # Source: Nucleus Iceberg lake (left)
    lake_y = bottom_header_y + 60
    lake_box, lake_lbl = labeled_box(
        idg,
        "nuc_lake",
        60,
        lake_y,
        320,
        110,
        "Nucleus Iceberg lake\n(s3://warehouse + catalog)\nsource of truth",
        fill="built",
        label_size=SIZE_SMALL,
    )
    elems.extend([lake_box, lake_lbl])

    # 3 mode panels stacked vertically to the right of the lake
    mode_x = 460
    mode_w = 1280
    mode_h = 110
    mode_gap = 20
    mode_meta = [
        (
            "mode1",
            "Mode 1: Iceberg PORTABILITY",
            "User points Databricks / Snowflake / Polaris / Trino / R2 at the SAME s3://warehouse.\n"
            "Same Iceberg metadata. ZERO application-code migration. The killer graduation path.",
        ),
        (
            "mode2",
            "Mode 2: HYBRID COMPUTE   (v1.5+)",
            "@nucleus.sql_asset(compute='databricks')   |   @nucleus.python_asset(compute='snowflake')\n"
            "Heavy assets are dispatched off-laptop; result committed back to the same Iceberg lake.",
        ),
        (
            "mode3",
            "Mode 3: FEDERATION   (v2.0+)",
            "Iceberg REST catalog cross-account federation. Data Mesh: each domain runs its own\n"
            "Nucleus, all federated through a shared Iceberg REST catalog. No central control plane needed.",
        ),
    ]
    mode_boxes: list[dict[str, Any]] = []
    for i, (slug, header, body) in enumerate(mode_meta):
        my = lake_y + i * (mode_h + mode_gap)
        mb = rect(
            idg,
            idg.make(f"mode_{slug}"),
            mode_x,
            my,
            mode_w,
            mode_h,
            fill=("muted" if i > 0 else "wrapped"),
        )
        elems.append(mb)
        elems.append(
            text(
                idg,
                idg.make(f"mode_h_{slug}"),
                mode_x + 18,
                my + 10,
                header,
                size=SIZE_BADGE,
                color="#1864ab",
                align="left",
            )
        )
        elems.append(
            text(
                idg,
                idg.make(f"mode_b_{slug}"),
                mode_x + 18,
                my + 38,
                body,
                size=SIZE_SMALL,
                color="#212529",
                align="left",
            )
        )
        mode_boxes.append(mb)
        # Connector from lake to this mode
        elems.extend(
            elbow_arrow(
                idg,
                idg.make(f"ar_lake_{slug}"),
                start=box_anchor(lake_box, "right", frac=0.5),
                end=box_anchor(mb, "left", frac=0.5),
                via=[(420, lake_y + 55), (420, my + mode_h / 2)],
                color="#1864ab",
            )
        )

    # Why-this-strategy-wins note (bottom-right corner of the bottom half)
    why_y = mode_boxes[-1]["y"] + mode_h + 20
    why_box = rect(idg, idg.make("why_box"), 60, why_y, 1680, 130, fill="muted")
    elems.append(why_box)
    elems.append(
        text(
            idg,
            idg.make("why_lbl"),
            76,
            why_y + 14,
            "Why this strategy wins:\n"
            "  - acquisition-friendly: giants see Nucleus as a feeder, not a threat\n"
            "  - no data lock-in: Iceberg portability removes the #1 procurement objection\n"
            "  - smaller scope: we don't build distributed compute, we don't build a control plane\n"
            "  - customer trust: 'if we outgrow you, we can leave' - users stay LONGER, not shorter",
            size=SIZE_SMALL,
            color="#212529",
            align="left",
        )
    )

    elems.extend(legend_block(idg, 60, why_y + 150))
    assert_no_arrow_overlap("08_composability_yield_to_giants", elems)
    return _wrap(elems)


# ---------------------------------------------------------------------------
# README (per-diagram paradigm choices)
# ---------------------------------------------------------------------------


README = """# Nucleus Architecture - Excalidraw Diagram Set

Visual companion to [`docs/specs/nucleus_architecture_v4.1.md`](../../specs/nucleus_architecture_v4.1.md).
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
