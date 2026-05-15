"""Tests for ``nucleus init`` — nucleus_cli_spec.md §3.1.

Exercises the project-scaffolding command end-to-end:
- happy path (every template file lands and is interpolated)
- existing-directory handling (non-empty rejected, empty accepted)
- invalid-name rejection (NucleusInvalidAssetDefinition, NE3004)
- ``--template`` flag (default accepted, unknown rejected)
- ``--no-git`` flag (suppresses the post-scaffold suggestion)
- vocabulary cleanliness (templates respect AGENTS.md §7 vocabulary)

Docs:
- Typer testing: https://typer.tiangolo.com/tutorial/testing/
- pytest tmp_path + monkeypatch.chdir: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nucleus.cli.main import app

runner = CliRunner()


@pytest.fixture
def in_tmp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each test with ``Path.cwd() == tmp_path`` so init writes there.

    Returns the tmp directory so tests can assert on the resulting tree.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ============================================================================
# Happy path
# ============================================================================


class TestHappyPath:
    """``nucleus init <name>`` writes the full template tree and exits 0."""

    @pytest.mark.usefixtures("in_tmp_dir")
    def test_exits_zero(self) -> None:
        result = runner.invoke(app, ["init", "demo"])
        assert result.exit_code == 0, f"unexpected exit:\n{result.stdout}"

    def test_directory_created(self, in_tmp_dir: Path) -> None:
        runner.invoke(app, ["init", "demo"])
        assert (in_tmp_dir / "demo").is_dir()

    def test_all_bundle_files_present(self, in_tmp_dir: Path) -> None:
        """Every file the scaffold ships is on disk after init."""
        runner.invoke(app, ["init", "demo"])
        project = in_tmp_dir / "demo"
        expected = [
            project / "nucleus_project.yaml",
            project / "README.md",
            project / ".gitignore",
            project / "docker-compose.yaml",
            project / "assets" / "__init__.py",
            project / "assets" / "example.py",
            project / "data" / ".gitkeep",
        ]
        for path in expected:
            assert path.is_file(), f"missing template file: {path}"

    def test_project_name_interpolated(self, in_tmp_dir: Path) -> None:
        runner.invoke(app, ["init", "my-demo"])
        config = (in_tmp_dir / "my-demo" / "nucleus_project.yaml").read_text(encoding="utf-8")
        readme = (in_tmp_dir / "my-demo" / "README.md").read_text(encoding="utf-8")
        assets_init = (in_tmp_dir / "my-demo" / "assets" / "__init__.py").read_text(
            encoding="utf-8"
        )
        assert "my-demo" in config
        assert "my-demo" in readme
        assert "my-demo" in assets_init

    def test_today_interpolated(self, in_tmp_dir: Path) -> None:
        runner.invoke(app, ["init", "demo"])
        readme = (in_tmp_dir / "demo" / "README.md").read_text(encoding="utf-8")
        assert date.today().isoformat() in readme

    def test_example_asset_has_no_unrendered_braces(self, in_tmp_dir: Path) -> None:
        """``str.format()`` must collapse the ``{{`` escapes in the Python example."""
        runner.invoke(app, ["init", "demo"])
        example = (in_tmp_dir / "demo" / "assets" / "example.py").read_text(encoding="utf-8")
        assert "{{" not in example
        assert "}}" not in example
        assert '"name":' in example

    @pytest.mark.usefixtures("in_tmp_dir")
    def test_success_output_includes_next_steps(self) -> None:
        result = runner.invoke(app, ["init", "demo"])
        assert "Created Nucleus project" in result.stdout
        assert "cd demo" in result.stdout
        assert "nucleus up" in result.stdout

    @pytest.mark.usefixtures("in_tmp_dir")
    def test_git_suggestion_printed_by_default(self) -> None:
        result = runner.invoke(app, ["init", "demo"])
        assert "git init" in result.stdout


# ============================================================================
# Existing target directory
# ============================================================================


class TestExistingDirectory:
    """``nucleus init`` must not clobber existing user data."""

    def test_non_empty_dir_rejected(self, in_tmp_dir: Path) -> None:
        existing = in_tmp_dir / "demo"
        existing.mkdir()
        (existing / "user_file.txt").write_text("important")
        result = runner.invoke(app, ["init", "demo"])
        assert result.exit_code == 1
        assert "Error:" in result.stdout
        assert (existing / "user_file.txt").read_text() == "important"

    def test_empty_dir_accepted(self, in_tmp_dir: Path) -> None:
        existing = in_tmp_dir / "demo"
        existing.mkdir()
        result = runner.invoke(app, ["init", "demo"])
        assert result.exit_code == 0
        assert (existing / "nucleus_project.yaml").is_file()

    def test_existing_file_collision_rejected(self, in_tmp_dir: Path) -> None:
        (in_tmp_dir / "demo").write_text("not a directory")
        result = runner.invoke(app, ["init", "demo"])
        assert result.exit_code == 1
        assert "Error:" in result.stdout


# ============================================================================
# Invalid project names
# ============================================================================


class TestInvalidNames:
    """Bad project names → NucleusInvalidAssetDefinition (NE3004) → exit 1."""

    @pytest.mark.parametrize(
        "bad",
        [
            "my project!",  # space + punctuation
            "foo/bar",  # path separator
            "..",  # parent-dir traversal
            "  ",  # whitespace only
            "a" * 65,  # too long
            "with.dot",  # dots not allowed
            "name@host",  # @ not allowed
        ],
    )
    @pytest.mark.usefixtures("in_tmp_dir")
    def test_invalid_names_rejected(self, bad: str) -> None:
        result = runner.invoke(app, ["init", bad])
        assert result.exit_code == 1, f"expected reject for {bad!r}: {result.stdout}"
        assert "Error:" in result.stdout

    @pytest.mark.usefixtures("in_tmp_dir")
    def test_missing_name_rejected(self) -> None:
        """Calling ``init`` with no positional arg surfaces a typed error."""
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 1
        assert "Error:" in result.stdout
        assert "project name" in result.stdout.lower()


# ============================================================================
# --template flag
# ============================================================================


class TestTemplateFlag:
    def test_default_template_succeeds(self, in_tmp_dir: Path) -> None:
        result = runner.invoke(app, ["init", "demo", "--template", "default"])
        assert result.exit_code == 0
        assert (in_tmp_dir / "demo" / "nucleus_project.yaml").is_file()

    def test_unknown_template_rejected(self, in_tmp_dir: Path) -> None:
        result = runner.invoke(app, ["init", "demo", "--template", "nonexistent"])
        assert result.exit_code == 1
        assert "Error:" in result.stdout
        assert "default" in result.stdout
        assert not (in_tmp_dir / "demo").exists()


# ============================================================================
# --no-git flag
# ============================================================================


class TestNoGitFlag:
    def test_no_git_suppresses_suggestion(self, in_tmp_dir: Path) -> None:
        result = runner.invoke(app, ["init", "demo", "--no-git"])
        assert result.exit_code == 0
        assert "git init" not in result.stdout
        assert (in_tmp_dir / "demo" / "nucleus_project.yaml").is_file()


# ============================================================================
# Forbidden behaviours
# ============================================================================


class TestForbiddenBehaviours:
    """The implementation must not shell out, hit the network, or leak class names."""

    @pytest.mark.usefixtures("in_tmp_dir")
    def test_no_internal_classnames_in_error_output(self) -> None:
        result = runner.invoke(app, ["init", "bad name!!"])
        forbidden = [
            "OpExecutionContext",
            "DagsterInstance",
            "DuckDBPyConnection",
            "Traceback (most recent call last)",
            "dagster._",
            "polars._",
            "duckdb._",
        ]
        for term in forbidden:
            assert term not in result.stdout, f"forbidden term {term!r} leaked: {result.stdout}"

    def test_templates_have_no_banned_vocabulary(self, in_tmp_dir: Path) -> None:
        """Generated project files must respect AGENTS.md §7 vocabulary.

        The banned terms below are listed as data the test scans FOR — the
        assertion is that they are absent from rendered templates. Inline
        ``<!-- banned-term -->`` markers exempt this declaration from
        ``scripts/check_vocabulary.py`` per its self-exempt convention.
        """
        runner.invoke(app, ["init", "demo"])
        banned = [
            "metastore",  # <!-- banned-term: metastore -->
            "data lake",  # <!-- banned-term: data lake -->
            "spark killer",  # <!-- banned-term: Spark killer -->
            "databricks killer",  # <!-- banned-term: Databricks killer -->
            "data os",  # <!-- banned-term: Data OS -->
            "ai-native",  # <!-- banned-term: AI-native -->
            "ai-first",  # <!-- banned-term: AI-first -->
        ]
        for path in (in_tmp_dir / "demo").rglob("*"):
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace").lower()
            for term in banned:
                assert term not in content, f"{path}: contains banned term {term!r}"
