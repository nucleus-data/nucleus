---
title: Troubleshooting
description: Diagnose and fix common Nucleus installation, runtime, and environment issues.
---

# Troubleshooting

Most Nucleus problems fall into one of three buckets. Start with the bucket that matches your symptom; the page-level guides below cover ~80% of real-world cases.

| Bucket | Page | When to use |
|--------|------|-------------|
| Install / setup | [Install Issues](install-issues.md) | `pip install` fails, wrong Python version, missing wheels, venv confusion |
| Runtime errors | [Common Errors](common-errors.md) | The most frequent `NE`-codes (`nucleus up`, `nucleus run`, `nucleus ingest`) and their quick fixes |
| Network / corporate | [Corporate Proxy](proxy-corporate-network.md) | Behind a corporate proxy (Bosch, SAP, banks): pip TLS, Docker pulls, MinIO endpoint trust |

If your symptom doesn't match any of those, jump to the [Error Reference](../errors/index.md) and search by `NE`-code. Every error has a one-line **Fix** and a docs URL printed in the error envelope itself.

## Quick diagnosis (60 seconds)

Run these in order. The first one that fails identifies your problem class.

```bash
# 1. Is nucleus on PATH and importable?
nucleus version

# 2. Is your venv the active interpreter?
python -c "import nucleus, sys; print(nucleus.__file__); print(sys.executable)"

# 3. Is Docker running and reachable?
docker ps

# 4. Are the local-stack ports free?
# macOS / Linux:
lsof -i :9000 -i :9001 -i :3000
# Windows:
netstat -ano | findstr ":9000"

# 5. Do you have disk space for Iceberg data + Docker images?
df -h .

# 6. (v0.3+) End-to-end diagnostic
nucleus doctor
```

If steps 1–5 all pass and you're still stuck, the problem is almost always (a) credentials/network for an external source, or (b) a corner case worth a [GitHub issue](https://github.com/nucleus-data/nucleus/issues).

## How to read a Nucleus error

Every error follows the same three-field envelope:

```
Error: <what went wrong, in user language>
Fix:   <a concrete next action>
Docs:  https://nucleus.dev/errors/<slug>
       [NE<L><CCC>]
```

- The **Error** line is what to read first. It is intentionally written without external classnames (no `OpExecutionContext`, no `DuckDBPyConnection`) — see the [error-translation discipline](../governance/error-translation-discipline.md) for why.
- The **Fix** line is the single best next thing to try. ~75% of users are unblocked by it alone.
- The **Docs** URL deep-links to the canonical page for that code, with extended context, related codes, and reproductions.
- The bracketed `[NE<L><CCC>]` is the stable error code. Use it when filing issues; never paste stack traces alone.

## Filing a useful bug report

If you've worked the diagnosis above and are still stuck, please include:

1. The full error envelope (all four lines, including the `NE`-code)
2. Output of `nucleus version` (Python version, OS, wrapped engine versions)
3. The minimal `nucleus` command that reproduces it
4. Whether `make check` passes on a fresh clone (rules out repo-state issues)
5. If a connector-related issue: the source dialect and the redacted `nucleus.toml` source block

File at [github.com/nucleus-data/nucleus/issues](https://github.com/nucleus-data/nucleus/issues). For non-bug questions, [GitHub Discussions](https://github.com/nucleus-data/nucleus/discussions) is faster.

## Related references

- [Error Reference](../errors/index.md) — every `NE`-code, organized by architecture layer
- [Installation](../getting-started/installation.md) — system requirements and supported Python versions
- [CLI Reference](../cli-reference/index.md) — global flags and exit codes
- [Upgrade Policy](../governance/upgrade-policy.md) — when to expect breaking changes
