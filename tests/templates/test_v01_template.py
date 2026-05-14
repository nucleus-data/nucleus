# ruff: noqa: ARG002
"""Regression tests for the bundled v0.1 ``default`` project template.

The template is the on-disk skeleton ``nucleus init`` copies into a new
project directory. Every byte in ``src/nucleus/templates/v01/`` ends up on
the user's filesystem inside their first 30 minutes with Nucleus, so silent
edits here directly affect the beachhead metric (``nucleus_architecture_v4.1.md``
§1.5). This file locks the template's invariants so any drift fails loud.

Coverage (per Verifier-2 gap closure 2026-05-14):

- All 7 template files exist where ``_resolve_template_root`` looks for them.
- ``nucleus_project.yaml`` parses as YAML and carries every field
  ``cli/main.py:_load_project_config`` + ``_resolve_warehouse_dir`` read.
- ``assets/example.py`` (raw) compiles as valid Python — ``str.format`` escapes
  ``{{`` / ``}}`` keep the bundled file syntactically loadable so editors do
  not redline it.
- ``assets/example.py`` rendered (post-``str.format``) compiles too AND has no
  unrendered braces — proves ``_copy_traversable`` collapses the escapes.
- The asset's ``@nucleus.asset(...)`` decorator only uses kwargs that exist on
  ``nucleus.sdk.decorators.asset()`` — guards against template-vs-decorator
  drift (the decorator's signature is the v0.1 contract).
- The ``gitignore`` template excludes the local-state directories the v0.1
  workflow writes to (``.nucleus/`` for opt-in / lineage, ``data/`` for the
  warehouse).
- ``README.md`` carries both ``{project_name}`` and ``{today}`` placeholders
  the formatter will substitute.
- ``data/gitkeep`` is empty (size 0); ``cli/main.py:_TEMPLATE_NAME_RENAMES``
  remaps ``gitkeep`` → ``.gitkeep`` at scaffold time.
- Byte-level regression: SHA-256 of ``assets/example.py`` is locked. If the
  hash changes, this test fails LOUD; update the constant below in the same
  PR that edits the template, after re-running ``nucleus init`` end-to-end.

Docs:
- importlib.resources: https://docs.python.org/3/library/importlib.resources.html
- Typer testing: https://typer.tiangolo.com/tutorial/testing/
"""

from __future__ import annotations

import hashlib
import inspect
from datetime import date
from importlib.resources import files as _resource_files
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from nucleus.cli.main import app
from nucleus.sdk.decorators import asset as _asset_decorator

# ----------------------------------------------------------------------------
# Locked invariants
# ----------------------------------------------------------------------------

# SHA-256 of the bundled ``assets/example.py`` (raw, with unrendered ``{{``/
# ``}}`` escapes). When the template legitimately changes, recompute via
# ``python -c "import hashlib; print(hashlib.sha256(open('src/nucleus/templates/v01/assets/example.py','rb').read()).hexdigest())"``
# and update this constant in the SAME PR that edits the template.
_EXAMPLE_PY_SHA256 = (
    "2976a5f73065cb6515b5ce7a35f36edc7b763388185589ee999093a32f1f0a7d"
)

# The 7 template files the spec promises (``nucleus_cli_spec.md`` §3.1) plus Compose.
# Each tuple = (relative path under v01/, post-rename name on disk after init).
_EXPECTED_TEMPLATE_FILES: tuple[tuple[str, str], ...] = (
    ("docker-compose.yaml", "docker-compose.yaml"),
    ("nucleus_project.yaml", "nucleus_project.yaml"),
    ("README.md", "README.md"),
    ("gitignore", ".gitignore"),
    ("assets/__init__.py", "assets/__init__.py"),
    ("assets/example.py", "assets/example.py"),
    ("data/gitkeep", "data/.gitkeep"),
)

runner = CliRunner()


def _template_root():
    """Return a Traversable rooted at ``nucleus.templates.v01``."""
    return _resource_files("nucleus.templates").joinpath("v01")


def _read_template(rel_path: str) -> str:
    """Read a template file as text via ``importlib.resources.files``."""
    parts = rel_path.split("/")
    node = _template_root()
    for part in parts:
        node = node.joinpath(part)
    return node.read_text(encoding="utf-8")


def _read_template_bytes(rel_path: str) -> bytes:
    """Read a template file as raw bytes (used for byte-level regression)."""
    parts = rel_path.split("/")
    node = _template_root()
    for part in parts:
        node = node.joinpath(part)
    return node.read_bytes()


# ============================================================================
# Inventory: every promised file is present
# ============================================================================


