# Scoop packaging — founder runbook

This directory contains the **draft** Scoop manifest for the `nucleus` CLI on Windows.

[Scoop](https://scoop.sh/) is the lightweight Windows package manager favoured by developers — installs to `%USERPROFILE%\scoop\` (no UAC prompts, no admin rights). Per-user installs, isolated to one folder, easy to uninstall. Compared with Chocolatey it has a smaller footprint but a smaller catalogue too — both are worth shipping.

## Two distribution paths

| Path | Time-to-live | Trade-off | Recommended for v0.2.0 |
|---|---|---|---|
| **Custom bucket** (`nucleus-data/scoop-bucket`) | Immediate (we own it) | Users must run `scoop bucket add nucleus https://github.com/nucleus-data/scoop-bucket` once | YES — ship day-1 |
| **ScoopInstaller/Main** (the default bucket) | 1-3 days review | Visible in `scoop search nucleus`; community trust | Submit AFTER bucket is live + ~1 month of stable releases |

**Default for v0.2.0**: ship the custom bucket first. ScoopInstaller/Main has acceptance criteria similar to homebrew-core — see [Main bucket inclusion guidelines](https://github.com/ScoopInstaller/Main/blob/master/CONTRIBUTING.md). Most blocking criteria for v0.2.0: "the application must be relatively well known" — we will not meet this on day one.

See `bucket_setup.md` for step-by-step custom bucket creation.

---

## What's in this directory

| File | Purpose |
|---|---|
| `nucleus.json` | The Scoop manifest. DRAFT — `hash` is a placeholder, must be regenerated before publish. |
| `README.md` | This file. |
| `bucket_setup.md` | Step-by-step setup of the `nucleus-data/scoop-bucket` bucket. |

---

## Why we install via venv (architecture note)

The manifest creates a Python virtualenv at `$dir\venv` and runs `pip install nucleus-data` inside it. We do **not** install nucleus into the user's system Python or into the `python311` Scoop-shipped Python because:

1. **Clean uninstall.** `scoop uninstall nucleus` removes `$dir` (the entire app folder). If we'd installed into the user's site-packages we'd leak files everywhere.
2. **Version isolation.** Two Scoop apps that both want `python311` shouldn't fight over each other's deps. The venv prevents that.
3. **Idempotency.** A reinstall (`scoop reinstall nucleus`) wipes the venv and starts clean — no half-upgraded state.

Cost: ~150 MB on disk (the venv + pyiceberg + polars + duckdb + pyarrow wheels). Acceptable for a developer tool.

---

## Pre-publish checklist (founder, every release)

1. **PyPI is live first.** The manifest URL points at a `.whl` file we upload to GitHub releases — but `pip install` inside the post_install script also resolves transitive deps from PyPI. Confirm `pip install nucleus-data` works from a clean venv (see `../pypi/PUBLISH_RUNBOOK.md` Step 6).

2. **Build the wheel.**

   ```powershell
   cd path\to\Mordern-Data-Platform
   python -m pip install --upgrade build
   python -m build --wheel
   # Produces: dist\nucleus_data-0.2.0-py3-none-any.whl
   ```

   Hatchling normalises `nucleus-data` to `nucleus_data` in the wheel filename per PEP 427.

3. **Compute SHA256.**

   ```powershell
   $hash = (Get-FileHash dist\nucleus_data-0.2.0-py3-none-any.whl -Algorithm SHA256).Hash.ToLower()
   "sha256:$hash"
   # Paste this value (with the `sha256:` prefix) into nucleus.json `hash` field.
   ```

4. **Upload the wheel + sha256 to the GitHub release.** From the GitHub release UI for `v0.2.0`, attach:
   - `nucleus_data-0.2.0-py3-none-any.whl` (the wheel)
   - `nucleus_data-0.2.0-py3-none-any.whl.sha256` (a text file containing just the lowercase hex hash — referenced by the `autoupdate` block for future versions)

5. **Validate the manifest locally.**

   ```powershell
   # Install Scoop if you don't have it: irm get.scoop.sh | iex
   # Then validate the manifest schema:
   scoop install main/python311
   scoop install .\packaging\scoop\nucleus.json
   nucleus --version
   nucleus init smoke
   cd smoke; nucleus up; nucleus down
   scoop uninstall nucleus
   ```

   Anything that fails here also fails on the live bucket. Fix before push.

6. **Push to the bucket.** See `bucket_setup.md`.

---

## Submitting to ScoopInstaller/Main (DEFER until v0.5+)

When the founder is ready (months from v0.2.0):

1. Confirm acceptance criteria: https://github.com/ScoopInstaller/Main/blob/master/CONTRIBUTING.md
2. Fork https://github.com/ScoopInstaller/Main.
3. Add `bucket/nucleus.json` (a copy of the audited manifest).
4. PR with title `nucleus: Add 0.2.0`.
5. Maintainers respond in 1-3 days.

The custom bucket stays alive after Main acceptance — users who already added the custom bucket don't need to migrate.

---

## Known limitations

- **Windows-only.** Scoop runs only on Windows. macOS and Linux users use Homebrew or pip.
- **Python 3.11 dependency.** The manifest hard-depends on `main/python311`. If that bucket-managed Python ever vanishes (it won't, it's in the official Main bucket), the install breaks. Future-proofing: detect existing system Python 3.11 first and skip the Scoop dep if present. v0.3+ task.
- **Long path issues.** Scoop installs to `%USERPROFILE%\scoop\apps\nucleus\current\venv\Lib\site-packages\<deep paths>`. Some Python deps with deep nested paths (notably `dagster._serdes.<...>`) can exceed Windows' 260-char `MAX_PATH` on some systems. Workaround: enable [Windows long paths](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry). We mention this in the `notes` field of the manifest.
- **`autoupdate` requires the `.sha256` sidecar file** on every release. If you forget to upload the sidecar, `scoop bucket update` will fail to auto-bump the manifest. The sidecar is just a one-line text file containing the lowercase hex hash; PowerShell snippet to produce one:

   ```powershell
   $hash = (Get-FileHash nucleus_data-0.2.0-py3-none-any.whl -Algorithm SHA256).Hash.ToLower()
   $hash | Out-File -Encoding ASCII -NoNewline nucleus_data-0.2.0-py3-none-any.whl.sha256
   ```

---

## References

- App Manifests reference: https://github.com/ScoopInstaller/Scoop/wiki/App-Manifests
- Manifest JSON schema: https://github.com/ScoopInstaller/Scoop/blob/master/schema.json
- Buckets overview: https://github.com/ScoopInstaller/Scoop/wiki/Buckets
- Main bucket contribution guide: https://github.com/ScoopInstaller/Main/blob/master/CONTRIBUTING.md
- pipx Scoop manifest (a real-world Python CLI for reference): https://github.com/ScoopInstaller/Main/blob/master/bucket/pipx.json
