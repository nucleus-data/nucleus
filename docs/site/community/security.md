---
title: Security
description: Responsible disclosure policy for Nucleus security vulnerabilities.
---

# Security

## Reporting a vulnerability

**Do not file a public GitHub issue for security vulnerabilities.**

Instead, use GitHub's [private security advisory](https://github.com/nucleus-data/nucleus/internal/security/advisories/new) feature, or email the maintainer directly (address in the repo's `SECURITY.md`).

Include:
- Description of the vulnerability
- Reproduction steps
- Potential impact
- Your suggested fix (optional)

We aim to respond within 48 hours and to issue a fix within 14 days for critical vulnerabilities.

## Scope

- The Nucleus Python package (`src/nucleus/`)
- The CLI (`nucleus` command)
- The docker-compose configuration shipped with the project

Out of scope:
- Third-party dependencies (report to their maintainers)
- Issues requiring physical access to the machine
- Social engineering

## Threat model

See [`docs/internal/security/threat_model_v1.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/security/threat_model_v1.md) for the documented threat model.

## Security design

- **No custom auth** — Nucleus delegates authentication to OIDC (v0.3+; per ADR-010)
- **Secrets never committed** — use environment variables or `.env` (gitignored)
- **Dependencies pinned** — all runtime deps use exact version pins (per Constraint #11)
- **AI opt-in** — Copilot requires explicit consent before any data leaves the machine (per ADR-015)
