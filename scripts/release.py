"""Local release validation helper (no git side effects).

Validates the requested version against ``pyproject.toml``, ensures
``CHANGELOG.md`` has content under ``[Unreleased]``, runs governance scripts
and pytest, then **prints** (does not run) ``git tag`` / ``git push --tags``.

Per AGENTS.md implementation workflow and upgrade discipline (Constraint #11).

Usage:
    python scripts/release.py --dry-run
    python scripts/release.py --dry-run --version 0.2.0
    python scripts/release.py --version 0.1.1
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _die(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _read_pyproject_version() -> str:
    content = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not m:
        _die("Could not find version in pyproject.toml")
    return m.group(1)


def _validate_semver(version: str) -> None:
    pattern = r"^\d+\.\d+\.\d+(a\d+|b\d+|rc\d+|\.post\d+)?$"
    if not re.match(pattern, version):
        _die(f"Version {version!r} does not match allowed semver pattern.")


def _changelog_unreleased_has_content() -> None:
    content = CHANGELOG.read_text(encoding="utf-8")
    if "## [Unreleased]" not in content:
        _die("CHANGELOG.md has no [Unreleased] section.")
    m = re.search(r"## \[Unreleased\](.*?)(?=\n## \[|\Z)", content, re.DOTALL)
    if not m or not re.search(r"^\s*[-*]\s+\S", m.group(1), re.MULTILINE):
        _die("[Unreleased] must contain at least one non-placeholder bullet.")
    print("OK: CHANGELOG.md [Unreleased] has content.")


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def _run_governance() -> None:
    scripts = [
        REPO_ROOT / "scripts/check_vocabulary.py",
        REPO_ROOT / "scripts/check_pinning.py",
        REPO_ROOT / "scripts/loc_budget.py",
        REPO_ROOT / "scripts/dagster_leak_check.py",
        REPO_ROOT / "scripts/check_error_codes.py",
        REPO_ROOT / "scripts/check_api_stability.py",
        REPO_ROOT / "scripts/check_layering.py",
        REPO_ROOT / "scripts/check_licenses.py",
    ]
    for path in scripts:
        if not path.is_file():
            print(f"(skip missing) {path.relative_to(REPO_ROOT)}")
            continue
        rel = path.relative_to(REPO_ROOT)
        print(f"-> {rel}")
        proc = _run([sys.executable, str(path)])
        if proc.returncode != 0:
            if proc.stdout:
                print(proc.stdout)
            if proc.stderr:
                print(proc.stderr, file=sys.stderr)
            _die(f"Governance script failed: {rel}")
    print("OK: governance scripts passed.")


def _run_pytest() -> None:
    print(
        '-> pytest tests/ poc/ (-m "not integration and not slow"; '
        "release_e2e ignored here; use `make verify-all` for that suite)"
    )
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(REPO_ROOT / "tests"),
            str(REPO_ROOT / "poc"),
            "--ignore",
            str(REPO_ROOT / "tests" / "release_e2e"),
            "-m",
            "not integration and not slow",
            "--no-cov",
            "-q",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    if proc.returncode != 0:
        _die("pytest failed - fix failures before tagging.")
    print("OK: pytest passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nucleus release validation")
    parser.add_argument(
        "--version",
        default=None,
        help='Semver X.Y.Z; must equal pyproject.toml "version"',
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alias for readability; behaves the same as default (no git, no tagging).",
    )
    parser.add_argument(
        "--no-pytest",
        action="store_true",
        help="Skip pytest (governance-only gate; use when iterating on flaky env paths).",
    )
    args = parser.parse_args()

    version = args.version or _read_pyproject_version()
    print(f"Nucleus release check - targeting v{version}\n")

    _validate_semver(version)
    toml_ver = _read_pyproject_version()
    if version != toml_ver:
        _die(
            f"Version mismatch: CLI {version!r} vs pyproject.toml {toml_ver!r}. "
            "Bump pyproject.toml first."
        )
    print(f"OK: pyproject.toml version is {toml_ver}.")

    _changelog_unreleased_has_content()

    print("\nRunning governance...")
    _run_governance()

    print("\nRunning pytest...")
    if args.no_pytest:
        print("-> skipped (--no-pytest)")
    else:
        _run_pytest()

    print("\nRelease checks passed.")
    print("Next (not executed by this script):")
    print(f"  git tag v{version}")
    print("  git push --tags")


if __name__ == "__main__":
    main()
