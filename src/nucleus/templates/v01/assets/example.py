"""Example asset for {project_name} (generated {today}).

Run: ``nucleus run example.greeting`` (after ``nucleus up``).
"""

from __future__ import annotations

import polars as pl

import nucleus


@nucleus.asset("example.greeting")
def greeting(ctx: object) -> pl.DataFrame:
    """A tiny self-contained example — no upstream dependency required.

    Demonstrates the minimum shape of a Nucleus asset: decorated function
    returning a Polars DataFrame. The Asset Materialization Adapter
    (v4.1 §6.2) writes the returned frame to an Iceberg snapshot.
    """
    del ctx
    return pl.DataFrame(
        {{
            "name": ["world", "nucleus", "iceberg"],
            "value": [1, 2, 3],
        }}
    )
