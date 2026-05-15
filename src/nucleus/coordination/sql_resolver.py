"""Native ``ctx.sql`` Jinja resolver — ``resolve_sql()``.

Promoted 2026-05-13 from ``poc/p2_ctx_sql/resolver.py`` per architecture v4.1 §6.

# Stability: Beta

Scope (deliberately minimal — v4.1 §5.6.0):
    - ONE feature: ``{{ ref('schema.name') }}`` rendering.
    - No ``source()``, no ``config()``, no macros, no DAG building. Those
      are explicit non-goals for v0.1; later PoC iterations layer them on.
    - 16 tests after the v0.2 hardening pass (arity, cycle, unknown
      asset, empty / injection-shaped names, whitespace, comments).

Pins/docs (per AGENTS.md §11.12):
    - jinja2==3.1.5
    - ``nucleus_architecture_v4.1.md`` §5.6.0 — native ctx.sql scope ceiling
    - ``nucleus_architecture_v4.1.md`` §6.4 — Error Translation Discipline
"""

from __future__ import annotations

import difflib

# Docs: https://docs.python.org/3/library/difflib.html
import re
from collections.abc import Callable, Iterable

import jinja2

# Docs: https://jinja.palletsprojects.com/en/stable/api/
# Pinned version: 3.1.5
from nucleus.errors import (
    NucleusAssetNotFound,
    NucleusError,
    NucleusInvalidAssetDefinition,
    NucleusSQLSyntaxError,
)

# T9 cycle detection: NucleusInvalidAssetDefinition reused for graph-level
# cycle invariant (Option A, 2026-05-13 autopilot default per promotion task).
# A dedicated NucleusAssetGraphError may be introduced when the asset-graph
# walker lands; no ADR-006 amendment required for Option A.

# Asset name shape used by ``ref()``: ``<schema>.<name>``, both lowercase,
# starting with a letter. v0 deliberately accepts any ``schema`` segment
# (not only ``raw|staging|marts|ops`` from engineering.md §15.3) — that
# stricter layer-validation belongs in the asset registry, not the SQL
# resolver. Keeps this PoC focused on rendering, not registration.
_REF_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def resolve_sql(
    template: str,
    ref_resolver: Callable[[str], str],
    *,
    available: Iterable[str] | None = None,
    bindings: dict[str, object] | None = None,
    _resolving: frozenset[str] = frozenset(),
) -> tuple[str, list[str]]:
    """Render a Jinja-templated SQL string.

    Args:
        template: Raw SQL with ``{{ ref('schema.name') }}`` expressions.
        ref_resolver: Callable that maps a logical asset name like
            ``'staging.orders'`` to a concrete Iceberg reference (e.g.
            ``"iceberg_scan('warehouse/staging/orders')"``).
        available: Optional set of known asset names. When provided,
            unknown-asset errors include a "did you mean" suggestion
            list (all names if ≤5, else the 5 closest by difflib).
        bindings: Optional user-defined Jinja variables. When provided,
            they are made available to the template as top-level globals
            via ``env.globals.update()`` AFTER ``ref`` is installed.
            ``'ref'`` is reserved — a binding named ``'ref'`` raises
            ``NucleusSQLSyntaxError`` so the resolver's ``ref()`` cannot
            be shadowed. Default ``None`` → no extra globals (preserves
            single-template behavior used by recursive multi-asset
            callers).
        _resolving: Set of asset names currently in flight (used by
            recursive callers that expand multi-asset chains). When the
            template re-refs a name already in this set, a cycle is
            raised. Default empty → no cycle detection (single-template
            mode, which is what v0.1 ``ctx.sql`` uses).

    Returns:
        ``(rendered_sql, refs)`` — ``refs`` is the deduplicated list of
        asset names the template referenced, in encounter order. Useful
        later for asset graph building (deferred to a future PoC).

    Raises:
        NucleusSQLSyntaxError: ``ref()`` was called with bad arity, a
            malformed / empty name, an unknown Jinja variable, the
            template failed to parse, or ``bindings`` collided with the
            reserved ``'ref'`` name.
        NucleusAssetNotFound: ``ref_resolver`` raised ``KeyError`` for
            the looked-up asset name.
        NucleusInvalidAssetDefinition: a ``ref()`` cycle was detected
            against the caller-supplied ``_resolving`` stack.
    """
    if bindings is not None and "ref" in bindings:
        # Reserved-name collision check (defensive depth on top of
        # ordering below — even if a future refactor swaps the order of
        # env.globals updates, this guard rejects the unsafe input up
        # front per v4.1 §6.4 translation discipline).
        raise NucleusSQLSyntaxError(
            user_message=("Binding name 'ref' is reserved and cannot be used as a Jinja variable."),
            fix_hint=(
                "Rename the binding. 'ref' is reserved for the asset "
                "resolver in {{ ref('schema.name') }}; pick a different "
                "name (e.g. 'ref_value' or 'reference')."
            ),
        )

    seen: set[str] = set()
    ordered: list[str] = []
    _available_list = sorted(set(available)) if available is not None else None

    def _ref(*args: object, **kwargs: object) -> str:
        if kwargs or len(args) != 1:
            raise NucleusSQLSyntaxError(
                user_message=(
                    f"ref() takes exactly 1 positional asset-name argument; "
                    f"got {len(args)} positional and {len(kwargs)} keyword."
                ),
                fix_hint="ref() requires an asset name. Example: ref('staging.orders').",
            )
        name = args[0]
        if not isinstance(name, str) or not name:
            raise NucleusSQLSyntaxError(
                user_message="ref() requires a non-empty quoted asset name.",
                fix_hint="Did you forget the quotes? Example: ref('staging.orders').",
            )
        if not _REF_NAME_RE.match(name):
            raise NucleusSQLSyntaxError(
                user_message=f"ref({name!r}) is not a valid asset name.",
                fix_hint=(
                    "Asset names must match '<schema>.<name>' where each part "
                    "starts with a lowercase letter and contains only lowercase "
                    "letters, digits, or underscores. Example: ref('staging.orders')."
                ),
            )
        if name in _resolving:
            cycle = " -> ".join([*sorted(_resolving), name])
            raise NucleusInvalidAssetDefinition(
                user_message=f"Circular asset reference detected: {cycle}.",
                fix_hint="Break the cycle in the asset chain — asset graphs must be acyclic.",
            )
        if name not in seen:
            seen.add(name)
            ordered.append(name)
        try:
            return ref_resolver(name)
        except KeyError as exc:
            hint = "Check the asset name spelling, or register the asset first."
            if _available_list:
                suggestions = (
                    list(_available_list)
                    if len(_available_list) <= 5
                    else difflib.get_close_matches(name, _available_list, n=5, cutoff=0.0)
                )
                if suggestions:
                    hint = f"Available assets include: {', '.join(suggestions)}. " + hint
            raise NucleusAssetNotFound(
                user_message=f"Asset {name!r} is not defined.",
                fix_hint=hint,
                cause=exc,
            ) from exc

    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    env.globals["ref"] = _ref
    if bindings is not None:
        # Order matters: install ``ref`` FIRST, then user globals. The
        # collision check above already rejects ``'ref' in bindings``;
        # this ordering is intentional (additive parameter, not a
        # general macro injection point).
        env.globals.update(bindings)

    try:
        rendered = env.from_string(template).render()
    except NucleusError:
        # ref() validation failures, unknown-asset hints, and cycle
        # detection are already typed; pass through untouched (v4.1 §6.4).
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
