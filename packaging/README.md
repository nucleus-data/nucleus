# `packaging/` — cross-platform install recipes for the `nucleus` CLI

> **Status (2026-05-15)**: DRAFT recipes for v0.2.0 GA. Founder reviews and submits. Nothing in this directory has been published yet.

This directory holds the per-channel package recipes that turn a tagged GitHub release into installable artefacts on macOS, Windows, and Linux. Pip remains the primary install path (cross-platform); the channels here are for users who prefer their OS package manager.

```
packaging/
├── README.md            <-- you are here (founder runbook)
├── pypi/                <-- read FIRST. Everything else depends on PyPI.
│   └── PUBLISH_RUNBOOK.md
├── brew/                <-- macOS (and Linuxbrew). Custom tap default.
│   ├── nucleus.rb
│   ├── README.md
│   └── tap_setup.md
├── scoop/               <-- Windows (developer audience). Custom bucket default.
│   ├── nucleus.json
│   ├── README.md
│   └── bucket_setup.md
├── chocolatey/          <-- Windows (corporate audience). Community feed.
│   ├── nucleus.nuspec
│   ├── tools/
│   │   ├── chocolateyInstall.ps1
│   │   └── chocolateyUninstall.ps1
│   ├── README.md
│   └── package_test.md
├── snap/                <-- v0.3+ DRAFT, not yet published.
│   └── snapcraft.yaml.draft
└── apt/                 <-- v0.3+ deferred. Decision-record only.
    └── README.md
```

---

## CRITICAL — read this section before doing anything

### PyPI name collision

**The bare `nucleus` name is squatted on PyPI** by a 2015-vintage placeholder package with no functionality.

| Verified 2026-05-15 | Status |
|---|---|
| `pypi.org/project/nucleus/` | TAKEN — version 0.0.1, 2015-11-23, abandoned |
| `pypi.org/project/nucleus-data/` | AVAILABLE |
| `pypi.org/project/nucleusio/` | AVAILABLE |
| `pypi.org/project/nucleus-cli/` | AVAILABLE |
| `pypi.org/project/nucleus-platform/` | AVAILABLE |

**Founder decision required (Step 0 in `pypi/PUBLISH_RUNBOOK.md`):** pick a PyPI distribution name. Default recommendation is **`nucleus-data`** because it matches the GitHub org `nucleus-data/nucleus` and reads cleanly.

The Python *import* name stays `nucleus` regardless — the `pip install` command becomes `pip install nucleus-data`, but the user code still says `import nucleus.ctx as ctx`. Distribution and import names are independent (cf. `pip install scikit-learn` → `import sklearn`).

The downstream package recipes (brew / scoop / chocolatey / snap) all use the Chocolatey/brew/scoop **package id `nucleus`** because that is the user-facing CLI binary — but the wheel they download is named `nucleus_data-*.whl`. The recipes already encode this assumption.

### Implications if you pick a different name

If the founder picks something other than `nucleus-data`:

- `pyproject.toml` `[project] name` — change once.
- README.md / docs install snippets — global find-replace `nucleus-data` → `<new>`.
- `packaging/scoop/nucleus.json` — `url` field references `nucleus_data-*.whl`; rename pattern to `<new>_*.whl` (with PEP 427 underscore normalisation).
- `packaging/chocolatey/tools/chocolateyInstall.ps1` — `$wheelName` variable.
- `packaging/brew/nucleus.rb` — comments + the `url` line + `poet` regeneration target.
- `packaging/snap/snapcraft.yaml.draft` — comment reference.

Cost: ~10 minutes of mechanical edits. Do this BEFORE first publish; doing it after means a name change on PyPI (impossible — PyPI doesn't allow renames; you'd have to publish a new package and deprecate the old).

---

## Recommended publish order for v0.2.0

Each step blocks the next. Do not parallelise across the dotted line.

