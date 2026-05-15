# Chocolatey packaging — founder runbook

This directory contains the **draft** Chocolatey package for the `nucleus` CLI on Windows.

[Chocolatey](https://chocolatey.org/) is the de facto Windows package manager in corporate / IT-managed environments. Compared with Scoop:

| | Chocolatey | Scoop |
|---|---|---|
| Audience | IT departments, system-wide installs, requires admin | Devs, per-user installs, no admin |
| Install location | `C:\ProgramData\chocolatey\lib\<pkg>` | `%USERPROFILE%\scoop\apps\<pkg>` |
| Catalogue size | Larger | Smaller, dev-focused |
| Review queue | 1-21 days (slow) | 1-3 days |
| Friction to publish | Higher (moderation review) | Lower |

We ship both because they target distinct populations.

---

## Two distribution paths

| Path | Time-to-live | Trade-off | Recommended for v0.2.0 |
|---|---|---|---|
| **Chocolatey community feed** ([community.chocolatey.org](https://community.chocolatey.org/)) | 1-21 days moderation review | Public, discoverable | Submit alongside the GitHub release |
| **Internal NuGet feed** (e.g., a corporate Azure Artifacts) | Immediate | Private, not for general public | Only relevant if Bosch / specific enterprise consumes it |

For v0.2.0 we publish to the public community feed. Internal feeds are a v0.3+ "if asked" item.

---

## What's in this directory

| File | Purpose |
|---|---|
| `nucleus.nuspec` | NuGet spec (XML metadata: id, version, license, deps). |
| `tools/chocolateyInstall.ps1` | PowerShell install script — venv creation + pip install + shim. |
| `tools/chocolateyUninstall.ps1` | PowerShell uninstall script — shim removal + venv delete. |
| `README.md` | This file. |
| `package_test.md` | Step-by-step local validation procedure before push. |

---

## Pre-publish checklist (founder, every release)

1. **PyPI is live first.** chocolateyInstall.ps1 fetches the wheel from the GitHub release URL — but the GitHub release is built from the same `python -m build` invocation that publishes to PyPI (see `../pypi/PUBLISH_RUNBOOK.md`). Confirm the wheel is downloadable.

2. **Update `nucleus.nuspec`:**
   - Bump `<version>` to match the release tag (without leading `v`).
   - Update `<releaseNotes>` URL to the new CHANGELOG anchor.
   - If the iconUrl version segment ages out, bump it to the new tag.

3. **Compute SHA256 and paste into `tools/chocolateyInstall.ps1`:**

   ```powershell
   # After uploading the wheel to the GitHub release for v0.2.0:
   $url = "https://github.com/nucleus-data/nucleus/releases/download/v0.2.0/nucleus_data-0.2.0-py3-none-any.whl"
   $tmp = New-TemporaryFile
   Invoke-WebRequest $url -OutFile $tmp
   (Get-FileHash $tmp -Algorithm SHA256).Hash.ToLower()
   Remove-Item $tmp
   ```

   Replace the `0000...0000` placeholder at line `$wheelChecksum = '...'` in `chocolateyInstall.ps1`.

4. **Pack and validate locally.** See `package_test.md` for the full procedure. Summary:

   ```powershell
   cd packaging\chocolatey
   choco pack
   # Produces: nucleus.0.2.0.nupkg
   choco install nucleus -dvy -s . --force
   nucleus --version
   choco uninstall nucleus -y
   ```

   Anything that fails locally also fails on the community feed. Fix before submission.

5. **Submit to community feed:**

   ```powershell
   # One-time setup (founder, sign in to https://community.chocolatey.org/account first):
   choco apikey add --source https://push.chocolatey.org/ --api-key <YOUR_API_KEY>

   # Per release:
   choco push nucleus.0.2.0.nupkg --source https://push.chocolatey.org/
   ```

   Watch the moderation queue at https://community.chocolatey.org/profiles/<your-account>/packages.

---

## Submission and moderation

The Chocolatey community feed enforces [package moderation rules](https://docs.chocolatey.org/en-us/community-repository/moderation/). Common reasons for moderation rejection:

| Reason | Fix |
|---|---|
| Missing or unverifiable license | We have a public Apache-2.0 LICENSE on GitHub at the tagged URL — should pass |
| Install script downloads from a non-deterministic URL | Our URL is pinned to the release tag — should pass |
| Install script doesn't validate checksum | We use `Get-ChocolateyWebFile` with `-Checksum` — should pass |
| Install script leaves the system dirty on failure | Our script throws on every error — should pass |
| Package id taken | `nucleus` may already be on the community feed — verify at https://community.chocolatey.org/packages/nucleus before submission |

**STOP CONDITION**: If `nucleus` is already taken on the Chocolatey community feed by an unrelated project, fall back to `nucleus-data` (matches PyPI). Document the choice in `docs/decisions/ADR-NNN-chocolatey-name.md`. The Chocolatey package id can differ from the user-typed CLI binary; see precedent at https://community.chocolatey.org/packages?q=cli (many tools have packageId different from the binary they ship).

Verification:

```powershell
# Check community feed for an existing nucleus package
Invoke-WebRequest https://community.chocolatey.org/api/v2/Packages?$filter=Id+eq+'nucleus' | Select-Object -ExpandProperty Content
```

---

## Per-release update (founder, ~30 min after every PyPI release)

1. Update `nucleus.nuspec` `<version>` and `<releaseNotes>`.
2. Update SHA256 in `chocolateyInstall.ps1`.
3. Local validation per `package_test.md`.
4. `choco push` to the community feed.
5. Monitor moderation queue (1-21 days).

While waiting on moderation, consider also pushing to a private feed (Cloudsmith / Azure Artifacts / JFrog) for users who can't wait.

---

## Known limitations

- **Slow moderation queue.** First-time submissions sometimes wait 1-3 weeks for human review. Plan around it.
- **Long path issues.** Same as Scoop — `dagster._serdes.<deep>` paths can hit Windows' 260-char `MAX_PATH`. We mention this in the package description; the user remediation is to enable [Windows long paths](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry).
- **Antivirus false positives.** PyInstaller / nuitka-built EXEs sometimes trip Windows Defender. We don't ship a packed EXE — we install the wheel into a venv — so this should not affect us. Monitor user issues with the label `packaging:chocolatey`.
- **Python311 dep upgrades.** When Chocolatey's `python311` package bumps from 3.11.X → 3.11.Y, our venv stays on the original Python (the venv copies, not symlinks, the interpreter binary). On reinstall, the venv is recreated with the new Python. Most users won't notice.
- **OIDC publishing not yet supported.** Unlike PyPI, Chocolatey still uses long-lived API keys. Store the founder's key in 1Password / similar; do not commit. As of 2026-05 there is an [open Chocolatey RFC](https://github.com/chocolatey/choco/issues) for OIDC; revisit when accepted.

---

## References

- Create Packages overview: https://docs.chocolatey.org/en-us/create/create-packages
- Function reference (Install-BinFile, Get-ChocolateyWebFile, etc.): https://docs.chocolatey.org/en-us/create/functions/
- Moderation rules: https://docs.chocolatey.org/en-us/community-repository/moderation/
- Nuspec schema: https://learn.microsoft.com/en-us/nuget/reference/nuspec
- Test environments: https://docs.chocolatey.org/en-us/create/test-environment
