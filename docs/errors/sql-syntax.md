# NE2002 — NucleusSQLSyntaxError

**Code**: `NE2002`  ·  **Class**: `NucleusSQLSyntaxError`  ·  **Layer**: L1 Engines  ·  **Stability**: Stable

## What happened

A SQL string in your project failed to parse. The engine could not interpret the statement at all, so no binding or execution was attempted. The error includes a line / column position when the engine provides one.

## Likely causes

- A typo (missing comma, unclosed quote, stray semicolon).
- A missing `FROM` clause or stray keyword.
- Dialect drift — the SQL was written for Postgres or another dialect and uses syntax the engine does not accept.
- A `{{ ref(...) }}` template that did not resolve (check `ctx.sql` is being used and the referenced asset exists).

## Fix steps

1. Read the line / column position in the error message and fix the syntax there.
2. If the syntax looks valid in another dialect, rewrite it for the engine in use (the default v0.1 dialect is the embedded analytics engine, not Postgres).
3. Re-run the materialization.

## Related

- Source: `src/nucleus/errors.py` (`NucleusSQLSyntaxError`)
- Default fix hint: "Check the SQL for typos, missing FROM clauses, or unclosed quotes. The dialect is not Postgres."
- Architecture: [v4.1 §6.4 Error Translation Layer](../../nucleus_architecture_v4.1.md)
- ADR: [ADR-006](../decisions/ADR-006-nucleus-error-code-numbering.md)
