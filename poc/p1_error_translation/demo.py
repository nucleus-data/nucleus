"""PoC #1 — manual end-to-end demo.

Run after ``pip install -e .[dev]`` from the repo root::

    python poc/p1_error_translation/demo.py

What it does:
    1. Defines one OK asset + one failing asset.
    2. Materializes them; catches the Dagster exception.
    3. Translates to NucleusError; prints rendered output.
    4. Verifies the rendered string contains no ``dagster`` substring
       (the acceptance criterion §2.5 of README).
"""

from __future__ import annotations

import dagster as dg

from poc.p1_error_translation.translator import translate


@dg.asset
def ok_upstream() -> int:
    """Trivial healthy asset. Returns 42."""
    return 42


@dg.asset
def failing_downstream(ok_upstream: int) -> int:  # noqa: ARG001
    """Simulates a source-connection failure during materialization.

    ``ok_upstream`` is unused in the body but required so Dagster wires the
    dependency from :func:`ok_upstream` by parameter name.
    """
    raise ConnectionError("could not reach postgres at localhost:5432")


def main() -> int:
    print("=" * 60)
    print("PoC #1 — Dagster error translation demo")
    print("=" * 60)

    try:
        dg.materialize([ok_upstream, failing_downstream])
    except Exception as raw_exc:
        print(f"\nCaught raw exception: {type(raw_exc).__name__}")
        print(f"  str(): {raw_exc!s}\n")

        translated = translate(raw_exc)
        rendered = translated.rendered()

        print("Rendered NucleusError:")
        print("-" * 60)
        print(rendered)
        print("-" * 60)

        if "dagster" in rendered.lower():
            print("\nFAIL: dagster type leaked into rendered output!")
            return 1
        print("\n[OK] No dagster references in rendered output.")
        return 0

    print("ERROR: expected materialization to fail, but it succeeded.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