```
                     [Step 0]  Founder picks PyPI name + edits pyproject.toml
                                            │
                                            ▼
                     [Step 1]  PyPI Trusted Publisher configured (one-time)
                                            │
                                            ▼
                     [Step 2]  GitHub Actions release.yml shipped (one-time)
                                            │
                                            ▼
                     [Step 3]  Tag v0.2.0 → wheel published to PyPI
                                            │
            ┌─────────── verification gate ─┼───────────┐
            ▼                               ▼           ▼
    pip install nucleus-data       . . . . . . . .  pip install
    works on clean venv            (no errors)      reproducibly works
                                            │
       . . . . . . . . . . . . . . . . . . .│ everything below is parallelisable
                                            ▼
        ┌───────────────┬───────────────────┼───────────────────┐
        ▼               ▼                   ▼                   ▼
   [Step 4]        [Step 5]            [Step 6]            [Step 7 — defer]
   brew tap        scoop bucket        chocolatey          snap / apt
   nucleus-data/   nucleus-data/       community feed      v0.3+
   homebrew-       scoop-bucket        moderation queue    only if user
   nucleus         (we control         (1-21 days)         demand emerges
   (we control     timing — push
   timing — push   and done)
   and done)
```

Steps 4-6 can run in parallel **after** Step 3 succeeds. Step 7 (snap / apt) is explicitly deferred to v0.3+ unless a user files an issue requesting them.

---

## Founder action items for v0.2.0 (top 3)

In strict priority order. Items below the line are nice-to-have for v0.2.0; revisit before v0.3.

1. **Pick the PyPI distribution name** and bump `pyproject.toml`.
   - Default: `nucleus-data`.
   - Open `docs/decisions/ADR-NNN-pypi-name.md` recording the choice.
   - Update `pyproject.toml` line `name = "nucleus"` → `name = "nucleus-data"` (or chosen name).
   - Update README `pip install nucleus` → `pip install nucleus-data`.

2. **Configure PyPI OIDC trusted publisher.**
   - Visit https://pypi.org/manage/account/publishing/.
   - Add publisher: PyPI project = `nucleus-data`, Owner = `nucleus-data`, Repo = `nucleus`, Workflow = `release.yml`, Environment = `pypi`.
   - Full step-by-step in `pypi/PUBLISH_RUNBOOK.md` Step 2.

3. **Ship `.github/workflows/release.yml`** that builds + publishes the wheel on tag push.
   - File does not exist in this repo today. Drafting it is a swarm follow-up task — see "Founder follow-up backlog" below.
   - Reference template: https://docs.pypi.org/trusted-publishers/using-a-publisher/#examples

Below the line (v0.2.0 nice-to-have, v0.3 mandatory):

4. Create the `nucleus-data/homebrew-nucleus` tap repo (`brew/tap_setup.md`).
5. Create the `nucleus-data/scoop-bucket` bucket repo (`scoop/bucket_setup.md`).
6. Submit `nucleus.0.2.0.nupkg` to the Chocolatey community feed (`chocolatey/README.md`).

---

## Founder follow-up backlog (work the swarm doesn't own)

These items are out of scope for `packaging/` but adjacent. They block the publish path.

| Task | Owner | Estimated time | Blocks |
|---|---|---|---|
| Create GitHub org `nucleus-data` (if not exists) | founder | 5 min | All channels |
| Create `nucleus-data/nucleus` repo + push existing code | founder | 30 min | All channels |
| Pick PyPI distribution name + update pyproject.toml | founder | 5 min | PyPI |
| Open `docs/decisions/ADR-NNN-pypi-name.md` | founder | 10 min | Auditability |
| Open PyPI account + enable 2FA | founder | 10 min | PyPI |
| Configure PyPI OIDC trusted publisher | founder | 10 min | Tag-push publish |
| Ship `.github/workflows/release.yml` | swarm task | 1-2 hr | Tag-push publish |
| Create `nucleus-data/homebrew-nucleus` GitHub repo | founder | 10 min | brew |
| Create `nucleus-data/scoop-bucket` GitHub repo | founder | 10 min | scoop |
| Generate `homebrew-pypi-poet` resource blocks | swarm task post-publish | 30 min | brew (homebrew-core) |
| Open Chocolatey community account + API key | founder | 15 min | chocolatey |
| First `choco push` of nucleus.0.2.0.nupkg | founder | 5 min + queue wait | chocolatey |
| If demand: snap / apt | future swarm | 2-3 days each | snap/apt only |

