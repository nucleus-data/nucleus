# Snowflake Connector Research Notes

> **Purpose**: Pre-integration research per AGENTS.md §11.12 (Constraint #10 — read official docs before integration).
> **Component**: Snowflake source connector via `dlt[snowflake]` + `snowflake-sqlalchemy`
> **Date**: 2026-05-15
> **Author**: Builder (connector expansion wave)
> **ADR**: ADR-019-snowflake-connector-via-dlt.md (PROPOSED)

---

## §1. Official Documentation Sources

| Source | URL |
|--------|-----|
| Snowflake SQLAlchemy (official) | https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy |
| Snowflake Python Connector | https://docs.snowflake.com/en/developer-guide/python-connector/python-connector |
| Snowflake Python Connector error codes | https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-error-codes |
| dlt `sql_database` verified source | https://dlthub.com/docs/dlt-ecosystem/verified-sources/sql_database |
| dlt Snowflake connector extras | https://dlthub.com/docs/dlt-ecosystem/destinations/snowflake |
| SQLAlchemy core exceptions | https://docs.sqlalchemy.org/en/20/core/exceptions.html |

---

## §2. Connection String Format

Snowflake SQLAlchemy URL (per official docs §2.1):

```
snowflake://user:password@account/database/schema?warehouse=mywh&role=myrole
```

Where `account` is in one of these forms:
- `orgname-accountname` (preferred, per docs §1.1)
- `accountid` (legacy)
- `accountid.region` (legacy multi-region)
- `accountid.region.cloud` (legacy multi-cloud)

Optional URL parameters:
- `warehouse=COMPUTE_WH` — override the default warehouse
- `role=ANALYST` — override the default role
- `login_timeout=30` — seconds to wait for login (default 60)
- `network_timeout=120` — seconds for network operations

**Key**: The schema is the THIRD path segment (after database). If omitted, defaults to `PUBLIC`.

---

## §3. Authentication Methods

v0.1 supports URL-embedded username/password only (simplest, no custom auth code).

| Method | URL form | Status |
|--------|----------|--------|
| Username/Password | `snowflake://user:pass@account/db/schema` | ✅ v0.1 |
| Key-pair | `private_key_path=` URL param | Deferred to v0.5+ (ADR-010) |
| OAuth / Browser SSO | `authenticator=externalbrowser` | Deferred to v0.5+ (ADR-010) |
| Okta SSO | `authenticator=https://...okta.com/...` | Deferred to v0.5+ (ADR-010) |
| AWS IAM / Workload Identity | `authenticator=snowflake_jwt` | Deferred to v0.5+ (ADR-010) |

---

## §4. Error Codes Relevant to v0.1

From https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-error-codes:

| Code | Class | Trigger |
|------|-------|---------|
| 250001 | `ProgrammingError` | The account name does not exist |
| 251001 | `ProgrammingError` | Incorrect username or password |
| 251006 | `ProgrammingError` | User is disabled; contact administrator |
| 002003 | `ProgrammingError` | SQL compilation error: Table not found |
| 002043 | `ProgrammingError` | Statement reached its statement or warehouse timeout |
| 604 | `OperationalError` | Statement cancelled by user |
| (network) | `OperationalError` | Host unreachable / network timeout |

The `snowflake.connector` exception hierarchy:
```
snowflake.connector.errors.Error (base)
  ├── DatabaseError
  │     ├── ProgrammingError  ← SQL/auth/account errors
  │     ├── OperationalError  ← network/connection errors
  │     └── DataError         ← data type/value errors
  ├── InterfaceError          ← driver-level errors
  └── NotSupportedError       ← unsupported feature
```

---

## §5. dlt Integration Notes

The `sql_database` verified source (dlt==1.26.0) works with Snowflake via the standard SQLAlchemy dialect. No special Snowflake-specific dlt configuration is needed — the same `sql_table()` API applies.

```python
from dlt.sources.sql_database import sql_table

resource = sql_table(
    credentials="snowflake://user:pass@account/db/PUBLIC",
    table="orders",
    schema="PUBLIC",
    backend="sqlalchemy",
    reflection_level="full_with_precision",
)
```

**Key gotcha**: Snowflake table and column names default to UPPERCASE. Quoted identifiers preserve case. When passing `source_table`, use exact case.

**`dlt[snowflake]` extra installs**:
- `snowflake-connector-python` (~60 MB, contains C extensions for pure-Python auth)
- `snowflake-sqlalchemy` (thin SQLAlchemy dialect wrapper)

---

## §6. Type Mapping Considerations

Snowflake types → Iceberg types (via dlt reflection with `full_with_precision`):

| Snowflake | Arrow via dlt | Iceberg |
|-----------|--------------|---------|
| NUMBER(p,s) | decimal128(p,s) | DecimalType(p,s) |
| FLOAT / DOUBLE | float64 | DoubleType |
| VARCHAR(n) | string | StringType |
| BOOLEAN | bool_ | BooleanType |
| DATE | date32 | DateType |
| TIMESTAMP_NTZ | timestamp[us] | TimestampType(adjust_to_utc=False) |
| TIMESTAMP_TZ | timestamp[us, utc] | TimestampType(adjust_to_utc=True) |
| VARIANT / ARRAY / OBJECT | string (JSON-encoded) | StringType (v0.1 only) |
| BINARY | binary | BinaryType |

---

## §7. Known Limitations (v0.1 scope per ADR-019)

1. **Single table per call** — no multi-table pipeline in v0.1.
2. **Username/password auth only** — SSO, key-pair, OAuth deferred to v0.5+.
3. **`append` + `replace` write dispositions only** — `merge`/incremental deferred.
4. **No SSH/IAM/Vault integration** — deferred to ADR-010 (v0.5+).
5. **VARIANT/OBJECT/ARRAY columns** serialized as JSON strings (lossless but not typed).
6. **Large tables** — full-scan only; no incremental DML watermark in v0.1.

---

## §8. License

`snowflake-connector-python`: Apache-2.0 · GREEN (per ADR-007)
`snowflake-sqlalchemy`: Apache-2.0 · GREEN
`dlt[snowflake]`: Apache-2.0 · GREEN (same as core dlt)
