# Connect Superset / Evidence / Rill / Streamlit to Nucleus via `nucleus.db`

Every time you run `nucleus up`, Nucleus generates a DuckDB file at
`<project-root>/nucleus.db`.  This file contains one native DuckDB table per
materialised asset in your Iceberg catalog, plus a `_nucleus_catalog_info`
metadata table.  Any DuckDB-compatible BI tool can connect to it with a single
file path — no server, no REST catalog, no credentials.

> **Note**: `nucleus.db` is a snapshot at `nucleus up` time.  Re-run
> `nucleus up` after new materializations to refresh it.

---

## Superset

1. In Superset, go to **Settings → Database Connections → + Database**.
2. Choose **DuckDB** as the database driver.
3. Enter the connection string:

   ```
   duckdb:///<absolute-path-to-project>/nucleus.db
   ```

   Example on macOS/Linux:
   ```
   duckdb:////home/alice/my-stack/nucleus.db
   ```

   Example on Windows:
   ```
   duckdb:///C:/Users/alice/my-stack/nucleus.db
   ```

4. Click **Test Connection** → **Connect**.
5. Your asset tables (e.g. `raw__users`, `staging__orders`) appear immediately
   under the `main` schema.

**Required**: `pip install duckdb-engine` in your Superset environment.
Superset official DuckDB support: https://superset.apache.org/docs/databases/duckdb

---

## Evidence.dev

1. In your Evidence project, open `sources/nucleus/connection.yaml` (create if
   absent):

   ```yaml
   name: nucleus
   type: duckdb
   options:
     filename: /absolute/path/to/my-stack/nucleus.db
   ```

2. Reference your assets in Evidence pages:

   ```sql
   -- pages/index.md
   ```sql nucleus
   SELECT name, COUNT(*) AS orders
   FROM raw__orders
   GROUP BY name
   ```

Evidence DuckDB source: https://docs.evidence.dev/core-concepts/data-sources/duckdb

---

## Rill Developer

1. Add a source in `rill.yaml` or create `sources/nucleus.yaml`:

   ```yaml
   type: duckdb
   db: /absolute/path/to/my-stack/nucleus.db
   sql: SELECT * FROM raw__users
   ```

2. Run `rill dev` — Rill reads from `nucleus.db` directly.

Rill DuckDB source: https://docs.rilldata.com/reference/connectors/duckdb

---

## Streamlit

```python
import duckdb
import streamlit as st

DB_PATH = "/absolute/path/to/my-stack/nucleus.db"

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()
df = conn.execute("SELECT * FROM raw__users LIMIT 1000").df()
st.dataframe(df)
```

---

## View available assets

```sql
-- In any DuckDB client:
SELECT asset_key, duckdb_table, row_count, snapshot_id
FROM _nucleus_catalog_info
ORDER BY asset_key;
```

---

## Live views (advanced — requires DuckDB iceberg extension)

If you want live Iceberg reads (re-scanning the latest snapshot on every query)
instead of the boot-time snapshot, install the DuckDB iceberg extension and
create views manually:

```sql
-- Requires network access to install the extension once:
INSTALL iceberg;
LOAD iceberg;

-- Create a live view pointing at the Iceberg table location:
-- (find iceberg_location from _nucleus_catalog_info)
CREATE OR REPLACE VIEW live__raw__users AS
    SELECT * FROM iceberg_scan('s3://warehouse/raw/users/');
```

DuckDB iceberg extension docs: https://duckdb.org/docs/extensions/iceberg

---

*This page is auto-generated from ADR-026. Last updated: 2026-05-15.*
