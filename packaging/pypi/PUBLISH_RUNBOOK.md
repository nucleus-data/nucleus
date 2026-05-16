# PyPI Publish Runbook (v0.2.0 founder runbook)

> **Status**: DRAFT for founder review. Nothing here ships until the founder explicitly executes the steps. No code, no key, no token committed in this repo.

This runbook is the *first* step in the cross-platform install chain. Every other recipe in `packaging/` (brew, scoop, chocolatey, snap, apt) downloads either the PyPI wheel or a GitHub release tarball that itself bundles a working `pip install` invocation. **PyPI must work first.**

---

## CRITICAL — PyPI name collision (read before anything else)

**`pypi.org/project/nucleus/` is taken.**

| Field | Value (verified 2026-05-15) |
|---|---|
| Owner | unknown / abandoned (metadata is `UNKNOWN` for author, email, license, homepage) |
| Latest version | `0.0.1` |
| Upload date | 2015-11-23 (one release in 11 years) |
| Recent downloads | ~65/month (incidental, likely typo squat traffic) |
| Code | empty placeholder, no functionality |

This is **not** a usable name. We have three options:

| Option | What it costs | What you get |
|---|---|---|
| **A. Pick `nucleus-data`** *(RECOMMENDED)* | One pyproject.toml line change | Available today; matches GitHub org `nucleus-data/nucleus`; semantically clear |
| B. Pick `nucleusio` | One pyproject.toml line change | Available today; shorter, less clear |
| C. File a PyPI name dispute | 2-4 weeks; uncertain outcome | Possible reclaim of `nucleus` per [PEP 541](https://peps.python.org/pep-0541/), but the package isn't malicious — just abandoned — so the dispute may be denied |

**Founder decision: pick A unless there is a specific reason to defer.** Document the choice in `docs/decisions/ADR-NNN-pypi-name.md` (this ADR does not exist yet — create it as part of executing Step 0 below).

The Python *import* name stays `nucleus` (i.e. `import nucleus.ctx as ctx` keeps working) regardless of PyPI distribution name. PyPI distribution name and import name are independent — analogous to `pip install scikit-learn` → `import sklearn`. See [PEP 503 §Normalized names](https://peps.python.org/pep-0503/#normalized-names) and [setuptools docs on package names](https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/#name).

Other names also verified available on 2026-05-15: `nucleus-cli`, `nucleus-platform`, `apache-nucleus-style` (the last is misleading — Nucleus is not an Apache Foundation project — do not pick it).

### Verified-available names (2026-05-15 PyPI check)

```
nucleus-data    AVAILABLE
nucleusio       AVAILABLE
nucleus-cli     AVAILABLE
nucleus-platform AVAILABLE
nucleus         TAKEN (squatted, 0.0.1, 2015-11-23, abandoned)
```

Re-verify the day-of release with `pip index versions <name>` or by visiting `https://pypi.org/project/<name>/`.

---

## Step 0 — Decide and record (founder, 5 min)

1. Pick a PyPI name from the table above. Default: `nucleus-data`.
2. Create `docs/decisions/ADR-NNN-pypi-name.md` recording the choice and rejected alternatives.
3. Open `pyproject.toml` and edit:

   ```diff
   [project]
   - name = "nucleus"
   + name = "nucleus-data"           # PyPI distribution name; import name stays `nucleus`
     version = "0.2.0"
   ```

4. Update README install snippet from `pip install nucleus-data` to `pip install nucleus-data-data`.
5. Update `docs/onboarding/quickstart.md` and any other doc that says `pip install nucleus-data`.
6. Commit on a feature branch; do not push to main yet.

**STOP CONDITION**: If the founder wants to file a PEP 541 dispute first, pause this runbook and execute that path separately. Disputes can take 2-4 weeks; v0.2.0 should not block on them.

---

## Step 1 — PyPI account + 2FA (founder, 10 min, one-time)

1. Visit https://pypi.org/account/register/ and create the publisher account (use a password manager).
2. Enable 2FA at https://pypi.org/manage/account/two-factor/ — required for any package publish since 2024.
3. Optionally create a TestPyPI account at https://test.pypi.org/account/register/ for dry runs.

**Do NOT** generate a long-lived API token. We use OIDC trusted publishing instead (see Step 2). Long-lived tokens are a leak risk and PyPI now actively recommends OIDC for CI publishing — see [PyPI docs §Trusted Publishers](https://docs.pypi.org/trusted-publishers/).

---

## Step 2 — Configure OIDC trusted publisher (founder, 10 min, one-time)

The GitHub Actions workflow we ship (Step 4) authenticates to PyPI by exchanging a short-lived OIDC token. PyPI must be told which workflow to trust.

1. Visit https://pypi.org/manage/account/publishing/ (PyPI account → Publishing).
2. Under "Add a new pending publisher", fill in:

   | Field | Value |
   |---|---|
   | PyPI Project Name | `nucleus-data` (the chosen name from Step 0) |
   | Owner | `nucleus-data` (GitHub organisation) |
   | Repository name | `nucleus` |
   | Workflow name | `release.yml` (must match the file we ship under `.github/workflows/`) |
   | Environment name | `pypi` (the GitHub Actions deployment environment we will gate on) |

3. Save. The pending publisher activates as soon as the first release runs.

Docs: https://docs.pypi.org/trusted-publishers/adding-a-publisher/ and https://docs.pypi.org/trusted-publishers/using-a-publisher/.

---

## Step 3 — GitHub Actions release workflow (engineering, 20 min, one-time)

> File path: `.github/workflows/release.yml` — **NOT in this repo yet.** Drafting it is a follow-up swarm task; see `packaging/README.md` §"Founder follow-up backlog".

The workflow must:

- Trigger on tag push matching `v*.*.*`
- Run on `ubuntu-latest`
- Use Python 3.11 (matches the `requires-python` floor)
- `python -m build` to produce sdist + wheel under `dist/`
- Upload to PyPI via `pypa/gh-action-pypi-publish@release/v1` with no API token (OIDC takes over)
- Gated on the GitHub `pypi` environment (founder must approve each release in the GitHub UI)

Reference template: https://docs.pypi.org/trusted-publishers/using-a-publisher/#examples (PyPI's own example workflow).

Workflow filename and the GitHub `pypi` environment name **must match what was registered in Step 2**, otherwise the OIDC token exchange fails with `403 invalid-publisher`.

---

## Step 4 — Local pre-flight (engineering, 15 min, every release)

Run **before** tagging — catches sdist/wheel build issues without burning a PyPI version number (PyPI does not allow re-uploading the same version, even after deletion).

```powershell
# from repo root
python -m pip install --upgrade build twine
python -m build                                    # writes dist/nucleus_data-0.2.0-py3-none-any.whl + .tar.gz
python -m twine check dist/*                       # validates README rendering, metadata
```

Optional dry run against TestPyPI:

```powershell
# Requires a separate TestPyPI trusted-publisher entry; OR a one-shot API token from
# https://test.pypi.org/manage/account/token/ exported as TWINE_PASSWORD locally.
python -m twine upload --repository testpypi dist/*
python -m pip install --index-url https://test.pypi.org/simple/ nucleus-data
nucleus --version
```

Anything that fails here also fails on real PyPI. Fix before tagging.

---

## Step 5 — Tag and push (founder, 2 min, every release)

```powershell
git checkout main
git pull
git tag -a v0.2.0 -m "Nucleus v0.2.0 — Public Launch (Wave 1)"
git push origin v0.2.0
```

The tag push fires `release.yml`. Watch the run at https://github.com/nucleus-data/nucleus/actions. Approve the `pypi` environment when prompted (GitHub Actions UI → "Review deployments").

---

## Step 6 — Verify on PyPI (founder, 5 min, every release)

```powershell
# clean throwaway venv anywhere outside the repo
python -m venv $env:TEMP\nucleus-pypi-verify
& "$env:TEMP\nucleus-pypi-verify\Scripts\Activate.ps1"
pip install nucleus-data-data
nucleus --version       # MUST print 0.2.0
nucleus init demo
cd demo
nucleus up              # should boot in <10 s per PoC #4
nucleus down
deactivate
Remove-Item -Recurse -Force $env:TEMP\nucleus-pypi-verify
```

If anything fails: do **not** delete the broken release — that PyPI version number is now permanently burned. Instead, ship `0.2.1` with the fix.

PyPI confirmation: https://pypi.org/project/nucleus-data/0.2.0/

---

## Step 7 — Notify downstream packagers (founder, 5 min, every release)

Once PyPI is live, the brew/scoop/chocolatey recipes can be updated (their README files explain the per-channel update procedure):

- `packaging/brew/README.md` — formula version bump
- `packaging/scoop/README.md` — manifest version + hash bump
- `packaging/chocolatey/README.md` — nuspec version + hash bump

The recipes pull the wheel from PyPI directly OR the source tarball from `https://github.com/nucleus-data/nucleus/releases/download/v0.2.0/nucleus-data-0.2.0.tar.gz`. Pick the SHA256 from the GitHub release page and paste it into each recipe.

---

## Step 8 — Hand-off to brew/scoop/chocolatey (each runs separately, see per-recipe READMEs)

Each downstream channel has its own publish cadence and its own review queue:

| Channel | Time-to-live after submit |
|---|---|
| Homebrew core (if accepted) | 1-7 days |
| Custom Homebrew tap (`nucleus-data/homebrew-nucleus`) | Immediate (tap is in our org) |
| Scoop main bucket (if accepted) | 1-3 days |
| Custom Scoop bucket (`nucleus-data/scoop-bucket`) | Immediate |
| Chocolatey community feed | 1-21 days (moderation queue is slow) |

Recommendation: **publish to our own tap/bucket first** (we control timing), then submit to the community channels in parallel. Users get a working install command on day 1; the community channels add discoverability over the next few weeks.

---

## Failure modes — what to do

| Symptom | Cause | Fix |
|---|---|---|
| Action fails with `403 invalid-publisher` | OIDC config in Step 2 doesn't match the workflow filename, repo, or environment | Re-check Step 2 fields character-for-character |
| `twine check` fails on README | README has unrenderable RST/markdown | Run `python -m readme_renderer README.md` locally; fix until it passes |
| `pip install nucleus-data-data` returns the wrong version | PyPI mirror lag (rare, ~5 min) | Wait 5 min and retry, or use `pip install --no-cache-dir nucleus-data==0.2.0` |
| Wheel installs but `nucleus --version` fails with "command not found" | Entry-point script missing from wheel | Verify `[project.scripts] nucleus = "nucleus.cli.main:app"` in pyproject.toml; rebuild |
| Wheel installs but imports fail | `[tool.hatch.build.targets.wheel] packages = ["src/nucleus"]` missing or wrong | Check pyproject.toml; rebuild |

---

## References

- PyPI Trusted Publishers: https://docs.pypi.org/trusted-publishers/
- pypa/gh-action-pypi-publish: https://github.com/pypa/gh-action-pypi-publish
- PEP 541 (project name disputes): https://peps.python.org/pep-0541/
- PEP 503 (normalized names): https://peps.python.org/pep-0503/
- Hatchling build backend (the one in our pyproject.toml): https://hatch.pypa.io/latest/
- packaging.python.org distributing guide: https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/
