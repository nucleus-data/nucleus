# apt (Debian / Ubuntu) packaging — DEFERRED to v0.3+

This directory is intentionally **near-empty**. There is no .deb spec for v0.2.0.

## Why deferred

Linux users have a working install path via `pip install nucleus-data-data` (per `../pypi/PUBLISH_RUNBOOK.md`). System-managed Python on Debian/Ubuntu (`python3.11`, `python3-venv`) is well-maintained, and pip-into-venv is the default workflow for Python tooling in the Linux dev community.

Building a real .deb requires:

- **Where to host the apt repo.** Options:
  - **Launchpad PPA** (`ppa:nucleus-data/nucleus`) — free, Canonical-hosted, good for Ubuntu users; build infra is opinionated and slow.
  - **Cloudsmith** — managed apt repo SaaS, paid (~$50/mo for the tier we'd need), cleanest UX.
  - **JFrog Artifactory** — same as Cloudsmith but pricier and aimed at enterprise.
  - **Self-hosted** (`reprepro` on a public S3 bucket) — cheapest, more maintenance.
- **Signing key infrastructure.** GPG-signed `Release` and `Packages` files; the founder must hold the signing key (HSM ideally), and rotate it on a schedule. This is real opsec work — wrong key handling = supply-chain risk.
- **Multi-arch builds.** `amd64` + `arm64` on `bookworm` (Debian 12) + `noble` / `jammy` (Ubuntu 24.04 / 22.04) = 6 .debs per release minimum.
- **Maintainer scripts** (`postinst`, `prerm`) that play nicely with `apt upgrade` and `apt purge`.
- **Conflict / Replaces** declarations against any existing `nucleus`-named package in the Debian / Ubuntu universe (none today, verified 2026-05-15).

That's ~2-3 days of one-time setup plus ~30 min per release to maintain. Not worth it for v0.2.0 when pip works.

## When to revisit (v0.3+)

Trigger conditions — any one of:

1. A user files an issue saying "we run a Debian box where pip-install isn't allowed by IT policy" and we have ≥3 such reports.
2. A Bosch-internal apt mirror needs to host us (the original PoC-#5 customer profile suggests this is plausible).
3. A `sudo apt install nucleus` mention is a stated marketing requirement (e.g., "our docs say apt-installable on a podcast appearance").

When the trigger fires:

| Choice | Cost | Recommendation |
|---|---|---|
| Cloudsmith-hosted apt repo + GitHub Action push | $50/mo + ~1 day setup | Default for v0.3 — fastest path to "it works" |
| Launchpad PPA | Free + ~3 days setup | Only if we already use Launchpad for something else |
| Self-hosted reprepro on R2 / B2 | Cheapest hosting + most maintenance | Skip unless cost is the binding constraint |

## What goes in this directory when we do build it

```
apt/
├── README.md                       (this file, expanded)
├── debian/
│   ├── changelog
│   ├── compat
│   ├── control                     # Depends, Conflicts, Maintainer
│   ├── copyright                   # Apache-2.0 declaration
│   ├── rules                       # debhelper invocation
│   ├── nucleus.install             # which files land where
│   └── source/format
└── build.sh                        # docker-based reproducible build
```

Reference: https://www.debian.org/doc/manuals/maint-guide/

For Python tools specifically, prefer building with [`dh-virtualenv`](https://github.com/spotify/dh-virtualenv) — it bundles a venv into the .deb so we don't depend on the system Python being a specific minor version. That mirrors our brew/scoop/chocolatey strategy of "isolated venv per install". Spotify maintains the tool; it's the same approach Spotify uses for their internal Python services.

## STOP CONDITION before any apt work

Before opening this work, the founder must answer:

1. Which hosted vs self-hosted apt repo? (governs ongoing cost)
2. Where does the GPG signing key live? (governs supply-chain risk)
3. Which Debian / Ubuntu releases do we support? (governs build matrix size)

Without answers to all three, no apt work happens. Open `docs/decisions/ADR-NNN-apt-distribution.md` to record the answers.
