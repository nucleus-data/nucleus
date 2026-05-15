"""Empirical benchmark suite for the Nucleus v0.2.0 GA hardening wave.

Each ``b*_*.py`` script measures one dimension of the perf claims in
``docs/research/performance_reliability_targets.md`` and writes both
human-readable output (stdout) and machine-readable JSON
(``docs/benchmarks/_results/<name>.json``).

``run_all.py`` orchestrates them and aggregates results into the
``docs/benchmarks/2026-05-15_baseline.md`` report.

Anti-fakery rule (per task spec): if a measurement falls short of a
claim, the script records the honest number and a ``severity`` tag —
never a fabricated value.
"""
