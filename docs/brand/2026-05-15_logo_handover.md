# Logo Handover — 2026-05-15

## Decision (locked)

**Primary brand mark**: Option 2 — Composable Hexagon.

Source asset: `assets/nucleus-logo-option-2-composable.png`

## Why this one

- Tells the architecture story directly: 6 wrap'd OSS components forming a single core; 1 orange segment offset = "swap interface + smoke tests" (Composability Law #1, `nucleus_architecture_v4.1.md` §9).
- Metallic film-grain + blue/orange accent matches Editorial Hero UI direction (Workbench v0.3).
- Visually distinct from React (orbital), Dagster (DAG), Airflow (pinwheel), generic monograms.
- Scales: hexagon-only mark works at 16px favicon; full lockup works at billboard.

## Retained alternates (do NOT delete)

| Asset path | Reserved use |
|---|---|
| `assets/nucleus-logo-option-1-atomic.png` | Slide-deck hero / OG cards / marketing illustrations |
| `assets/nucleus-logo-option-3-monogram.png` | Favicon experiments / CLI ASCII splash fallback |
| `assets/nucleus-logo-option-4-dag.png` | Explorations folder; do not ship publicly (too close to competitor marks) |

## Next-chat queue (logo workstream only)

### 1. Variants of Option 2
- **Dark-mode**: off-black background (#0A0A0F), brighter blue palette, orange accent retained.
- **Monochrome**: single-color flat version (black + white variants) for embroidery, single-color print, fax/scan fallback.
- **Horizontal lockup**: hexagon on left + "nucleus" wordmark on right — for site headers, GitHub README banner.
- **Hexagon-only mark**: no wordmark — for app icon, favicon, tab indicator.

### 2. Export size matrix
- PNG raster: 16, 32, 64, 128, 192, 256, 512, 1024 px
- SVG vector master (single source-of-truth)
- ICO bundle for `favicon.ico` (16+32+48)
- OG card 1200×630 with founder-approved tagline placement (see §3)

### 3. Tagline candidates for OG card (founder picks one)
- "Ship data products from a laptop."
- "Composable data engineering, AI-assisted by design."
- "Modern data platform built on open Apache foundations."

### 4. Files to update once exports ready
- `frontend/public/favicon.ico`
- `src/nucleus/workbench/static/favicon.*`
- `src/nucleus/workbench/static/og-card.png`
- `README.md` header banner
- `docs/brand/README.md` (new brand-guide section: colors, spacing rules, do/don't)

## Out-of-scope for the logo chat

The following are tracked in the main chat — do **not** touch in the logo workstream:

- Foreground reconciliation across 3 builder returns (`ee37bb6` + `0a65da5` + Workbench v0.3 commits): pyproject.toml / CHANGELOG / AGENTS.md collision check.
- Wave 1A-K agents status sweep.
- Phase 2 root reorg per `docs/reorg/2026-05-15_root_md_reorg.md`.
- ADR ratification follow-ups.

## Copy-paste prompt for the new chat

```
Read docs/brand/2026-05-15_logo_handover.md.

Founder picked Option 2 (Composable Hexagon) as Nucleus's primary brand mark.

Execute the "Next-chat queue" §1 + §2 + §4. Use assets/nucleus-logo-option-2-composable.png as the visual reference for grain density, hexagon proportions, and the blue + orange accent palette.

Stay strictly inside the logo workstream — do not touch foreground reconciliation, wave agents, or root reorg.

Run in Multitask Mode.
```
