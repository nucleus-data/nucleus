"""ADR-039 install-extras well-formedness test.

Validates that the eight runtime extras groups introduced by
[ADR-039](../docs/decisions/ADR-039-install-size-split.md) plus the
two pre-existing runtime groups (``observability``, ``lineage-advanced``)
are well-formed across BOTH layers of truth:

1. **Source layer** -- ``pyproject.toml`` declares the group with a
   non-empty list of exact-pinned entries (operator must be ``==``).
2. **Wheel/install layer** -- ``importlib.metadata.requires("nucleus")``
   surfaces each declared dep with the matching ``; extra == "<name>"``
   marker so ``pip install nucleus[<name>]`` actually pulls it in.

This catches three regression classes early:

* A contributor accidentally moves a runtime dep into the wrong extras
  group (or back into core) without updating the boundary docs.
* The hatchling build backend drops an extras row from the wheel
  metadata (would silently break ``pip install nucleus[ai]``).
* The ``all`` meta-group loses its PEP 508 self-reference (would make
  ``pip install nucleus[all]`` a no-op).

Per PEP 621 ``[project.optional-dependencies]``
(https://peps.python.org/pep-0621/) + PEP 508 environment markers
(https://peps.python.org/pep-0508/#environment-markers).

Companion governance:
- ``scripts/check_install_size.py`` -- enforces the <30 core-deps ceiling
- ``scripts/check_pinning.py`` -- enforces ``==`` discipline on extras
- ``docs/compatibility.md`` §2 -- human-readable extras matrix
"""

from __future__ import annotations

import importlib.metadata
import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Eight named extras groups from ADR-039 + the two pre-existing groups
# (`observability`, `lineage-advanced`). Each row is (group_name,
# minimum_expected_dep_count). The minimum is a sanity floor -- the
# `pyproject.toml` is the source of truth, but we want to fail loudly if
# a group is accidentally emptied (which would happen if a contributor
# mass-deletes lines).
_RUNTIME_EXTRAS: tuple[tuple[str, int], ...] = (
    ("postgres", 3),  # sqlalchemy + psycopg + dlt
    ("mysql", 3),  # sqlalchemy + pymysql + dlt
    ("snowflake", 1),  # dlt[snowflake]
    ("s3", 1),  # s3fs self-ref
    ("gcs", 1),  # gcsfs
    ("ai", 1),  # litellm
    ("workbench", 3),  # fastapi + uvicorn + orjson
    ("observability", 1),  # opentelemetry-sdk
    ("lineage-advanced", 1),  # sqlglot
)


# Regex to pull the bare package name (extras + version stripped).
_PKG_NAME_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_.\-]*)")


def _load_pyproject() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _extras_from_pyproject(group: str) -> list[str]:
    project = _load_pyproject()["project"]
    assert isinstance(project, dict)
    extras = project.get("optional-dependencies", {})
    assert isinstance(extras, dict)
    deps = extras.get(group, [])
    assert isinstance(deps, list)
    return [str(d) for d in deps]


def _pkg_name(raw: str) -> str:
    """Lowercase the package name from a dep spec like 'psycopg[binary]==3.2.3'."""
    m = _PKG_NAME_RE.match(raw)
    assert m, f"could not parse package name from {raw!r}"
    return m.group(1).lower()


def _installed_extras_for_pkg(pkg: str, extra: str) -> set[str]:
    """Return the set of installed deps whose metadata has ``; extra == "<extra>"``.

    Walks ``importlib.metadata.requires("<pkg>")`` -- the live wheel
    metadata of the installed Nucleus distribution. Returns lowercase
    package names. Empty set means: the extra is unknown to the wheel
    OR the wheel was built before the extras change landed.
    """
    requires = importlib.metadata.requires(pkg)
    if requires is None:
        return set()
    out: set[str] = set()
    marker_substring = f'extra == "{extra}"'
    for req in requires:
        if marker_substring not in req:
            continue
        # Strip everything after the first ';' to get the bare spec.
        spec_part = req.split(";", 1)[0]
        out.add(_pkg_name(spec_part))
    return out


# ---------------------------------------------------------------------------
# 1. Each extras group is declared in pyproject.toml with at least N entries
#    and every entry is an exact pin (==).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("group", "minimum_count"), _RUNTIME_EXTRAS)
def test_extras_group_declared_in_pyproject(group: str, minimum_count: int) -> None:
    """Every runtime extras group exists with >= minimum_count entries."""
    deps = _extras_from_pyproject(group)
    assert len(deps) >= minimum_count, (
        f"[project.optional-dependencies] {group!r} has {len(deps)} "
        f"entry/entries but the ADR-039 floor is {minimum_count}. "
        f"Found: {deps}"
    )


@pytest.mark.parametrize(("group", "_minimum"), _RUNTIME_EXTRAS)
def test_extras_group_uses_exact_pins(group: str, _minimum: int) -> None:
    """Every entry in a runtime extras group uses '==' (no '>=', '~=' allowed).

    Mirrors ``scripts/check_pinning.py`` ``RUNTIME_EXTRAS_GROUPS``
    enforcement -- duplicate here so a missed CI invocation can't merge
    a loose pin.
    """
    deps = _extras_from_pyproject(group)
    for raw in deps:
        assert "==" in raw, (
            f"Runtime extras `{group}` entry {raw!r} is not exact-pinned. "
            f"Per AGENTS.md §11.13 + ADR-039, every runtime extras entry "
            f"must use `==`."
        )


