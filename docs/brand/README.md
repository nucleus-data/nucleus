# Nucleus brand pack

**Decision locked 2026-05-15** — Option 2 "Composable Hexagon" per
[`docs/brand/2026-05-15_logo_handover.md`](2026-05-15_logo_handover.md).

## Visual metaphor

5 wrapped open-source engines forming a single core + 1 offset wedge =
swap interface + smoke tests. Per
[`nucleus_architecture_v4.1.md` §9](../../nucleus_architecture_v4.1.md#9-composability-by-constitution)
(Composability Law #1).

## Variant hierarchy

| Variant | File | Use when |
|---|---|---|
| **Premium** (vertical lockup, cream paper, grain) | `assets/brand/nucleus-logo.png` | **Default everywhere there's space** — README banner, OG cards, slides, docs hero |
| **Vertical lockup SVG** (transparent) | `assets/brand/nucleus-logo.svg` | In-app UI contexts where the cream paper would clash (dark themes, embedded inline) |
| **Mark-only SVG** (transparent) | `assets/brand/nucleus-mark.svg` | True small-format constraints — favicons, app icons, tab badges |
| **Favicon ICO/SVG** | `assets/brand/favicon.{ico,svg}` | Browser tabs (extreme small format) |

**Default to the premium PNG anywhere there's space.** The mark-only SVG is for
favicons and other extreme small-format constraints — not the default.

## Color palette (sampled from the locked reference)

| Token | Hex | Use |
|---|---|---|
| `nucleus-navy-deep` | `#132A65` | Top wedge (deepest) |
| `nucleus-blue-900` | `#0F3193` | Top-left wedge |
| `nucleus-blue-800` | `#2E65DD` | Bottom-left wedge |
| `nucleus-blue-600` | `#3273FB` | Bottom wedge |
| `nucleus-blue-400` | `#72A6F7` | Bottom-right wedge (lightest) |
| `nucleus-orange` | `#F37840` | Swap wedge (top-right, offset) |
| `nucleus-cream` | `#FAF9F6` | Paper-cream canvas |
| `nucleus-night` | `#0A0A0F` | Reserved dark-mode surface |
| `nucleus-ink` | `#09224F` | Wordmark navy |

## Build

```
pip install resvg-py Pillow         # build-time only; not pinned in pyproject.toml
python scripts/brand/build_logo_assets.py
```

## Tagline note

`Ship data products from a laptop.` ships as the working default per
[ADR-002 §8.1](../decisions/ADR-002-positioning-decision-2026-05.md);
final wording locks after the PoC #5 external-tester field test (§8.4).
