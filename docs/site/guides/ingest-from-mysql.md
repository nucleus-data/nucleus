---
title: Ingest from MySQL
description: Pull data from MySQL or MariaDB into Iceberg using nucleus ingest.
---

# Ingest from MySQL

Nucleus supports MySQL and MariaDB via PyMySQL and SQLAlchemy.

## Prerequisites

- Nucleus core install (includes `pymysql==1.1.1`)
- MySQL connection string: `mysql+pymysql://user:password@host:port/database`

## CLI

```bash
nucleus ingest mysql+pymysql://user:password@localhost:3306/shop \
  --table orders \
  --as raw.orders \
  --mode overwrite
```

## Python SDK

```python
import nucleus.ctx as ctx

ctx.copy_from(
    "mysql+pymysql://user:password@localhost:3306/shop",
    table="orders",
    target="raw.orders",
)
```

!!! note "URI format"
    MySQL URIs use `mysql+pymysql://` rather than plain `mysql://` to select the PyMySQL driver explicitly. This matches SQLAlchemy's dialect+driver syntax.
    Docs: https://docs.sqlalchemy.org/en/20/dialects/mysql.html#module-sqlalchemy.dialects.mysql.pymysql

## Connection options

```bash
# With charset and connect_timeout
nucleus ingest "mysql+pymysql://user:pass@host/db?charset=utf8mb4&connect_timeout=10" \
  --table orders --as raw.orders
```

## Common errors

| Error | Code | Fix |
|-------|------|-----|
| `NucleusSourceConnectionError` | NE1001 | Check host/port/credentials; verify MySQL is running |
| `NucleusPermissionError` | NE1006 | `GRANT SELECT ON shop.orders TO 'nucleus'@'%'` |
| `NucleusSchemaError` | NE2001 | MySQL schema uses a type not yet supported; check column types |

## MariaDB

MariaDB is compatible with the MySQL driver:

```bash
nucleus ingest mysql+pymysql://user:pass@mariadb-host:3306/db \
  --table orders --as raw.orders
```