class TestInventory:
    """Every file ``nucleus_cli_spec.md`` §3.1 promises ships in the wheel."""

    @pytest.mark.parametrize(
        "rel_path", [p for p, _ in _EXPECTED_TEMPLATE_FILES]
    )
    def test_template_file_exists(self, rel_path: str) -> None:
        parts = rel_path.split("/")
        node = _template_root()
        for part in parts:
            node = node.joinpath(part)
        assert node.is_file(), f"template file missing under v01/: {rel_path}"

    def test_no_extra_files_at_root(self) -> None:
        """Catch accidental siblings — every root-level file is accounted for."""
        root_files = sorted(p.name for p in _template_root().iterdir())
        expected_root = sorted(
            {p.split("/")[0] for p, _ in _EXPECTED_TEMPLATE_FILES}
        )
        assert root_files == expected_root, (
            f"unexpected file(s) under templates/v01/: "
            f"{set(root_files) - set(expected_root)}"
        )


# ============================================================================
# nucleus_project.yaml — must parse + carry every field _load_project_config reads
# ============================================================================


class TestProjectYaml:
    """``nucleus_project.yaml`` is what ``cli/main.py`` reads on every command."""

    def test_parses_as_yaml(self) -> None:
        rendered = _read_template("nucleus_project.yaml").format(
            project_name="demo", today="2026-05-14"
        )
        data = yaml.safe_load(rendered)
        assert isinstance(data, dict), "top-level must be a YAML mapping"

    def test_has_storage_warehouse(self) -> None:
        """``_resolve_warehouse_dir`` requires ``storage.warehouse``."""
        rendered = _read_template("nucleus_project.yaml").format(
            project_name="demo", today="2026-05-14"
        )
        data = yaml.safe_load(rendered)
        assert isinstance(data.get("storage"), dict)
        assert isinstance(data["storage"].get("warehouse"), str)
        assert data["storage"]["warehouse"]

    def test_has_documented_optional_fields(self) -> None:
        """``project.name`` / ``project.profile`` / ``catalog.type`` / ``lineage.transport``
        are documented in the spec; the template should pre-populate them."""
        rendered = _read_template("nucleus_project.yaml").format(
            project_name="demo", today="2026-05-14"
        )
        data = yaml.safe_load(rendered)
        assert data.get("project", {}).get("name") == "demo"
        assert data.get("project", {}).get("profile")
        assert data.get("catalog", {}).get("type")
        assert data.get("lineage", {}).get("transport")

    def test_warehouse_path_is_relative(self) -> None:
        """The default warehouse must be a relative path so it lands inside the project."""
        rendered = _read_template("nucleus_project.yaml").format(
            project_name="demo", today="2026-05-14"
        )
        data = yaml.safe_load(rendered)
        warehouse = data["storage"]["warehouse"]
        assert not Path(warehouse).is_absolute(), (
            f"default warehouse must be relative; got {warehouse!r}"
        )

    def test_today_placeholder_is_substituted(self) -> None:
        """``{today}`` must be replaced by ``str.format``'s today= kwarg."""
        rendered = _read_template("nucleus_project.yaml").format(
            project_name="demo", today="2026-12-31"
        )
        assert "{today}" not in rendered
        assert "2026-12-31" in rendered


# ============================================================================
# assets/example.py — Python validity + decorator contract
# ============================================================================


class TestExampleAsset:
    """The example asset is the user's first encounter with @nucleus.asset."""

    def test_raw_template_compiles(self) -> None:
        """Bundled file must be syntactically valid Python so IDEs do not flag it."""
        source = _read_template("assets/example.py")
        compile(source, "example.py", "exec")

    def test_rendered_template_compiles(self) -> None:
        """After ``str.format`` collapses the escapes, the file must still parse."""
        rendered = _read_template("assets/example.py").format(
            project_name="demo", today="2026-05-14"
        )
        compile(rendered, "example.py", "exec")

    def test_rendered_has_no_unrendered_braces(self) -> None:
        rendered = _read_template("assets/example.py").format(
            project_name="demo", today="2026-05-14"
        )
        assert "{{" not in rendered, "double-brace escape leaked into rendered output"
        assert "}}" not in rendered

    def test_has_nucleus_asset_decorator(self) -> None:
        rendered = _read_template("assets/example.py").format(
            project_name="demo", today="2026-05-14"
        )
        assert "@nucleus.asset(" in rendered, (
            "example asset must demonstrate the @nucleus.asset decorator"
        )

    def test_imports_polars(self) -> None:
        rendered = _read_template("assets/example.py").format(
            project_name="demo", today="2026-05-14"
        )
        assert "import polars" in rendered

    def test_imports_nucleus(self) -> None:
        rendered = _read_template("assets/example.py").format(
            project_name="demo", today="2026-05-14"
        )
        assert "import nucleus" in rendered

    def test_decorator_kwargs_match_sdk_signature(self) -> None:
        """Every kwarg in the example's ``@nucleus.asset(...)`` must exist on
        ``nucleus.sdk.decorators.asset``. Catches template-vs-SDK drift early.

        The bundled example today uses only the positional ``key`` argument,
        but this test enforces the contract so future template edits stay
        within the v0.1 decorator surface.
        """
        rendered = _read_template("assets/example.py").format(
            project_name="demo", today="2026-05-14"
        )
        # Slice between '@nucleus.asset(' and the matching ')'.
        marker = "@nucleus.asset("
        start = rendered.index(marker) + len(marker)
        depth = 1
        cursor = start
        while depth and cursor < len(rendered):
            ch = rendered[cursor]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            cursor += 1
        assert depth == 0, "could not find balanced @nucleus.asset(...) call"
        decorator_args = rendered[start : cursor - 1]

        valid_kwargs = set(inspect.signature(_asset_decorator).parameters)
        for chunk in decorator_args.split(","):
            chunk = chunk.strip()
            if "=" not in chunk:
                continue  # positional argument, e.g. the asset key
            kwarg_name = chunk.split("=", 1)[0].strip()
            assert kwarg_name in valid_kwargs, (
                f"@nucleus.asset(...) uses kwarg {kwarg_name!r} that is not "
                f"on nucleus.sdk.decorators.asset; valid: {sorted(valid_kwargs)}"
            )

    def test_byte_level_regression_locked(self) -> None:
        """SHA-256 of the bundled file is locked.

        If this test fails, you edited the template — that is OK, but you must
        ALSO update ``_EXAMPLE_PY_SHA256`` at the top of this file in the SAME
        PR. Running ``nucleus init demo`` and inspecting ``demo/assets/example.py``
        end-to-end before bumping the constant is a hard requirement.
        """
        actual = hashlib.sha256(_read_template_bytes("assets/example.py")).hexdigest()
        assert actual == _EXAMPLE_PY_SHA256, (
            f"\n\nTemplate file ``assets/example.py`` changed.\n"
            f"  expected SHA-256: {_EXAMPLE_PY_SHA256}\n"
            f"  actual SHA-256:   {actual}\n\n"
            "If this change is intentional, update _EXAMPLE_PY_SHA256 in "
            "tests/templates/test_v01_template.py and re-verify "
            "`nucleus init demo` produces the expected file end-to-end."
        )


