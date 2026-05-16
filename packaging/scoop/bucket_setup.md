# Setting up the `nucleus-data/scoop-bucket` Scoop bucket

A Scoop **bucket** is a Git repository containing JSON manifests. Users add it once with `scoop bucket add` and from then on `scoop install <name>` works for any manifest in the bucket.

User-facing install once the bucket exists:

```powershell
scoop bucket add nucleus https://github.com/nucleus-data/scoop-bucket
scoop install nucleus
```

(Bucket repos do **not** require any prefix in the name — they can be called anything. We pick `scoop-bucket` for clarity.)

---

## One-time setup (founder, ~30 min)

### Step 1 — Create the GitHub repo

1. Visit https://github.com/organizations/nucleus-data/repositories/new (create the org first if it doesn't exist).
2. Name: **`scoop-bucket`**.
3. Visibility: Public.
4. Description: "Scoop bucket for the Nucleus CLI (https://github.com/nucleus-data/nucleus)".
5. Initialize with README + Apache-2.0 LICENSE.

### Step 2 — Repo layout

```
scoop-bucket/
├── bucket/
│   └── nucleus.json            # copied from packaging/scoop/nucleus.json
├── README.md
├── LICENSE
└── .github/
    └── workflows/
        └── ci.yml              # OPTIONAL — auto-run `scoop install` smoke per PR
```

The `bucket/` subdirectory is where Scoop looks. Top-level manifests are also accepted but `bucket/` is the convention.

### Step 3 — Copy the manifest

```powershell
git clone git@github.com:nucleus-data/scoop-bucket.git
cd scoop-bucket
mkdir bucket
copy ..\Mordern-Data-Platform\packaging\scoop\nucleus.json bucket\nucleus.json
```

Then **fill in the SHA256** (currently `0000...0000`) per `README.md` §"Pre-publish checklist" Step 3.

### Step 4 — Validate locally

```powershell
# Install Scoop if you don't have it
irm get.scoop.sh | iex

# Add the bucket from the local clone
scoop bucket add nucleus-local "$(Resolve-Path .)"

# Install
scoop install nucleus-local/nucleus
nucleus --version                      # MUST print 0.2.0
nucleus init smoke
cd smoke; nucleus up; nucleus down

# Cleanup
scoop uninstall nucleus
scoop bucket rm nucleus-local
```

If anything fails, fix in `bucket\nucleus.json` and retry.

### Step 5 — Push

```powershell
git add bucket\nucleus.json
git commit -m "nucleus 0.2.0 (initial manifest)"
git push origin main
```

The bucket is now live. Anyone can:

```powershell
scoop bucket add nucleus https://github.com/nucleus-data/scoop-bucket
scoop install nucleus
```

### Step 6 — Bucket-side README

Replace the GitHub-generated `README.md` with:

```markdown
# nucleus-data/scoop-bucket

Scoop bucket for the [Nucleus CLI](https://github.com/nucleus-data/nucleus).

## Install

\`\`\`powershell
scoop bucket add nucleus https://github.com/nucleus-data/scoop-bucket
scoop install nucleus
\`\`\`

## Issues

File install bugs at https://github.com/nucleus-data/nucleus/issues with the label `packaging:scoop`.
```

(Backticks escaped above; un-escape on copy.)

### Step 7 — (Optional but recommended) CI for the bucket

Add `.github/workflows/ci.yml` that runs `scoop install` from the manifest on every PR. Sample at https://github.com/ScoopInstaller/GithubActions. Catches manifest schema breakage before users hit it.

---

## Per-release update (founder, ~5 min after every PyPI release)

After `pip install nucleus-data-data==0.X.Y` works (per `../pypi/PUBLISH_RUNBOOK.md`):

```powershell
cd scoop-bucket
git pull

# Edit bucket\nucleus.json:
#   - bump "version"
#   - bump "url" to the new wheel URL
#   - replace "hash" with the new SHA256 (computed per ../README.md Step 3)

# Local smoke
scoop bucket add nucleus-local "$(Resolve-Path .)"
scoop install nucleus-local/nucleus
nucleus --version
scoop uninstall nucleus
scoop bucket rm nucleus-local

git add bucket\nucleus.json
git commit -m "nucleus 0.X.Y"
git push origin main
```

Users get the new version on their next `scoop update && scoop update nucleus`.

If the `autoupdate` block in the manifest is wired correctly (see `nucleus.json` `autoupdate` field) and you've uploaded the `.sha256` sidecar to the GitHub release, you can skip the manual edit and run `bucket\nucleus.json | scoop checkver -u` to auto-bump.

---

## STOP conditions

- The PyPI distribution name changes (e.g., `nucleus-data` → `nucleus` after a successful PEP 541 dispute). The wheel filename in `url` references `nucleus_data-...`; rename will be needed.
- A new release adds a non-pure-Python dep that lacks Windows wheels (rare for our deps — polars/duckdb/pyarrow all ship win_amd64 wheels).
- ScoopInstaller deprecates a manifest field we use (rare — schema is stable since 2019).

---

## References

- Scoop bucket guide: https://github.com/ScoopInstaller/Scoop/wiki/Buckets
- Bucket schema: https://github.com/ScoopInstaller/Scoop/blob/master/schema.json
- ScoopInstaller/GithubActions (CI helpers for buckets): https://github.com/ScoopInstaller/GithubActions
- Excavator (auto-updates buckets via GitHub Actions): https://github.com/ScoopInstaller/Excavator
