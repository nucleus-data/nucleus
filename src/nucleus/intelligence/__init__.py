"""Intelligence layer — AI-assisted authoring & operations (L3).

**This layer is empty in v0.1.** Per ``AGENTS.md`` and the staged release
plan, AI features land in later tiers:

    - v0.2    Workbench Copilot (simple chat)
    - v0.3    Workbench Copilot (schema-aware)
    - v0.5    Lineage-aware Copilot + ``ctx.agent`` runtime
    - v0.7+   Semantic Knowledge Graph + Cost-aware planner
    - v0.8+   Replay / time-travel debugger

Per ``nucleus_architecture_v4.1.md`` §13.3, AI-related APIs may have
breaking changes in minor versions (with ``NucleusAIBreakingChange``
warnings) — they evolve faster than the core data APIs which follow
strict semver.

Dependency direction (``engineering.md`` §3.1):
    intelligence may import from coordination, engines, physics, _internal.
    intelligence must NEVER import from ctx or cli.
"""

from __future__ import annotations
