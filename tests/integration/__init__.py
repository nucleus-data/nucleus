"""Integration tests — end-to-end flows that touch multiple layers.

Per ``AGENTS.md`` §11.10 (single-file PR discipline) + ``.cursor/rules/nucleus.mdc``
(Composability by Constitution): tests here verify the *swap boundary* works
empirically — e.g. the Dagster ⇄ mini-scheduler swap test that proves the
abstraction is real, not aspirational.

Distinct from ``tests/swap/`` (per-component smoke tests) and
``tests/coordination/`` (single-module unit tests).  Integration tests may
register assets and exercise the AMA against a real Iceberg filesystem
catalog; they remain in-process (no Docker / no real cloud).
"""
