# Nucleus v0.2.0 Go/No-Go Checklist

> Last updated 2026-05-16. Use this immediately before public announcement. If any MUST PASS item is unchecked, the launch verdict is **NO-GO**.

## MUST PASS before public

- [ ] Canonical repo URL is consistent in launch-critical docs: `https://github.com/nucleus-data/nucleus`. Any legacy personal-repo URL appears only where explicitly marked historical.
- [ ] Public docs URL is either live at `https://nucleus-data.github.io/nucleus/` or all launch copy states the README/quickstart are the canonical entry points until Pages is enabled. GitHub Pages requires the repo to be public or GitHub Pro until enabled.
- [ ] PyPI Trusted Publisher is registered for owner `nucleus-data`, repo `nucleus`, workflow `release.yml`, environment `pypi`.
- [ ] Public install copy is honest: before PyPI publish use `pip install -e ".[dev]"`; after the `v0.2.0` workflow succeeds use `pip install nucleus` or exact-version `pip install nucleus==0.2.0`. Optional extras are explicit, e.g. `pip install "nucleus[postgres,workbench]"`.
- [ ] Release mechanics are single-path: founder pushes the tag, then verifies `.github/workflows/release.yml` created the GitHub Release. Manual `gh release create` is fallback only if the workflow did not create one.
- [ ] Workbench default URL is consistent with source: `http://localhost:8765`.
- [ ] Launch kit has no raw angle-bracket placeholders. Missing media is represented as `FOUNDER ACTION` or `WORKSTREAM C ACTION`.
- [ ] No self-upvote, vote-ring, or engagement-manipulation instruction remains in Hacker News or timeline docs.
- [ ] CI on `main` is green immediately before tag push.
- [ ] `python scripts/check_vocabulary.py` exits 0.
- [ ] `python scripts/dagster_leak_check.py` exits 0.
- [ ] `docs/internal/benchmarks/2026-05-15_baseline.md` known gaps are reflected in public-facing copy: 11 measured deltas, Windows concurrent-run failure, and v0.2.1 follow-up.
- [ ] Screenshots and demo status are explicit. If `assets/demos/v0.2/launch_60s.mp4` or `assets/screenshots/v0.2/` outputs are missing, do not use media-heavy posts until Workstream C produces them.

## SHOULD PASS before public

- [ ] Press kit stats are rechecked against the latest `scripts/loc_budget.py`, release notes, and README.
- [ ] Clean PyPI smoke succeeds after publish: `pip install nucleus==0.2.0 && nucleus version`.
- [ ] Fresh clone smoke succeeds from the canonical repo URL.
- [ ] HN/Reddit FAQ has concise answers for "just a wrapper", Windows concurrent-run failure, performance baseline gaps, solo-founder risk, and graduation to giants.
- [ ] Founder has 4 hours blocked after Show HN submission for good-faith responses.
- [ ] Workstream C has captured or explicitly deferred: 60-second demo MP4, README poster, Workbench dashboard screenshot, terminal run screenshot, terminal query screenshot.
- [ ] PoC #5 outreach has concrete compensation, booking link, and feedback form owner.
- [ ] `FIRST_7_DAYS_PLAYBOOK.md` is open during launch monitoring and used as the triage guide.

## OK TO DEFER to v0.2.1

- [ ] GitHub branch protection if repo visibility or GitHub Pro/Team gating blocks the ruleset.
- [ ] Native Windows same-asset concurrent-run fix, provided public docs disclose Linux/WSL passes and Windows concurrent writes are not launch-safe.
- [ ] Fresh beachhead-spec benchmark remeasurement on a clean MacBook or Linux laptop.
- [ ] Press outreach beyond founder-owned channels.
- [ ] Polished press screenshots beyond the minimum Workstream C launch assets.
- [ ] Post-launch docs-site domain polish beyond `https://nucleus-data.github.io/nucleus/`.
- [ ] Packaging channel publication for Homebrew/Scoop/Chocolatey drafts.
