"""Native ``ctx.sql`` Jinja resolver — PoC #2 (steps 2-3 of nucleus_poc_plan.md §2).

Scope (deliberately minimal):
    - ONE feature: ``{{ ref('schema.name') }}`` rendering.
    - No ``source()``, no ``config()``, no macros, no DAG building. Those
      are explicit non-goals for v0; later PoC iterations layer them on.
    - 5-7 tests, not 50.
    - Will graduate to ``src/nucleus/coordination/sql_resolver.py``
      (or similar) only after acceptance criteria pass.

Pins/docs:
    - jinja2==3.1.5
    - ``nucleus_architecture_v4.1.md`` §6.4 — Error Translation Discipline
    - ``nucleus_poc_plan.md`` §2 — PoC #2 spec
"""

from __future__ import annotations

import re
from typing import Callable

import jinja2

# Docs: https://jinja.palletsprojects.com/en/stable/api/
# Pinned version: 3.1.5

from nucleus.errors import NucleusSQLSyntaxError

# Asset name shape used by ``ref()``: ``<schema>.<name>``, both lowercase,
# starting with a letter. v0 deliberately accepts any ``schema`` segment
# (not only ``raw|staging|marts|ops`` from engineering.md §15.3) — that
# stricter layer-validation belongs in the asset registry, not the SQL
# resolver. Keeps this PoC focused on rendering, not registration.
_REF_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def resolve_sql(
    template: str,
    ref_resolver: Callable[[str], str],
) -> tuple[str, list[str]]:
    """Render a Jinja-templated SQL string.

    Args:
        template: Raw SQL with ``{{ ref('schema.name') }}`` expressions.
        ref_resolver: Callable that maps a logical asset name like
            ``'staging.orders'`` to a concrete Iceberg reference (e.g.
            ``"iceberg_scan('warehouse/staging/orders')"``).

    Returns:
        ``(rendered_sql, refs)`` — ``refs`` is the deduplicated list of
        asset names the template referenced, in encounter order. Useful
        later for asset graph building (deferred to a future PoC).

    Raises:
        NucleusSQLSyntaxError: ``ref()`` was called with a malformed name,
            an unknown Jinja variable was referenced (``StrictUndefined``),
            or the template failed to parse.
    """
    seen: set[str] = set()
    ordered: list[str] = []

    def _ref(name: object) -> str:
        if not isinstance(name, str) or not _REF_NAME_RE.match(name):
            raise NucleusSQLSyntaxError(
                user_message=f"ref({name!r}) is not a valid asset name.",
                fix_hint=(
                    "Asset names must match '<schema>.<name>' where each "
                    "part starts with a lowercase letter and contains only "
                    "lowercase letters, digits, or underscores. "
                    "Example: ref('staging.orders')."
                ),
            )
        if name not in seen:
            seen.add(name)
            ordered.append(name)
        return ref_resolver(name)

    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    env.globals["ref"] = _ref

    try:
        rendered = env.from_string(template).render()
    except NucleusSQLSyntaxError:
        # ref() validation failures are already typed; pass through.
        raise
    except (jinja2.UndefinedError, jinja2.TemplateSyntaxError) as exc:
        # Translate at the boundary; never let a Jinja class name reach
        # the caller (mirrors PoC #1 leak discipline; v4.1 §6.4).
        raise NucleusSQLSyntaxError(
            user_message=f"SQL template rendering failed: {exc}",
            fix_hint=(
                "Check the template for unknown variables, mismatched "
                "braces, or unsupported expressions. v0 supports only "
                "{{ ref('schema.name') }} — source(), config(), and "
                "user macros are deferred."
            ),
            cause=exc,
        ) from exc

    return rendered, ordered
