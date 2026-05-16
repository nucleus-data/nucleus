# Nucleus v0.2.0 First 7 Days Playbook

> Last updated 2026-05-16. Use this after tag push and public announcement. Principle: respond fast, keep claims empirical, cut v0.2.1 only for confirmed install, data-loss, security, or release-workflow failures.

## Day 0 Operating Rhythm

- Keep one terminal on GitHub Actions, one browser tab on PyPI, one tab on GitHub Issues, and one tab on the active HN/Reddit thread.
- Triage every report into one of four buckets: `installation broken`, `data-loss risk`, `security`, or `docs/support`.
- Acknowledge critical reports within 1 hour during launch day. Acknowledge non-critical reports within 24 hours.
- Do not argue tone. Answer technical substance, thank users for reproductions, and move sensitive details out of public comments.

## Install Failures

Detection signals:
- `pip install nucleus==0.2.0` fails.
- User reports Python version mismatch, missing wheel, resolver conflict, or optional extras breakage.
- PyPI page renders but `nucleus version` does not report `0.2.0`.

Response:
- Ask for OS, Python version, exact install command, and full terminal output.
- First reproduce in a clean venv outside the repo.
- If core install fails for many users, pause social amplification and prepare v0.2.1.
- If only an optional extra fails, document the workaround and patch the extra in v0.2.1.

Public reply template:

```text
Thanks for the exact output. I am reproducing this in a clean venv now. If it is a core install failure, I will cut v0.2.1 rather than ask users to work around it. For now, please share OS + Python version + the exact pip command so I can confirm the resolver path.
```

## PyPI Issues

Detection signals:
- Release workflow `publish-pypi` fails.
- PyPI package name conflict appears.
- Wheel/sdist uploads but metadata or README render is broken.

Response:
- OIDC publisher missing: register Trusted Publisher, then re-run the failed workflow. Do not re-tag.
- Package name conflict before publish: stop and make a founder decision on package name before public announcement.
- Metadata/readme issue after publish: do not yank unless install is broken or misleading security content shipped. Patch docs and release v0.2.1 if needed.

## HN and Reddit Criticism

Expected critiques:
- "This is just dbt/Dagster/DuckDB."
- "The benchmark gaps look bad."
- "Windows concurrent run failure means it is not ready."
- "Solo-founder risk."
- "Why not Databricks/Snowflake?"

Response stance:
- Agree with true premises. Nucleus wraps proven OSS by design.
- Link to empirical docs and known issues before defending.
- Do not claim production readiness. v0.2.0 is beta.
- Use "graduate" and "yield to giants" language; do not frame Nucleus as a replacement for the giants.

Public reply template:

```text
That is a fair read: Nucleus deliberately wraps the proven pieces instead of rebuilding them. The product bet is that a 5-20 engineer team benefits from one CLI, one error namespace, one asset model, and Iceberg portability without doing the integration work themselves. The rough parts are documented in docs/internal/benchmarks/2026-05-15_baseline.md, including the Windows concurrent-run gap.
```

## Security Reports

Detection signals:
- Credential leak, unsafe file handling, dependency CVE, path traversal, data exposure, or unauthenticated destructive action.

Response:
- Acknowledge within 24 hours, faster on launch day.
- Move exploit details out of public thread if the report is sensitive.
- Reproduce locally, record affected versions, and decide: docs-only mitigation, v0.2.1 patch, or PyPI yank.
- Yank only if users are actively exposed and a patch cannot be cut quickly.

Public reply template:

```text
Thanks for reporting this. I am going to handle the details carefully rather than debug the exploit path in public. I will confirm affected versions, patch if reproducible, and update the issue with a safe summary and mitigation.
```

## CI Red

Detection signals:
- `ci.yml` fails on `main`.
- `release.yml` succeeds publish but release-asset upload fails.
- Governance script goes red after docs edits.

Response:
- If CI is red before public announcement, stop the launch.
- If CI goes red after public announcement but install works, file and fix normally unless the failure affects users.
- If release assets are missing but PyPI works, edit the GitHub Release once workflow artifacts are available.

## Support Triage

Labels:
- `installation broken`: core install, version command, package metadata.
- `bug`: reproducible runtime failure after install.
- `security`: sensitive or exploitable issue.
- `docs`: confusing or stale docs.
- `question`: usage support or design question.
- `v0.2.1-candidate`: small patch that protects first-week users.

Prioritization:
- First: security, data-loss risk, core install failure.
- Second: launch-copy correction, broken docs URL, PyPI metadata problem.
- Third: optional connector issues, Workbench UI bugs, benchmark clarifications.
- Defer: feature requests not needed for the 30-minute beachhead metric.

## User Feedback Capture

Every day for the first 7 days, capture:
- Top 3 repeated user questions.
- Top 3 install or quickstart failures.
- Any mismatch between public claims and user-observed behavior.
- Any docs page users cite as confusing.
- Any issue that should become a v0.2.1 patch.

End-of-week synthesis:
- Publish a short internal note with what shipped, what broke, what users wanted, and what moves into v0.2.1.
- Do not expand scope based on excitement. Only patch what protects first-week adoption or the 30-minute beachhead metric.