# ---------------------------------------------------------------------------
# 2. The wheel metadata surfaces the same extras with matching markers.
#    Skip when the installed distribution is older than the pyproject under
#    test (e.g. an editable install hasn't been re-run after pyproject edits).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("group", "_minimum"), _RUNTIME_EXTRAS)
def test_extras_group_visible_in_wheel_metadata(group: str, _minimum: int) -> None:
    """``importlib.metadata.requires("nucleus")`` exposes the extras group.

    Validates that the wheel metadata has the `; extra == "<group>"`
    markers for every dep declared in `pyproject.toml`. If the
    installed package was built from an older `pyproject.toml`, the
    test is skipped (with an explicit message) so we don't fail CI on
    a stale editable install.
    """
    try:
        installed_version = importlib.metadata.version("nucleus")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("nucleus is not installed as a distribution; run `pip install -e .` first")

    declared = {_pkg_name(d) for d in _extras_from_pyproject(group)}
    observed = _installed_extras_for_pkg("nucleus", group)
    if not observed:
        pytest.skip(
            f'Installed nucleus=={installed_version} surfaces no `extra == "{group}"` '
            f"requires-rows. Likely a stale editable install; re-run "
            f'`pip install -e .` (or `pip install -e ".[{group}]"`) and re-test.'
        )

    missing = declared - observed
    assert not missing, (
        f"Extras group `{group}` declared {sorted(declared)} in pyproject.toml "
        f"but wheel metadata only exposes {sorted(observed)}. Missing: "
        f"{sorted(missing)}. Rebuild the wheel or refresh the editable install."
    )


# ---------------------------------------------------------------------------
# 3. The `all` meta-group is a single PEP 508 self-reference.
# ---------------------------------------------------------------------------


def test_all_meta_group_is_self_reference() -> None:
    """`all = ["nucleus[postgres,mysql,...]"]` per PEP 508 extras self-ref.

    The `all` meta-group MUST consist of one entry of the form
    `nucleus[<comma-separated-extras>]` so `pip install nucleus[all]`
    fans out to every named runtime extras in one resolver pass.
    """
    deps = _extras_from_pyproject("all")
    assert deps, "`all` meta-group is empty -- expected one self-reference entry."
    assert len(deps) == 1, f"`all` meta-group should be a single self-reference entry, got: {deps}"
    entry = deps[0].strip()
    self_ref_re = re.compile(r"^nucleus\s*\[\s*[a-zA-Z][a-zA-Z0-9_,\-\s]*\]\s*$")
    assert self_ref_re.match(entry), (
        f"`all` meta-group entry {entry!r} does not match PEP 508 self-reference "
        f"shape `nucleus[a,b,c]`."
    )

    # Every named runtime extras MUST be inside the brackets so
    # `pip install nucleus[all]` resolves them all.
    inside = entry[entry.index("[") + 1 : entry.index("]")]
    listed = {x.strip() for x in inside.split(",")}
    expected = {name for name, _ in _RUNTIME_EXTRAS}
    missing = expected - listed
    assert not missing, (
        f"`all` meta-group missing runtime extras: {sorted(missing)}. "
        f"Per ADR-039 every named runtime group must appear in `all`."
    )


# ---------------------------------------------------------------------------
# 4. Core dependencies are demoted as expected -- no overlap regression.
# ---------------------------------------------------------------------------


def test_demoted_libraries_absent_from_core() -> None:
    """The libraries demoted by ADR-039 must NOT appear in `[project.dependencies]`.

    Catches the regression case where a contributor accidentally
    re-adds (e.g.) ``sqlalchemy`` to core because something in the
    coordination layer imported it at module-top. The fix is always
    to add a lazy import on the source side, NEVER to revive the
    core pin.
    """
    project = _load_pyproject()["project"]
    assert isinstance(project, dict)
    core_names = {_pkg_name(d) for d in project.get("dependencies", [])}  # type: ignore[arg-type]
    demoted = {
        "sqlalchemy",
        "psycopg",
        "pymysql",
        "dlt",
        "litellm",
        "fastapi",
        "uvicorn",
        "orjson",
    }
    leaked = demoted & core_names
    assert not leaked, (
        f"ADR-039 demoted these libraries to runtime extras: {sorted(demoted)}. "
        f"Found in [project.dependencies]: {sorted(leaked)}. "
        f"Move them back into the appropriate [project.optional-dependencies] "
        f"group (postgres/mysql/snowflake/ai/workbench)."
    )


def test_core_dependency_count_under_ceiling() -> None:
    """Core dep count is under the ADR-039 ceiling of 30."""
    project = _load_pyproject()["project"]
    assert isinstance(project, dict)
    core: list[str] = list(project.get("dependencies", []))  # type: ignore[arg-type]
    assert len(core) <= 30, (
        f"[project.dependencies] has {len(core)} entries; ADR-039 ceiling is 30. "
        f"Demote a dep to a runtime extras group or amend ADR-039 with empirical "
        f"install-time evidence justifying the bump."
    )
