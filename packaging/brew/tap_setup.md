# Setting up the `nucleus-data/homebrew-nucleus` tap

A Homebrew **tap** is a third-party repository the user adds with `brew tap`, after which formulae from that repo behave exactly like core formulae. This is the path we recommend for v0.2.0 because we control the timing — no `homebrew-core` review queue.

User-facing install once the tap exists:

```bash
brew tap nucleus-data/nucleus
brew install nucleus
```

(Note: the tap repo MUST be named `homebrew-<X>` where `<X>` is the suffix users type. We use `homebrew-nucleus`, so users type `brew tap nucleus-data/nucleus`. See [Homebrew taps reference §Naming conventions](https://docs.brew.sh/Taps#repository-naming).)

---

## One-time setup (founder, ~30 min)

### Step 1 — Create the GitHub repo

1. Visit https://github.com/organizations/nucleus-data/repositories/new (or your account if the org doesn't exist yet).
2. Name: **`homebrew-nucleus`** (the `homebrew-` prefix is mandatory).
3. Visibility: Public.
4. Description: "Homebrew tap for the Nucleus CLI (https://github.com/nucleus-data/nucleus)".
5. Initialize with README + `.gitignore` (`Ruby` template) + `LICENSE` (Apache-2.0 to match the upstream).

### Step 2 — Repo layout

```
homebrew-nucleus/
├── Formula/
│   └── nucleus.rb           # copied from packaging/brew/nucleus.rb (this repo)
├── README.md
└── LICENSE
```

That's it. Homebrew discovers any `Formula/*.rb` under a tap.

### Step 3 — Copy the formula

```bash
git clone git@github.com:nucleus-data/homebrew-nucleus.git
cd homebrew-nucleus
mkdir -p Formula
cp /path/to/Mordern-Data-Platform/packaging/brew/nucleus.rb Formula/nucleus.rb
```

Then **fill in the SHA256** (currently a placeholder of all zeros) and the **Python resource blocks** per `README.md` §"Pre-publish checklist" Steps 2-3.

### Step 4 — Audit and test locally

```bash
brew tap nucleus-data/nucleus $(pwd)        # tap from the local clone
brew audit --strict --new --online nucleus
brew install --build-from-source nucleus
nucleus --version                            # MUST print 0.2.0
nucleus init smoke && (cd smoke && nucleus up && nucleus down)
brew uninstall nucleus
brew untap nucleus-data/nucleus
```

If anything fails, fix in `Formula/nucleus.rb` and retry. Do not push a broken formula.

### Step 5 — Push

```bash
git add Formula/nucleus.rb
git commit -m "nucleus 0.2.0 (initial formula)"
git push origin main
```

The tap is now live. Anyone in the world can:

```bash
brew tap nucleus-data/nucleus
brew install nucleus
```

### Step 6 — Tap-side README

Replace the GitHub-generated `README.md` with something like:

```markdown
# nucleus-data/homebrew-nucleus

Homebrew tap for the [Nucleus CLI](https://github.com/nucleus-data/nucleus).

## Install

\`\`\`bash
brew tap nucleus-data/nucleus
brew install nucleus
\`\`\`

## Issues

File formula bugs at https://github.com/nucleus-data/nucleus/issues with the label `packaging:homebrew`.
```

(Backticks escaped for this markdown file; un-escape when you copy.)

---

## Per-release update (founder, ~10 min after every PyPI release)

After `pip install nucleus-data==0.X.Y` works (per `../pypi/PUBLISH_RUNBOOK.md`):

```bash
cd homebrew-nucleus
git pull

# Compute the new sdist SHA256
NEW_VERSION=0.2.1
SHA=$(curl -sL "https://github.com/nucleus-data/nucleus/releases/download/v${NEW_VERSION}/nucleus-data-${NEW_VERSION}.tar.gz" | shasum -a 256 | awk '{print $1}')

# Edit Formula/nucleus.rb:
#   - bump the version segment in the `url` line
#   - replace `sha256 "..."` with the new value
#   - regenerate Python resource blocks via `poet` (see ../README.md Step 3)

brew audit --strict --new --online ./Formula/nucleus.rb
brew uninstall nucleus 2>/dev/null || true
brew install --build-from-source ./Formula/nucleus.rb
nucleus --version

git add Formula/nucleus.rb
git commit -m "nucleus ${NEW_VERSION}"
git push origin main
```

Users get the new version on their next `brew update && brew upgrade nucleus`.

---

## STOP conditions

If any of these fire, stop and ask the founder:

- The PyPI distribution name changes (e.g., from `nucleus-data` back to `nucleus` after a successful PEP 541 dispute). Many places in the formula and resource blocks reference `nucleus-data`; a global rename is needed.
- A transitive dep ships a wheel that doesn't build on macOS (rare but real — historical example: pyarrow v0.16 didn't have an arm64 wheel until v0.17).
- `brew audit --strict` complains about a license incompatibility — Homebrew is strict about non-FOSS deps in formulae destined for homebrew-core. Our pyproject.toml deps are all FOSS-compatible (Apache-2.0 / MIT / BSD-3-Clause / LGPLv3+ for psycopg dynamically-linked) but new deps in future versions could surprise us.

---

## References

- Taps overview: https://docs.brew.sh/Taps
- Tap repository naming: https://docs.brew.sh/Taps#repository-naming
- How a formula gets into homebrew-core: https://docs.brew.sh/How-To-Open-a-Homebrew-Pull-Request
