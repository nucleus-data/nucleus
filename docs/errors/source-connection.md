# NE1001 — NucleusSourceConnectionError

**Code**: `NE1001`  ·  **Class**: `NucleusSourceConnectionError`  ·  **Layer**: L0 Physics  ·  **Stability**: Stable

## What happened

Nucleus tried to reach an external source (Postgres, MySQL, HTTP endpoint, ...) and the connection attempt failed before any data moved. The source asset could not be read.

A builtin `TimeoutError` raised during source IO routes here as well — the source is reachable in principle but did not respond inside the configured budget.

## Likely causes

- Wrong host, port, or database name in the source config.
- Network path blocked (firewall, VPN not up, DNS resolution failing).
- Credentials missing, expired, or rejected by the source.
- Source is genuinely down or overloaded.

## Fix steps

1. Verify host, port, database, and credentials in your source config.
2. From the same machine, confirm the source is reachable (e.g. `psql` / `mysql` / `curl` against the same endpoint).
3. If the timeout fires on a slow-but-reachable source, raise the source's read timeout in config.

## Related

- Source: `src/nucleus/errors.py` (`NucleusSourceConnectionError`)
- Default fix hint: "Check host, port, and credentials in your source config." (timeout variant adds: "raise the source timeout if the source is genuinely slow.")
- Architecture: [v4.1 §6.4 Error Translation Layer](../specs/nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