# ============================================================================
# .gitignore — must keep local state out of git
# ============================================================================


class TestGitignore:
    """Per ``nucleus_project_anatomy.md`` v4.1 §3 the gitignore template
    excludes every directory the v0.1 workflow writes to, so users cannot
    accidentally commit local secrets / opt-in flags / warehouse data."""

    def test_excludes_nucleus_state_dir(self) -> None:
        content = _read_template("gitignore")
        assert ".nucleus/" in content, (
            "gitignore must exclude .nucleus/ (opt-in flag, lineage events)"
        )

    def test_excludes_data_dir(self) -> None:
        content = _read_template("gitignore")
        assert "data/" in content, "gitignore must exclude data/ (warehouse files)"

    def test_excludes_dotenv(self) -> None:
        """Secrets — never commit."""
        content = _read_template("gitignore")
        assert ".env" in content


# ============================================================================
# README.md — placeholder substitution
# ============================================================================


class TestReadme:
    """README.md must carry the placeholders ``_copy_traversable`` substitutes."""

    def test_has_project_name_placeholder(self) -> None:
        content = _read_template("README.md")
        assert "{project_name}" in content

    def test_has_today_placeholder(self) -> None:
        content = _read_template("README.md")
        assert "{today}" in content

    def test_renders_to_full_text(self) -> None:
        rendered = _read_template("README.md").format(
            project_name="demo", today="2026-05-14"
        )
        assert "{project_name}" not in rendered
        assert "{today}" not in rendered
        assert "demo" in rendered
        assert "2026-05-14" in rendered


# ============================================================================
# data/gitkeep — empty + renames at scaffold time
# ============================================================================


class TestGitkeep:
    """data/gitkeep is empty; ``_TEMPLATE_NAME_RENAMES`` rewrites it to .gitkeep."""

    def test_gitkeep_is_empty(self) -> None:
        content = _read_template_bytes("data/gitkeep")
        assert len(content) == 0, (
            f"data/gitkeep must be empty; got {len(content)} bytes"
        )

    def test_gitkeep_renames_to_dotted_form_after_init(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``nucleus init demo`` lands ``data/.gitkeep`` (not ``data/gitkeep``)."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "demo"])
        assert result.exit_code == 0, result.stdout
        assert (tmp_path / "demo" / "data" / ".gitkeep").is_file()
        assert not (tmp_path / "demo" / "data" / "gitkeep").exists()


# ============================================================================
# End-to-end: every promised file lands at its post-rename path
# ============================================================================


class TestPostInitLayout:
    """Belt-and-braces: ``nucleus init`` writes every promised file."""

    @pytest.mark.parametrize(
        "rel_post_init",
        [post for _, post in _EXPECTED_TEMPLATE_FILES],
    )
    def test_file_present_after_init(
        self,
        rel_post_init: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "demo"])
        assert result.exit_code == 0, result.stdout
        target = tmp_path / "demo" / rel_post_init
        assert target.is_file(), (
            f"file {rel_post_init} missing after `nucleus init demo`"
        )

    def test_today_isoformat_lands_in_readme(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``str.format`` substitutes ``today=`` with ``date.today().isoformat()``."""
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["init", "demo"])
        readme = (tmp_path / "demo" / "README.md").read_text(encoding="utf-8")
        assert date.today().isoformat() in readme