Total founder time for v0.2.0 publish (assuming nothing breaks): ~75 min spread across 1-2 days. Bulk of the time is the Chocolatey moderation queue (1-21 days, **founder doesn't actively work** that wait — the package just sits).

---

## Per-release maintenance cadence

After v0.2.0 ships, every subsequent release follows:

```
1. Engineering: bump version in pyproject.toml + CHANGELOG.md
2. Engineering: tag vX.Y.Z and push           ──>  PyPI auto-publishes
3. Founder: bump packaging/scoop/nucleus.json (version + hash)         ──>  push to scoop-bucket
4. Founder: bump packaging/brew/nucleus.rb (sha + poet regen)          ──>  push to homebrew-nucleus
5. Founder: bump packaging/chocolatey/nucleus.nuspec + install.ps1     ──>  choco push
```

Estimated time per release after the first one: ~30 min (mostly the SHA256 fetch + paste cycles). Each per-channel README has a "Per-release update" section with copy-paste commands.

Two of the three channels (brew tap, scoop bucket) are in our own org — instant publish. Chocolatey adds 1-21 days of moderation latency that we cannot avoid; plan releases accordingly (v0.2.1 patch release does not block on Chocolatey).

---

## Quality bar for "shipped"

A release is considered "fully shipped" when ALL of these are true:

- [ ] `pip install <pypi-name>` works on a clean Python 3.11 venv on macOS, Windows, and Linux.
- [ ] `nucleus --version` returns the expected version string.
- [ ] `nucleus init demo && cd demo && nucleus up && nucleus down` completes without error.
- [ ] At least one OS package manager install (brew tap or scoop bucket) is updated to the new version.
- [ ] `CHANGELOG.md` has a section dated to release day.
- [ ] GitHub release has the wheel + sdist attached (so the brew/scoop/choco recipes can pull from it).

The Chocolatey community feed update is **NOT** in the quality bar because we cannot control its review queue. We track Chocolatey separately.

---

## STOP CONDITIONS — pause and ask the founder

Halt all packaging work and surface to the founder if any of these fire:

1. **PyPI publish fails with `403 invalid-publisher`** after Step 2 of `pypi/PUBLISH_RUNBOOK.md`. Root cause is almost always a workflow filename / repo / environment mismatch; do not hand-craft a fix without re-reading PyPI docs.
2. **A package id is taken on a downstream channel** (e.g., `nucleus` is already on the Chocolatey community feed by an unrelated project). Fall back to `nucleus-data` per the per-channel README; document the decision in an ADR.
3. **A transitive dep ships a wheel that doesn't build on a target arch** (rare — pyiceberg/polars/duckdb/pyarrow all ship for amd64+arm64 on macos+linux+win, but a future release could regress).
4. **A signing key handling decision is needed** (apt repo, future code-signing for the Windows EXE shim if we ever produce one). Founder must own key rotation policy.
5. **Founder considers PEP 541 dispute** to reclaim the bare `nucleus` PyPI name. This is a multi-week process and should not block v0.2.0; pause this packaging stream while the dispute runs.

---

## References

- PyPI: https://docs.pypi.org/
- Homebrew Formula Cookbook: https://docs.brew.sh/Formula-Cookbook
- Scoop App Manifests: https://github.com/ScoopInstaller/Scoop/wiki/App-Manifests
- Chocolatey Create Packages: https://docs.chocolatey.org/en-us/create/create-packages
- Snapcraft schema: https://snapcraft.io/docs/snapcraft-yaml-schema
- PEP 503 (normalized names): https://peps.python.org/pep-0503/
- PEP 541 (project name disputes): https://peps.python.org/pep-0541/
