"""PoC #2 — manual end-to-end demo.

Run after ``pip install -e .[dev]`` from the repo root::

    python poc/p2_ctx_sql/demo.py

What it does:
    1. Defines a tiny in-memory asset directory.
    2. Renders a sample SELECT template with ``{{ ref('staging.orders') }}``
       and prints the rendered SQL + the captured ref list.
    3. Demonstrates the malformed-name failure path (``ref('Bad Name')``).
    4. Returns 0 only if BOTH the happy path AND the error path behave
       correctly; 1 otherwise.
"""

from __future__ import annotations

from nucleus.errors import NucleusSQLSyntaxError
from poc.p2_ctx_sql.resolver import resolve_sql

# Tiny in-memory directory: logical name → concrete Iceberg expression.
# The real ``ctx`` will look this up against the asset registry + catalog.
_ASSETS = {
    "staging.orders": "iceberg_scan('warehouse/staging/orders')",
    "staging.customers": "iceberg_scan('warehouse/staging/customers')",
}


def _resolve(name: str) -> str:
    return _ASSETS[name]


_TEMPLATE = """\
SELECT customer_id, SUM(amount) AS total
FROM {{ ref('staging.orders') }}
WHERE order_date >= '2026-01-01'
GROUP BY customer_id
"""


def main() -> int:
    print("=" * 60)
    print("PoC #2 — native ctx.sql Jinja resolver demo")
    print("=" * 60)

    rendered, refs = resolve_sql(_TEMPLATE, _resolve)
    print("\nRendered SQL:")
    print("-" * 60)
    print(rendered, end="")
    print("-" * 60)
    print(f"Referenced assets (encounter order): {refs}")

    if "iceberg_scan('warehouse/staging/orders')" not in rendered:
        print("\nFAIL: ref() did not resolve to the expected Iceberg expression.")
        return 1
    if refs != ["staging.orders"]:
        print(f"\nFAIL: expected refs == ['staging.orders'], got {refs}.")
        return 1
    print("[OK] Happy path resolved correctly.")

    print("\nMalformed-name path:")
    try:
        resolve_sql("SELECT * FROM {{ ref('Bad Name') }}", _resolve)
    except NucleusSQLSyntaxError as exc:
        print("Caught NucleusSQLSyntaxError as expected:")
        print(exc.rendered())
        if "jinja2" in exc.rendered().lower():
            print("\nFAIL: jinja2 type leaked into rendered output.")
            return 1
        print("\n[OK] No jinja2 references in rendered output.")
        return 0

    print("FAIL: ref('Bad Name') did not raise.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
