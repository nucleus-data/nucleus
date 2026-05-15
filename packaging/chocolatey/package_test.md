# Chocolatey package — local validation procedure

Run this end-to-end on a clean Windows VM **before** every `choco push` to the community feed. Failures here become user-facing within hours; failures on the public feed take days to retract.

## Prereqs

- Windows 10/11 or Windows Server 2019/2022.
- Chocolatey installed: https://chocolatey.org/install
- An admin PowerShell window (Choco needs admin to install/uninstall).
- A clean machine OR a snapshotted VM you can roll back. **Do not test on your main machine** — this script installs python311 system-wide.

Recommended environments per Chocolatey docs: https://docs.chocolatey.org/en-us/create/test-environment (free Vagrant boxes provided).

---

## Test 1 — Pack

```powershell
cd packaging\chocolatey
choco pack
```

Expect: `nucleus.0.2.0.nupkg` produced in the current directory. No warnings.

If `choco pack` warns "iconUrl deprecated", regenerate the icon as a packaged file (advanced; not needed for v0.2.0 — community feed accepts iconUrl).

---

## Test 2 — Install (clean machine)

```powershell
choco install nucleus -dvy -s . --force
```

Flags:
- `-d` debug
- `-v` verbose
- `-y` auto-confirm
- `-s .` source = current directory (the .nupkg we just packed)
- `--force` reinstall even if a stale install exists

Expect:
1. `python311` dep installs (~2-5 min on first install).
2. `nucleus` package install runs `chocolateyInstall.ps1`:
   - Locates Python 3.11.
   - Creates venv at `C:\ProgramData\chocolatey\lib\nucleus\tools\venv\`.
   - Downloads wheel from GitHub release URL.
   - Pip-installs the wheel.
   - Shims `nucleus` onto PATH.
   - Prints `NUCLEUS-INSTALL: smoke OK (nucleus 0.2.0)`.
3. Final line: `Chocolatey installed 1/1 packages.`

If install fails: read the verbose log, fix `chocolateyInstall.ps1`, repack, retry.

---

## Test 3 — Smoke (open a NEW PowerShell window)

```powershell
# Confirm shim is on PATH
where.exe nucleus
nucleus --version            # MUST print 0.2.0

# End-to-end smoke
nucleus init c:\temp\choco-smoke
cd c:\temp\choco-smoke
nucleus up
nucleus query "SELECT 'hello' AS msg"
nucleus down
```

Expect:
- `nucleus --version` returns `nucleus 0.2.0` and exits 0.
- `nucleus init` scaffolds a project under `c:\temp\choco-smoke`.
- `nucleus up` boots local infra in <30 s.
- `nucleus query` returns one row.
- `nucleus down` exits cleanly.

If any step fails, the package is broken — do not push. Most failures here are missing transitive deps (e.g., a wheel that doesn't ship win_amd64).

---

## Test 4 — Uninstall

```powershell
choco uninstall nucleus -y
```

Expect:
1. `chocolateyUninstall.ps1` runs:
   - Removes the `nucleus` PATH shim.
   - Removes `C:\ProgramData\chocolatey\lib\nucleus\tools\venv\`.
2. python311 stays installed (correct — it's a separate package).
3. Final line: `Chocolatey uninstalled 1/1 packages.`

Then verify cleanup:

```powershell
where.exe nucleus            # MUST exit non-zero (command not found)
Test-Path C:\ProgramData\chocolatey\lib\nucleus      # MUST be False
```

---

## Test 5 — Reinstall (idempotency)

```powershell
choco install nucleus -y -s .
nucleus --version
choco uninstall nucleus -y
```

Expect: same behaviour as Test 2 + Test 4. Reinstall must not produce a "venv already exists" error (`chocolateyInstall.ps1` deletes the venv first).

---

## Test 6 — Sandbox (optional but recommended)

If you have Windows Sandbox enabled (Pro/Enterprise only):

```powershell
# Run from elevated PowerShell
choco install windowssandbox -y      # if not already present
WindowsSandbox.exe                    # opens a fresh Windows VM
# Inside the sandbox: install Chocolatey, then run Tests 1-5
```

Sandbox is the gold-standard "clean machine" — every run starts from scratch. If the package works in Sandbox, it works for new users.

---

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `python311 dependency could not be installed` | Choco source mirror is down (rare) | Retry; wait 5 min |
| `pip install of wheel failed` with SSL error | Outbound proxy blocking PyPI | Document corp proxy in `chocolateyInstall.ps1` notes |
| `nucleus.exe was not produced inside the venv` | `[project.scripts]` missing in pyproject.toml at build time | Verify pyproject.toml; rebuild wheel; re-upload |
| `nucleus --version` fails after install | PATH not refreshed in current session | Open a new PowerShell window (PATH is set per-process at launch) |
| Long-path errors during `pip install` | Windows MAX_PATH=260 hit | User must enable long paths via [LongPathsEnabled registry key](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation) |
| Defender quarantines the wheel | False positive on a transitive dep | Submit a sample to Defender; usually cleared in 24 h |

---

## Sign-off checklist

Before `choco push`:

- [ ] All 5 tests pass on a clean machine.
- [ ] SHA256 in `chocolateyInstall.ps1` matches the wheel on GitHub releases.
- [ ] `<version>` in `nucleus.nuspec` matches the GitHub release tag.
- [ ] CHANGELOG.md anchor referenced in `<releaseNotes>` exists.
- [ ] No leftover `0000...0000` placeholders.
- [ ] Local moderation log clean (`choco pack` + `choco install` show no warnings).

When all boxes are checked, push:

```powershell
choco push nucleus.0.2.0.nupkg --source https://push.chocolatey.org/
```

Then watch the moderation queue at https://community.chocolatey.org/profiles/nucleus-data/packages.
