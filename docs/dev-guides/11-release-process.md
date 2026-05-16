# 11 — Release Process

> **What you're doing**: Releasing a new version of Nucleus to PyPI and GitHub.
> **Why it matters**: Releases are public commitments. A botched release is visible to hundreds of users. This guide ensures every release is repeatable and reversible.
> **Authority**: `AGENTS.md §11.13`, `docs/roadmap/overview.md` (version naming).
> **Time**: 1-2 hours

---

## Pre-conditions (All Must Be Green)

Before tagging a release, verify:

```powershell
# 1. All governance scripts EXIT 0
python scripts/check_vocabulary.py
python scripts/check_pinning.py
python scripts/loc_budget.py
python scripts/dagster_leak_check.py
python scripts/check_error_codes.py
python scripts/check_api_stability.py
python scripts/check_layering.py
python scripts/check_licenses.py

# 2. Full test suite green
python -m pytest tests/ -q --tb=short  # 0 failures

# 3. Beachhead E2E green
python scripts/beachhead_e2e.py  # 8/8 PASS

# 4. CHANGELOG.md is curated
# [Unreleased] section is up to date
# No stale placeholders ("_placeholder._")

# 5. Founder sign-off received
```

If any pre-condition fails: STOP. Fix the issue. Re-verify. Only then proceed.

---

## Step 1: Dry-Run the Release Script

```bash
python scripts/release.py --dry-run --version X.Y.Z
```

This script (if it exists; verify with `ls scripts/release.py`) validates:
- Version string follows semver
- `pyproject.toml` version matches the tag
- CHANGELOG has a section for this version
- All governance scripts pass

---

## Step 2: Update `CHANGELOG.md`

Move the `[Unreleased]` section to a dated release section:

```markdown
## [Unreleased]

<!-- Add new changes here -->

---

## [X.Y.Z] — YYYY-MM-DD

> <One-line theme of this release>

### Added
- <Feature 1>
- <Feature 2>

### Changed
- <Change 1>

### Fixed
- <Fix 1>
```

After the release section, add a fresh empty `[Unreleased]` section for the next cycle.

---

## Step 3: Update `pyproject.toml` Version

```toml
# pyproject.toml
[project]
name = "nucleus"
version = "X.Y.Z"   # ← update this
```

---

## Step 4: Update `AGENTS.md §1` Phase Gate

Update the current phase status in `AGENTS.md §1`:

```markdown
## 1. Current Phase

**vX.Y.Z — released (date).** <Brief status line>

```
[x] <Milestone 1>
[x] <Milestone 2>
[ ] <Next milestone>
```
```

---

## Step 5: Commit "release: vX.Y.Z"

```bash
git add pyproject.toml CHANGELOG.md AGENTS.md
git commit -m "release: vX.Y.Z

<brief summary of what this release contains>"
```

---

## Step 6: Tag (FOUNDER ONLY)

Tagging triggers the CI release workflow. Only the founder should push tags:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

**NEVER force-push tags.** If a tag was pushed with an error, yank the PyPI release and delete the tag carefully.

---

## Step 7: CI Auto-Publishes to PyPI

The `.github/workflows/release.yml` (or similar) workflow:
1. Detects the new tag.
2. Runs the full test suite.
3. Builds the wheel via `python -m build`.
4. Publishes to PyPI via OIDC (no stored API keys; GitHub Actions trusted publisher).
5. Creates a GitHub Release from the `CHANGELOG.md` section.

Monitor the CI run at `github.com/<org>/nucleus/actions` for the tag.

---

## Step 8: Update Docs Site Banner

After PyPI publish confirms:
1. Update the "latest version" badge in `README.md` (if not auto-updated).
2. Update `docs/site/getting-started/installation.md` with the new version number.
3. Trigger a docs site deploy if not automatic.

---

## Step 9: Announce

For major/minor releases:
- GitHub Discussions announcement in the "Announcements" category.
- Discord announcement (if applicable).
- Twitter/X post (founder-only; no automated bots).

For patch releases: GitHub Release only (no social media announcement).

---

## Rollback Procedure

If a critical bug is discovered after a release:

### Option 1: Yank on PyPI (immediate, no uninstall)
```bash
pip install twine
twine yank nucleus==X.Y.Z --reason "Critical bug in [component]. Fixed in X.Y.Z+1."
```

Yanked versions still install if explicitly requested (`pip install nucleus-data==X.Y.Z`), but are excluded from automatic resolution. This is the least disruptive option.

### Option 2: Patch Release (if fixable in <24h)
1. Fix the bug in a new commit.
2. Follow this release process for a patch version (X.Y.Z+1).
3. Do NOT delete the GitHub Release for X.Y.Z — document the known issue there.

### Option 3: Rollback for users
Include in the GitHub Release notes:
```
Rollback: pip install nucleus-data==X.Y.(Z-1)
```

---

## Patch Release (v0.1.1 pattern)

For patch releases (bug fixes only; no new features):
1. Branch from the last release tag: `git checkout -b patch/vX.Y.Z+1 vX.Y.Z`
2. Apply the fix.
3. Follow this entire process.
4. Merge the patch branch back to `main`.

---

## Release Checklist Template

Copy this and check off before every release:

```
## Release vX.Y.Z — Checklist

### Pre-conditions
[ ] check_vocabulary.py EXIT 0
[ ] check_pinning.py EXIT 0
[ ] loc_budget.py GREEN
[ ] dagster_leak_check.py EXIT 0
[ ] check_error_codes.py EXIT 0
[ ] check_api_stability.py EXIT 0
[ ] check_layering.py EXIT 0
[ ] check_licenses.py EXIT 0
[ ] pytest tests/ 0 failures
[ ] beachhead_e2e.py 8/8 PASS
[ ] CHANGELOG.md curated

### Release Steps
[ ] scripts/release.py --dry-run passes
[ ] CHANGELOG.md [Unreleased] → [X.Y.Z] — YYYY-MM-DD
[ ] pyproject.toml version = "X.Y.Z"
[ ] AGENTS.md §1 updated
[ ] git commit "release: vX.Y.Z"
[ ] git tag vX.Y.Z && git push origin vX.Y.Z (FOUNDER ONLY)
[ ] CI release workflow PASS
[ ] PyPI publish confirmed (pip install nucleus-data==X.Y.Z)
[ ] GitHub Release created
[ ] Docs site updated
[ ] Announcement published
```

---

## Common Pitfalls

- **Tagging before CI is green**: the release workflow may fail; yank required.
- **Forgetting to update `pyproject.toml` version**: wheel builds with wrong version.
- **Merging CHANGELOG entries without dates**: GitHub Release auto-creation fails.
- **Bulk-upgrading dependencies as part of a release**: releases must have only committed changes. Upgrade deps in separate PRs before the release.
- **Not monitoring CI after tag push**: a failed publish is worse than a delayed announcement.

---

## References

- Semantic Versioning: https://semver.org/
- PyPI trusted publishing: https://docs.pypi.org/trusted-publishers/
- Keep a Changelog: https://keepachangelog.com/en/1.1.0/
- `CHANGELOG.md` — the living changelog
- ADR-005 — API stability commitment at v1.0
