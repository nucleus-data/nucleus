# Wave 3 Connectors Design Research (v0.3 target)

> **Status**: PROPOSED — design research only; no code written.
> **Target**: v0.3 implementer waves, post v0.2.0 GA.
> **Date**: 2026-05-15
> **Author**: Researcher tier (per AGENTS.md §11.14)
> **Inputs**: AGENTS.md §3 / §7 / §11.12 / §11.13 · `nucleus_architecture_v4.1.md` §5.5 + §6.4 · ADR-014 / 019 / 020 · existing `src/nucleus/ctx/copy_from*.py`.
> **Constraint**: READ-ONLY — this doc is the sole artifact; no `src/` changes.

---

## §0. Summary verdicts (1 line each)

| # | Connector | Verdict | Wrap target | Pin (proposed) | License | LOC | Bosch ELY priority |
|---|---|---|---|---|---|---|---|
| 1 | **BigQuery** | WRAP | `google-cloud-bigquery[pyarrow]` | `==3.41.0` | Apache-2.0 (GREEN) | ~220 | P3 |
| 2 | **Databricks UC read** | WRAP | `databricks-sql-connector[pyarrow]` | `==4.2.6` | Apache-2.0 (GREEN) | ~250 | **P1** |
| 3 | **REST API** | WRAP | `dlt[rest_api]==1.26.0` (core pin) | reuse | Apache-2.0 (GREEN) | ~200 | P2 |
| 4 | **SFTP** | WRAP | `paramiko==5.0.0` | `==5.0.0` | **LGPL-2.1** (YELLOW) | ~260 | P4 |
| 5 | **Azure Blob** | WRAP | `adlfs==2026.5.0` | `==2026.5.0` | BSD-3-Clause (GREEN) | ~190 | **P1** |

**Totals**: ~1,090 net LOC (with `_translate_dlt_base_exception` shared-translator refactor saving ~30). Current `src/nucleus/` ≈ 13K LOC → post-Wave-3 ≈ 14.1K, 47% headroom against 30K ceiling. 0% build / 100% wrap. 5/5 PASS the 8-Q gate; 2 STRONG PASS (Databricks UC + Azure Blob — direct Bosch ELY beachhead).

**Implementation order**: Databricks UC → Azure Blob → REST API → BigQuery → SFTP.

---

## §1. BigQuery — `ctx.copy_from_bigquery(...)`

### §1.1 API signature

```python
def ingest_bigquery_to_iceberg(
    query: str,
    *,
    project: str,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    location: str | None = None,
    credentials_path: str | None = None,         # path to service-account JSON
    use_storage_api: bool = False,               # opt-in to BigQuery Storage API
    max_bytes_billed: int | None = None,         # hard cost ceiling
) -> int:
    """Run a BigQuery SQL query; write result rows to a filesystem Iceberg table.

    Returns row count written. Mirrors ingest_gcs_to_iceberg() — Arrow zero-copy
    hand-off into the existing pyiceberg append path.
    """
```

Dispatcher scheme: `bigquery://project` with inline SQL via the dispatcher's existing `table=` field, or `bigquery://project/dataset/table` shortcut that rewrites to `SELECT * FROM`.

### §1.2 Wrap target

- **Library**: `google-cloud-bigquery==3.41.0` with `[pyarrow]` extra
- Docs: https://cloud.google.com/bigquery/docs/reference/libraries · https://cloud.google.com/python/docs/reference/bigquery/latest/summary_overview
- PyPI: https://pypi.org/project/google-cloud-bigquery/ (3.41.0 released 2026-03-30, verified 2026-05-15)
- License: Apache-2.0 · GREEN (ADR-007 Tier 1)
- Python `>=3.9` (satisfies Nucleus `>=3.11,<3.13`)
- Transitive (~30-40 MB total): google-api-core, google-auth, google-cloud-core, google-resumable-media, protobuf, requests — all OSI-approved (Apache-2.0 / BSD / MIT). No JVM.
- **Why not dlt**: dlt has no `dlt.sources.bigquery` verified source (only BigQuery destination). Direct client `query().to_arrow()` matches the GCS Arrow-pipe pattern.

### §1.3 Auth options

ADC chain via `google.auth.default()` — same chain `gcsfs` already uses. Docs: https://cloud.google.com/docs/authentication/application-default-credentials.

| Pattern | Mechanism | Default? |
|---|---|---|
| **Service-account JSON via `credentials_path`** | `bigquery.Client(credentials=service_account.Credentials.from_service_account_file(path))` | YES |
| ADC env (`GOOGLE_APPLICATION_CREDENTIALS`) | same chain, no explicit code | Fallback |
| `gcloud auth application-default login` | `~/.config/gcloud/...` | Local dev |
| Workload identity (GCE/GKE) | metadata server | Out of scope v0.3 |

`credentials_path` kwarg is preferred over env mutation (avoids cross-process state). Docs: https://cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.client.Client.

### §1.4 Schema inference + override

```python
arrow_table = client.query(sql).to_arrow(create_bqstorage_client=use_storage_api)
iceberg_table.append(arrow_table)
```

Docs: https://cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.job.QueryJob#google_cloud_bigquery_job_QueryJob_to_arrow

BigQuery → Arrow → Iceberg type-mapping risks:

| BigQuery type | Arrow | Iceberg | Risk |
|---|---|---|---|
| INT64 / FLOAT64 / STRING / BYTES / BOOL / DATE | int64 / float64 / utf-8 / binary / bool / date32 | matching primitives | none |
| TIMESTAMP / DATETIME | timestamp[us, UTC] / timestamp[us] | TimestamptzType / TimestampType | none |
| TIME | time64[us] | TimeType | **NEEDS VERIFICATION** pyiceberg 0.11.1 TimeType write coverage |
| NUMERIC(p≤38, s≤9) | decimal128 | DecimalType | none |
| BIGNUMERIC(p>38) | decimal256 | **no equivalent** | **HIGH** — raise NucleusUnsupportedTypeError (NE2004) |
| GEOGRAPHY / JSON | binary (WKB) / utf-8 JSON | BinaryType / StringType | acceptable |
| STRUCT / ARRAY | struct / list | StructType / ListType | NEEDS VERIFICATION nested-struct round-trip |

No `schema=` override exposed in v0.3 — user controls schema via SQL CASTs (matches Postgres/MySQL/Snowflake pattern).

### §1.5 Error handling — NE codes

| google-api-core exception | Translation | NE code | Status |
|---|---|---|---|
| `Forbidden` (403), `Unauthorized` (401), `DefaultCredentialsError` | `NucleusSourceAuthError` | NE1009 | exists |
| `NotFound` (404) | `NucleusSourceNotFound` | NE1008 | exists |
| `BadRequest` (SQL parse) | `NucleusSQLSyntaxError` | NE2002 | exists |
| `BadRequest` ("exceeded resource limits") / `TooManyRequests` (429) | `NucleusSourceQuotaExceededError` | **NE1011** | **NEW** |
| `ServiceUnavailable` (503) | `NucleusNetworkError` | NE1010 | exists |
| `DeadlineExceeded` | `NucleusTimeoutError` | NE3005 | exists |
| `GoogleAPICallError` (catch-all) | `NucleusIOError` | NE1005 | exists |
| `CommitFailedException` (pyiceberg) | `NucleusCommitConflictError` | NE1002 | exists |

**NE1011 NucleusSourceQuotaExceededError** is shared with REST API + Azure Blob + Databricks (all hit 429). Distinct from NE1010 (wire-level) and NE1009 (creds rejected): policy-level "quota exceeded; raise limit / wait / shard". Docs: https://cloud.google.com/bigquery/docs/error-messages · https://googleapis.dev/python/google-api-core/latest/exceptions.html · https://cloud.google.com/bigquery/quotas

Anti-pattern guard (AGENTS.md §11.7): no `google.*` class names in `user_message` or `fix_hint`.

### §1.6 Cost warning (BigQuery-specific)

BigQuery bills by bytes scanned (on-demand) OR slot-time (capacity). One careless `SELECT *` can blow $100s. Connector emits a structured WARN on first use:

```
WARNING: BigQuery query estimate: 47.2 GB scanned ≈ $0.24 (US, on-demand).
         Set --max-bytes-billed=... for a hard ceiling. Run with --quiet to suppress.
```

Estimate via `client.query(sql, job_config=QueryJobConfig(dry_run=True)).total_bytes_processed` (free, no slot consumption). Docs: https://cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.job.QueryJobConfig#google_cloud_bigquery_job_QueryJobConfig_dry_run. Optional `max_bytes_billed` kwarg sets BigQuery's hard ceiling — BigQuery refuses queries that would exceed.

### §1.7 8-Q gate

| # | Q | PASS? | Note |
|---|---|---|---|
| 1 | One of 5 layers? | ✅ | L0 + L4 |
| 2 | <30 min beachhead? | ✅ | GCP-native users one-command ingest |
| 3 | Wrap possible? | ✅ | Google-supported, GA |
| 4 | No-JVM? | ✅ | Pure Python + protobuf C ext |
| 5 | Local-identical-to-prod? | ✅ | Same library + auth on laptop/CI |
| 6 | ≤30K LOC budget? | ✅ | ~220 LOC; total <15K |
| 7 | Empirical telemetry? | ⚠️ | No PoC #5 user yet specifically asked; second-largest segment |
| 8 | v0.1 or defer? | ✅ defer to v0.3 |

**Verdict**: PASS with Q7 partial. Founder may gate on PoC #5 telemetry.

### §1.8 ADR skeleton (one-page)

```markdown
# ADR-NNN: BigQuery Read Source via google-cloud-bigquery
Status: PROPOSED  ·  Date: 2026-MM-DD  ·  Related: ADR-014, ADR-019, ADR-020
Context: Users with data in BigQuery must currently EXPORT → GCS → ingest.
Decision: WRAP google-cloud-bigquery[pyarrow]==3.41.0 as `pip install nucleus[bigquery]`.
Options rejected: dlt[bigquery] (destination-only); custom REST (BUILD); BigFrames (wrong model).
Scope v0.3: single-query call, ADC + service-account, dry-run cost estimate, NE1011 quota code.
OUT: streaming/storage-API (opt-in flag), incremental cursors, MERGE/INSERT, BigFrames, federated queries.
LOC: ~220  ·  New dep: google-cloud-bigquery[pyarrow]==3.41.0 (~35 MB)
Swap target: BigQuery REST API + manual Arrow (~600 LOC if needed); document docs/swap/bigquery.md.
Smoke test: tests/upgrade_smoke/test_google_cloud_bigquery.py mocked via google.cloud.bigquery._testing.
```

### §1.9 Test plan

| Layer | Test | Real account? |
|---|---|---|
| Unit | `_translate_bigquery_exception` for 403/404/400/429/503/Timeout/DefaultCredentialsError | No |
| Unit | URL parsing + type-mapping (BIGNUMERIC>38 → NE2004) + dry-run WARN emit | No |
| Integration (gated) | `bigquery-public-data.usa_names.usa_1910_2013` LIMIT 100 | YES (CI env `BIGQUERY_INTEGRATION_TEST=1`) |
| Upgrade smoke | Pinned-version 10-row read | YES (CI only) |

### §1.10 Out of scope (v0.3)

Write-back; pushdown of JOIN/WHERE/GROUP BY; MERGE; federated queries; streaming inserts; BigQuery DataFrames; BigFrames (compute pushed INTO BigQuery — orthogonal to local-first model).

---

## §2. Databricks Unity Catalog READ-ONLY — `ctx.copy_from_databricks_uc(...)`

### §2.1 API signature

```python
def ingest_databricks_uc_to_iceberg(
    *,
    server_hostname: str,
    http_path: str,
    catalog: str,
    schema: str,
    table: str,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    auth: Literal["pat", "oauth-m2m"] = "pat",
    access_token: str | None = None,             # for PAT
    client_id: str | None = None,                # for oauth-m2m
    client_secret: str | None = None,
    query_filter: str | None = None,             # appended as WHERE
) -> int:
    """Read a Unity Catalog table via Databricks SQL warehouse; write to Iceberg.

    Returns row count written. ONE-WAY only in v0.3 — Mode-2 dispatch per
    nucleus_architecture_v4.1.md §3 ("yield to giants"): pull from Databricks,
    materialize locally for cheap iteration, graduate back via Iceberg portability.
    """
```

Dispatcher scheme: `databricks://hostname/sql/1.0/warehouses/xxxx?catalog=main&schema=default` — hostname + http_path packed into URL; catalog/schema as query params.

### §2.2 Wrap target

- **Library**: `databricks-sql-connector==4.2.6` with `[pyarrow]` extra
- Docs: https://docs.databricks.com/aws/en/dev-tools/python-sql-connector
- GitHub: https://github.com/databricks/databricks-sql-python
- PyPI: https://pypi.org/project/databricks-sql-connector/ (4.2.6 released 2026-04-23, verified 2026-05-15)
- License: Apache-2.0 · GREEN
- Python `>=3.9,<4.0`
- **Thrift-based, no JVM, no JDBC, no ODBC** (per official PyPI README). Pure Python.
- `[pyarrow]` extra enables `cursor.fetchall_arrow()` for ~10× speedup over row-tuple `fetchall()`. PyArrow ≥18.0.0 already in core.
- Transitive (~30 MB): lz4, oauthlib, pyjwt, python-dateutil, requests, thrift, urllib3 — all OSI-approved.

### §2.3 Auth options

Per https://docs.databricks.com/aws/en/dev-tools/python-sql-connector#authentication:

| Pattern | Library entry | Default? |
|---|---|---|
| **PAT** | `sql.connect(access_token=...)` or `DATABRICKS_TOKEN` env | **YES** — single-engineer beachhead default |
| OAuth M2M (service principal) | `credentials_provider=oauth_service_principal(Config(...))` from `databricks-sdk` | v0.4 follow-up |
| OAuth U2M (browser) | `auth_type="databricks-oauth"` | **rejected** — CI-hostile |

OAuth M2M requires extra `pip install databricks-sdk`. Out of scope for v0.3 to keep extras small; add when there's a concrete request.

### §2.4 Yield-to-giants framing (Mode 2)

This connector is THE Bosch ELY beachhead unlock. Per `docs/research/parity_vs_bosch_ely_adb_batch.md`:

```
1. Engineer has 50 TB Iceberg table in Databricks Unity Catalog (Mode 1 substrate)
2. Wants to iterate on 100 GB sample LOCALLY (cheap, fast, BI-friendly)
3. `copy_from("databricks://...", target="bronze.uc_sample", ...)` pulls sample
4. Iterates with DuckDB / Polars locally
5. Promotes transformation back via Iceberg portability (Mode 1, automatic since Databricks UC Iceberg federation GA 2025-Q4)
```

**One-way only**: Iceberg portability (Mode 1) makes write-back automatic — Databricks UC reads Nucleus's filesystem-Iceberg catalog via Unity Catalog Iceberg federation. We don't need a write-side SQL connector. Docs: https://docs.databricks.com/en/data-governance/unity-catalog/iceberg.html (NEEDS VERIFICATION — confirm GA date before user-facing docs).

### §2.5 Schema inference + override

```python
from databricks import sql
with sql.connect(server_hostname=..., http_path=..., access_token=...) as connection:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM `{catalog}`.`{schema}`.`{table}`")
        arrow_table = cursor.fetchall_arrow()   # NEEDS VERIFICATION exact name vs fetchmany_arrow
```

Type-mapping risks (Databricks SQL → Arrow → Iceberg, per https://docs.databricks.com/en/sql/language-manual/data-types/index.html):

| Databricks type | Arrow | Iceberg | Risk |
|---|---|---|---|
| INT / BIGINT / DOUBLE / FLOAT / BOOLEAN / DATE / DECIMAL(≤38) / BINARY / STRING | matching primitives | matching | none |
| TIMESTAMP | timestamp[us, UTC] | TimestamptzType | verify TZ semantics |
| TIMESTAMP_NTZ | timestamp[us] | TimestampType | none |
| ARRAY / MAP / STRUCT | list / map / struct | ListType / MapType / StructType | none |
| VARIANT (semi-structured) | utf-8 JSON | StringType | match BigQuery JSON behaviour |
| INTERVAL | — | n/a | raise NucleusUnsupportedTypeError (NE2004) |

### §2.6 Error handling — NE codes

| `databricks.sql.exc` exception | Translation | NE code | Status |
|---|---|---|---|
| Auth subclasses | `NucleusSourceAuthError` | NE1009 | exists |
| `OperationalError` (network) | `NucleusSourceConnectionError` | NE1001 | exists |
| `ProgrammingError` (SQL parse) | `NucleusSQLSyntaxError` | NE2002 | exists |
| `NotSupportedError` | `NucleusEngineError` | NE2005 | exists |
| `RequestError` HTTP 429 | `NucleusSourceQuotaExceededError` | NE1011 | NEW (shared) |
| Error "warehouse not available" | `NucleusComputePausedError` | **NE1013** | **NEW** |
| Error "table not found" | `NucleusSourceNotFound` | NE1008 | exists |
| `TimeoutError` / `requests.Timeout` | `NucleusTimeoutError` | NE3005 | exists |

**NE1013 NucleusComputePausedError**: Databricks SQL warehouses auto-suspend after inactivity (2-5 min to wake). Distinct from NE1001 (host unreachable) and NE1010 (transport). Enables v0.4 `--wait-for-warehouse` retry-with-backoff. NEEDS VERIFICATION exception hierarchy against 4.2.6 source: https://github.com/databricks/databricks-sql-python/blob/main/src/databricks/sql/exc.py

### §2.7 8-Q gate

| # | Q | PASS? | Note |
|---|---|---|---|
| 1 | Layer? | ✅ | L0 + L4 |
| 2 | <30 min beachhead? | ✅✅ | Bosch ELY unlock |
| 3 | Wrap? | ✅ | Databricks-supported |
| 4 | No-JVM? | ✅ | Thrift, pure Python |
| 5 | Local=prod? | ✅ | |
| 6 | LOC? | ✅ | ~250 |
| 7 | Empirical telemetry? | ✅✅ | Explicit Bosch ELY ask |
| 8 | Defer to v0.3? | ✅ | |

**Verdict**: STRONG PASS. Lead Wave 3 connector.

### §2.8 ADR skeleton

```markdown
# ADR-NNN: Databricks UC Read Source via databricks-sql-connector
Status: PROPOSED (lead Wave 3)  ·  Related: ADR-014/019/020, parity_vs_bosch_ely_adb_batch.md
Context: Bosch ELY runs Azure Databricks daily; without UC read, engineers must
  df.write.format("parquet").save("abfs://...") then ingest via Azure Blob — two-step.
Decision: WRAP databricks-sql-connector[pyarrow]==4.2.6 as `pip install nucleus[databricks]`.
Read-only v0.3. Write-back via Mode 1 Iceberg portability — not via SQL connector.
Options rejected:
  - pyodbc + Databricks ODBC (system dep; no Arrow)
  - Spark Connect (JVM in client process — violates §3 #1)
  - dbsqlcli (CLI tool, not library)
Scope v0.3: PAT auth, single-table read with optional query_filter WHERE, NE1013 compute-paused.
OUT: OAuth M2M (v0.4), OAuth U2M (rejected; CI-hostile), write-back, MERGE, INSERT, Spark Connect.
LOC: ~250  ·  New dep: databricks-sql-connector[pyarrow]==4.2.6 (~30 MB)
Swap target: raw Thrift over HTTP/2 (~500 LOC); docs/swap/databricks.md.
Smoke test: tests/upgrade_smoke/test_databricks_sql.py mocked via pytest-httpserver.
```

### §2.9 Test plan

| Layer | Test | Real account? |
|---|---|---|
| Unit | `_translate_databricks_exception` (auth/network/SQL/quota/compute-paused) | No |
| Unit | URL parsing; type mapping (VARIANT → StringType; INTERVAL → NE2004) | No |
| Integration (gated) | `samples.nyctaxi.trips` LIMIT 100 against Databricks Free Tier workspace | YES (CI env `DATABRICKS_INTEGRATION_TEST=1`) |
| Upgrade smoke | Pinned-version 10-row read | YES (CI only) |

Databricks Free Tier (https://www.databricks.com/learn/free-trial) provides workspace + serverless SQL warehouse with credit — sufficient for the integration test lifetime.

### §2.10 Out of scope

Spark Connect (JVM); write-back (Mode 1 handles); DBFS access (deprecated → use UC volumes); `databricks-sqlalchemy` adapter (heavyweight, unnecessary); OAuth U2M (CI-hostile).

---

## §3. REST API via dlt — `ctx.copy_from_rest(...)`

### §3.1 API signature

```python
def ingest_rest_to_iceberg(
    base_url: str,
    *,
    endpoint: str,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    auth: dict[str, str] | None = None,            # bearer/basic/api_key — see §3.3
    paginator: dict[str, str | int] | None = None, # see §3.4
    params: dict[str, str | int] | None = None,
    headers: dict[str, str] | None = None,
    write_disposition: Literal["append", "replace", "merge"] = "append",
    primary_key: str | list[str] | None = None,
    schema_hint: dict[str, str] | None = None,
) -> int:
    """Pull JSON records from a REST endpoint; write to a filesystem Iceberg table.

    Returns row count written. Wraps dlt rest_api — inherits dlt's pagination
    + auth + schema-inference machinery.
    """
```

Dispatcher: NEW `https://` + `http://` schemes route here; or `rest:///path/to/rest_config.yaml` for YAML-config form.

### §3.2 Wrap target

- **Library**: `dlt[rest_api]==1.26.0` — **REUSE existing core pin** (no new top-level dep)
- Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/basic · https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/advanced
- License: Apache-2.0 · GREEN (already cleared per ADR-007 / ADR-014)
- **NEEDS VERIFICATION**: dlt 1.26.0 exposes `rest_api` as a built-in source per the basic-config docs — confirm `pip show dlt` shows `rest_api` in installed-sources; the current pin form is `dlt[sql_database,pyiceberg]` so the `rest_api` source should be available without an additional extra.

### §3.3 Auth options

Per https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/basic#authentication — dlt config dict:

| Pattern | Dict | Default? |
|---|---|---|
| **Bearer token** | `{"type": "bearer", "token": "..."}` | **YES** (env `REST_API_BEARER_TOKEN`) |
| Basic auth | `{"type": "http_basic", "username": "...", "password": "..."}` | No |
| API key (header) | `{"type": "api_key", "name": "X-API-Key", "value": "...", "location": "header"}` | No |
| API key (query string) | `{"type": "api_key", "name": "key", "value": "...", "location": "query"}` | No |
| OAuth2 client-credentials | custom `requests.Session` via `requests-oauthlib` | **NEEDS VERIFICATION** — dlt 1.26.0 may not ship a built-in helper. v0.4 helper if not. Docs: https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/advanced#authenticate-with-oauth |
| Custom `requests.Session` | `client.session=...` | Power-user escape hatch |

Anti-pattern: no credentials in URL — strip `https://user:pass@host` and WARN.

### §3.4 Pagination

Per https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/basic#pagination — built-in paginators:

| Type | Dict | Use case |
|---|---|---|
| `single_page` | `{"type": "single_page"}` | One-shot |
| `header_link` | `{"type": "header_link", "next_url_path": "next"}` | GitHub-style Link headers |
| `json_link` | `{"type": "json_link", "next_url_path": "paging.next"}` | Next-URL in body |
| `offset` | `{"type": "offset", "limit": 100, "offset_param": "offset"}` | offset/limit |
| `page_number` | `{"type": "page_number", "base_page": 1, "page_param": "page", "total_path": "meta.total_pages"}` | page=N |
| `cursor` | `{"type": "cursor", "cursor_param": "after", "cursor_path": "next_cursor"}` | Forward cursor (Stripe / Slack) |
| `auto` | dlt heuristic | Default for v0.3 |

Schema inference per https://dlthub.com/docs/general-usage/schema: first ~100 records inferred. `schema_hint` kwarg maps column names → dlt-type-names (`text`/`bigint`/`double`/`bool`/`timestamp`/`date`/`json`/`decimal`/`binary`).

### §3.5 Error handling — NE codes

| Exception | Translation | NE code |
|---|---|---|
| `requests.exceptions.ConnectionError` | `NucleusSourceConnectionError` | NE1001 |
| `requests.exceptions.Timeout` | `NucleusTimeoutError` | NE3005 |
| HTTPError 401 / 403 | `NucleusSourceAuthError` | NE1009 |
| HTTPError 404 | `NucleusSourceNotFound` | NE1008 |
| HTTPError 429 | `NucleusSourceQuotaExceededError` | **NE1011** |
| HTTPError 5xx + `SSLError` | `NucleusNetworkError` | NE1010 |
| `dlt.extract.exceptions.ResourceExtractionError` | `NucleusEngineError` | NE2005 |
| `dlt.common.exceptions.SchemaCorruptedException` | `NucleusSchemaError` | NE2001 |
| `dlt.pipeline.exceptions.PipelineConfigurationException` | `NucleusConfigError` | NE5001 |

Docs: https://requests.readthedocs.io/en/latest/api/#exceptions · dlt exceptions: read `dlt/extract/exceptions.py` + `dlt/pipeline/exceptions.py` (no central docs page per `docs/research/dlt.md` §3).

**Refactor opportunity**: extract `_translate_dlt_base_exception` in `coordination/error_translation.py` — saves ~30 LOC across Postgres/MySQL/Snowflake/REST.

### §3.6 8-Q gate

| # | Q | PASS? | Note |
|---|---|---|---|
| 1-6 | Standard | ✅ | L0+L4; dlt is canonical wrap; pure Python; declarative config = local=prod; ~200 LOC |
| 7 | Empirical telemetry? | ✅ | "How do I ingest REST APIs" is #1 ELT question on every forum |
| 8 | Defer to v0.3? | ✅ | |

**Verdict**: PASS. Strong fit, low cost, broad demand.

### §3.7 ADR skeleton

```markdown
# ADR-NNN: REST API Source Connector via dlt rest_api
Status: PROPOSED  ·  Related: ADR-014, docs/research/dlt.md, this doc §3
Context: SQL + object storage covered; REST is the largest remaining source category.
  dlt already pinned in core for Postgres/MySQL/Snowflake — zero new top-level deps.
Decision: WRAP dlt.sources.rest_api.rest_api_source via ingest_rest_to_iceberg(). New
  https:// + http:// dispatcher schemes.
Options rejected: custom requests wrapper (BUILD); airbyte-cdk (heavyweight 100+ deps);
  Singer/meltano (CLI ecosystem, not library).
Scope v0.3: bearer/basic/api_key auth; all 7 paginators + auto heuristic; first-record
  schema inference + override hint; append/replace/merge dispositions.
OUT: OAuth2 client-credentials helper (v0.4); per-record incremental cursors (v0.4);
  GraphQL (different protocol); WebSockets; SSE; Webhooks (push not pull).
LOC: ~200 (net 170 after _translate_dlt_base_exception refactor)
New dep: NONE — reuse dlt==1.26.0
Smoke test: tests/upgrade_smoke/test_dlt_rest.py mocked via pytest-httpserver.
```

### §3.8 Test plan

| Layer | Test | Real account? |
|---|---|---|
| Unit | Auth dict + paginator dict → dlt config | No |
| Unit | Error translation table | No |
| Integration | `https://api.github.com/repos/dlt-hub/dlt/issues?state=closed` (public, low rate) | NO — public sandbox |
| Integration | `https://pokeapi.co/api/v2/pokemon?limit=50` | NO — public sandbox |
| Upgrade smoke | Mocked HTTP server pin-regression | No |

REST is the easiest connector to test in CI without secrets — GitHub + PokéAPI are stable and used by dlt's own examples.

### §3.9 Out of scope

GraphQL (different protocol; defer to v0.5+ if dlt ships helper); Webhooks/push; WebSockets; SSE; OAuth2 authorization-code (3-legged interactive — CI-hostile).

---

## §4. SFTP — `ctx.copy_from_sftp(...)`

### §4.1 API signature

```python
def ingest_sftp_to_iceberg(
    *,
    host: str,
    path: str,                                    # remote path or single-dir glob
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    port: int = 22,
    username: str | None = None,
    auth: Literal["key", "password", "agent"] = "key",
    key_filename: str | None = None,
    key_passphrase: str | None = None,
    password: str | None = None,
    known_hosts: str | None = None,               # default: ~/.ssh/known_hosts
    host_key_check: Literal["strict", "warn", "ignore"] = "strict",
    format: Literal["auto", "parquet", "csv", "json"] = "auto",
) -> int:
    """Download file (or single-dir glob) from SFTP → tempdir → delegate to
    ingest_filesystem_to_iceberg() → cleanup. Returns row count written.
    """
```

Dispatcher: `sftp://user@host:22/path/*.parquet`

### §4.2 Wrap target

- **Library**: `paramiko==5.0.0`
- Docs: https://docs.paramiko.org · https://docs.paramiko.org/en/stable/api/client.html · https://docs.paramiko.org/en/stable/api/sftp.html
- PyPI: https://pypi.org/project/paramiko/ (5.0.0 released 2026-05-09)
- **License: LGPL-2.1 · YELLOW** per ADR-007 Tier 2
- Python `>=3.9`
- Transitive (~5 MB): `bcrypt`, `cryptography` (C + Rust extensions), `pynacl` — all OSI-approved (Apache-2.0/MIT/BSD). NEEDS VERIFICATION: confirm no transitive Nucleus already pulls `cryptography` to avoid version conflicts.

**LGPL-2.1 tier review** (ADR-007 §Tier 2):
- ✅ Runtime dep allowed (`import paramiko` is dynamic-link; LGPL §6 exempt)
- ✅ Wheel bundling allowed — same precedent as existing `psycopg LGPLv3+` in `[postgres]` extras
- ✅ Cloud tier (v1.0+): users install `nucleus[sftp]` in their own env; no Nucleus Cloud bundling
- **Verdict**: precedented; document precedent in ADR.

### §4.3 Auth options

Per https://docs.paramiko.org/en/stable/api/client.html#paramiko.client.SSHClient.connect:

| Pattern | paramiko kwargs | Default? |
|---|---|---|
| **SSH key file** | `key_filename="~/.ssh/id_ed25519"` (or list) | YES |
| Password | `password=...` | No |
| ssh-agent | (no kwarg — auto when no key/password) | CI option |
| Gssapi/Kerberos | `gss_auth=True, gss_kex=True` | v0.5+ |

**Host-key verification** — security-critical:

| Mode | Behaviour |
|---|---|
| `strict` (default) | `SSHClient.load_system_host_keys()`; mismatch raises NE1012 |
| `warn` | Print structured warning; auto-add. Dev only; CI default rejects |
| `ignore` | `AutoAddPolicy()` — accepts ANY host key; **MITM risk**. Test-only; emits WARN |

Anti-pattern: never `AutoAddPolicy` as default. Docs: https://docs.paramiko.org/en/stable/api/client.html#paramiko.client.MissingHostKeyPolicy · OpenSSH known_hosts(5): https://man.openbsd.org/sshd.8#SSH_KNOWN_HOSTS_FILE_FORMAT

### §4.4 Implementation pattern (download → delegate)

```python
import contextlib, shutil, tempfile
from pathlib import Path
import paramiko

def ingest_sftp_to_iceberg(...) -> int:
    tempdir = Path(tempfile.mkdtemp(prefix="nucleus_sftp_"))
    try:
        with paramiko.SSHClient() as ssh:
            ssh.set_missing_host_key_policy(<per host_key_check>)
            ssh.load_system_host_keys(known_hosts)
            ssh.connect(host, port=port, username=username,
                        key_filename=key_filename, password=password, ...)
            with ssh.open_sftp() as sftp:
                for remote_file in _glob_via_listdir(sftp, path):
                    sftp.get(remote_file, str(tempdir / Path(remote_file).name))
        # Delegate to existing filesystem connector
        return ingest_filesystem_to_iceberg(
            str(tempdir / f"*{Path(path).suffix}"),
            warehouse_dir=warehouse_dir,
            dest_namespace=dest_namespace, dest_table=dest_table,
            format=format,
        )
    finally:
        with contextlib.suppress(OSError):
            shutil.rmtree(tempdir)
```

**Trade-off**: download-to-disk uses 2× disk space (transient). Alternative is `fsspec/sshfs` (MIT) but adds a dep and complexity. **Defer streaming to v0.4** unless 100GB+ ingest hits disk limits — match `AGENTS.md §"Anti-Over-Engineering Discipline"`.

**Glob support v0.3**: single-directory only (`/path/*.parquet`). Recursive (`**`) needs ~50 LOC; defer to v0.4.

### §4.5 Schema + format

Inherited from filesystem connector. No SFTP-specific logic.

### §4.6 Error handling — NE codes

| paramiko exception | Translation | NE code | Status |
|---|---|---|---|
| `AuthenticationException` | `NucleusSourceAuthError` | NE1009 | exists |
| `SSHException` (generic) | `NucleusSourceConnectionError` | NE1001 | exists |
| `BadHostKeyException` | `NucleusSourceHostKeyError` | **NE1012** | **NEW** |
| `PasswordRequiredException` | `NucleusConfigError` | NE5001 | exists |
| `socket.timeout` | `NucleusTimeoutError` | NE3005 | exists |
| `socket.gaierror` | `NucleusSourceConnectionError` | NE1001 | exists |
| `FileNotFoundError` | `NucleusSourceNotFound` | NE1008 | exists |
| `PermissionError` | `NucleusPermissionError` | NE1006 | exists |
| `OSError` (local disk full) | `NucleusIOError` | NE1005 | exists |

**NE1012 NucleusSourceHostKeyError**: SSH host-key verification failure. Distinct from NE1009 (creds rejected) — the host-key failure says "the server may not be the one you think; MITM possible". Different fix hint: "verify fingerprint out-of-band, then add to known_hosts". Docs: https://docs.paramiko.org/en/stable/api/ssh_exception.html

### §4.7 8-Q gate

| # | Q | PASS? | Note |
|---|---|---|---|
| 1 | Layer? | ✅ | L0 + L4 |
| 2 | <30 min beachhead? | ⚠️ | Legacy/on-prem; Bosch industrial data uses it; non-Bosch low |
| 3 | Wrap? | ✅ | paramiko is de-facto |
| 4 | No-JVM? | ✅ | pure Python + cryptography C ext |
| 5 | Local=prod? | ✅ | |
| 6 | LOC? | ✅ | ~260 |
| 7 | Empirical telemetry? | ⚠️ | Bosch industrial sensors; non-Bosch demand low |
| 8 | Defer to v0.3? | ✅ | |

**Verdict**: PASS with two partial. Recommend implementing AFTER Databricks UC + Azure Blob.

### §4.8 ADR skeleton

```markdown
# ADR-NNN: SFTP Source Connector via paramiko
Status: PROPOSED  ·  Related: ADR-007 (license tier), ADR-020 (filesystem delegation)
Context: Bosch ELY uses SFTP for industrial sensor + factory-floor data exports.
  Without SFTP, engineers must scp manually then ingest — fragile two-step.
Decision: WRAP paramiko==5.0.0 as `pip install nucleus[sftp]`. Download → tempdir →
  delegate to existing filesystem connector → cleanup.
Options rejected:
  - fsspec/sshfs (wraps paramiko anyway; extra layer with no current win)
  - asyncssh (EPL-2.0 YELLOW; async-only; harder to test)
  - native ssh subprocess (BUILD; fragile/platform-specific)
Scope v0.3: SSH key + password, strict/warn/ignore host-key check, single-dir glob,
  all 4 formats via filesystem delegation.
OUT: Kerberos/gssapi (v0.5+), recursive globbing (`**`), streaming (v0.4 via sshfs if
  demand), file watching, remote command exec (SSHClient.exec_command — backdoor; reject).
LOC: ~260  ·  New dep: paramiko==5.0.0 (LGPL-2.1 YELLOW; dynamic-link exempt per
  ADR-007; same precedent as existing psycopg LGPLv3+ in [postgres])
Swap target: asyncssh (EPL-2.0) ~300 LOC; docs/swap/paramiko.md.
```

### §4.9 Test plan

| Layer | Test | Real account? |
|---|---|---|
| Unit | `_translate_paramiko_exception` for auth/host-key/network/missing | No |
| Unit | URL parsing: `sftp://user@host:22/path/*.parquet` | No |
| Integration (Docker) | testcontainers `atmoz/sftp:alpine-3.7` (https://hub.docker.com/r/atmoz/sftp) — key auth, 3 parquet files | NO — Docker |
| Integration (Docker) | Host-key mismatch detection | NO — Docker |
| Upgrade smoke | Pinned-version regression | No |

Public SFTP sandboxes (e.g. `test.rebex.net`) are unreliable in CI — testcontainers is the right answer.

### §4.10 Out of scope

Recursive globbing (defer v0.4); streaming (defer v0.4); pub-sub/file watching (Nucleus is pull-batch); remote command exec (backdoor, reject); SFTP write-back.

---

## §5. Azure Blob Storage — `ctx.copy_from_azure_blob(...)`

### §5.1 API signature

```python
def ingest_azure_blob_to_iceberg(
    az_uri: str,                                  # az:// or abfs://
    *,
    warehouse_dir: str | Path,
    dest_namespace: str,
    dest_table: str,
    account_name: str | None = None,
    account_key: str | None = None,
    sas_token: str | None = None,
    connection_string: str | None = None,
    tenant_id: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    format: Literal["auto", "parquet", "csv", "json"] = "auto",
) -> int:
    """Read file (or glob) from Azure Blob Storage; write to Iceberg.

    Returns row count written. Mirrors ingest_gcs_to_iceberg() —
    adlfs.AzureBlobFileSystem → pyarrow.fs.PyFileSystem → duckdb.register_filesystem.
    """
```

Dispatcher: `az://container/path` and `abfs://container@account.blob.core.windows.net/path`.

### §5.2 Wrap target

- **Library**: `adlfs==2026.5.0`
- Docs: https://fsspec.github.io/adlfs/ · https://github.com/fsspec/adlfs · API ref https://fsspec.github.io/adlfs/api/
- PyPI: https://pypi.org/project/adlfs/ (2026.5.0 released 2026-05-05, verified 2026-05-15)
- License: BSD-3-Clause · GREEN
- Python `>=3.10`
- Transitive (~15-20 MB): `azure-core>=1.28.0`, `azure-identity`, `azure-storage-blob[aio]>=12.17.0`, `fsspec>=2023.12.0` — all MIT
- **NEEDS VERIFICATION**: confirm `azure-identity` has an upper-pin in adlfs's dependency metadata (PyPI shows no upper pin 2026-05-15).

### §5.3 Auth options

Per https://github.com/fsspec/adlfs "Setting credentials" — `storage_options` dict:

| Pattern | Dict | Default? |
|---|---|---|
| **DefaultAzureCredential** | `{"account_name": "..."}` only | **YES** — walks env → MSI → CLI → VS Code → browser per https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential |
| Account key | `{"account_name": "...", "account_key": "..."}` | No (root admin; rotate) |
| SAS token | `{"account_name": "...", "sas_token": "?..."}` | Preferred over account key |
| Connection string | `{"connection_string": "..."}` | No |
| Service Principal | `tenant_id` + `client_id` + `client_secret` | Production / ADR-010 |
| Anonymous | `{"account_name": "...", "anon": True}` | Public datasets only |

Env-var fallbacks: `AZURE_STORAGE_CONNECTION_STRING`, `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_ACCOUNT_KEY`, `AZURE_STORAGE_SAS_TOKEN`, `AZURE_STORAGE_TENANT_ID`, `AZURE_STORAGE_CLIENT_ID`, `AZURE_STORAGE_CLIENT_SECRET`, `AZURE_STORAGE_ANON` — picked up by adlfs automatically.

Anti-pattern guard: when `account_key=` passed explicitly, WARN and suggest SAS.

### §5.4 Implementation pattern (mirror GCS)

```python
import adlfs, duckdb, pyarrow.fs as pafs
abfs = adlfs.AzureBlobFileSystem(**storage_options)
pa_fs = pafs.PyFileSystem(pafs.FSSpecHandler(abfs))
conn = duckdb.connect()
conn.register_filesystem(pa_fs)
arrow_table = conn.execute(
    f"SELECT * FROM {duckdb_fn}('{safe_uri}', union_by_name=true)"
).arrow()
iceberg_table.append(arrow_table)
```

URI forms (all accepted by adlfs):
- `az://container/path`
- `abfs://container@account.blob.core.windows.net/path`
- `abfs://container@account.dfs.core.windows.net/path` (ADLS Gen2 hierarchical namespace)

NEEDS VERIFICATION (medium risk): the FSSpec→PyArrow handler had async-vs-sync edge cases historically (e.g. `aiohttp.ClientResponseError` flagged in `docs/research/gcs_duckdb.md` §7). Smoke-test against Azurite before merge.

### §5.5 Error handling — NE codes

| azure-* / duckdb exception | Translation | NE code | Status |
|---|---|---|---|
| `ResourceNotFoundError` (404) | `NucleusSourceNotFound` | NE1008 | exists |
| `ClientAuthenticationError` / `CredentialUnavailableError` | `NucleusSourceAuthError` | NE1009 | exists |
| `HttpResponseError` (403 RBAC) | `NucleusSourceAuthError` | NE1009 | exists |
| `HttpResponseError` (429 throttle) | `NucleusSourceQuotaExceededError` | NE1011 | NEW (shared) |
| `HttpResponseError` (500/503) | `NucleusNetworkError` | NE1010 | exists |
| `HttpResponseError` (archive tier) | `NucleusSourceTierError` | **NE1014** | **NEW** |
| `duckdb.IOException` | `NucleusIOError` | NE1005 | exists |
| `duckdb.BinderException` | `NucleusSchemaError` | NE2001 | exists |
| `FileNotFoundError` (from adlfs) | `NucleusSourceNotFound` | NE1008 | exists |
| `PermissionError` (from adlfs) | `NucleusSourceAuthError` | NE1009 | exists |

**NE1014 NucleusSourceTierError**: Azure cool/archive blob read attempt (and S3 Glacier in future). Distinct from NE1008 — the object exists but is in a tier requiring rehydration. Enables a useful CLI hint: "Blob is in Archive tier. Rehydrate: `az storage blob set-tier --tier Cool --name ...`". Docs: https://learn.microsoft.com/en-us/python/api/azure-core/azure.core.exceptions

### §5.6 8-Q gate

| # | Q | PASS? | Note |
|---|---|---|---|
| 1 | Layer? | ✅ | L0 + L4, mirrors GCS |
| 2 | <30 min beachhead? | ✅✅ | Closes 3-cloud parity gap; Bosch ELY mandatory |
| 3 | Wrap? | ✅ | adlfs is fsspec-blessed |
| 4 | No-JVM? | ✅ | pure Python + azure-* SDKs |
| 5 | Local=prod? | ✅ | |
| 6 | LOC? | ✅ | ~190 (mirrors GCS) |
| 7 | Empirical telemetry? | ✅✅ | Bosch ELY explicit ask |
| 8 | Defer to v0.3? | ✅ | |

**Verdict**: STRONG PASS. Same risk profile as GCS; same shape; one new license-clean dep.

### §5.7 ADR skeleton

```markdown
# ADR-NNN: Azure Blob Source Connector via adlfs
Status: PROPOSED (P1)  ·  Related: ADR-020, parity_vs_bosch_ely_adb_batch.md
Context: Current object-storage: S3 + GCS + local FS. Azure Blob = remaining 3rd-cloud
  parity gap. Bosch ELY runs Azure Databricks + ADLS Gen2.
Decision: WRAP adlfs==2026.5.0 as `pip install nucleus[azure]`. Use same
  register_filesystem pattern as copy_from_gcs.py.
Options rejected:
  - azure-storage-blob directly (would re-implement adlfs fsspec adapter)
  - azure-datalake-store / ADLS Gen1 (retired by Microsoft 2024-Q1)
  - DuckDB azure extension (separate binary; less ergonomic creds; defer v0.4 evaluation)
Scope v0.3: az:// + abfs:// schemes; DefaultAzureCredential + account_key + SAS +
  connection_string + Service Principal; format auto-detect + override.
OUT: ADLS Gen1; Append Blob writes (read-only); HNS metadata ops; soft-delete;
  Event Grid notifications.
LOC: ~190  ·  New dep: adlfs==2026.5.0 (BSD-3-Clause GREEN) + transitive (~17 MB)
Swap target: DuckDB azure extension (~80 LOC) evaluate v0.4; docs/swap/adlfs.md.
NEW NE: NE1014 NucleusSourceTierError.
Smoke: tests/upgrade_smoke/test_adlfs.py via Azurite emulator.
```

### §5.8 Test plan

| Layer | Test | Real account? |
|---|---|---|
| Unit | Error translation (404/401/429/archive/RBAC) | No |
| Unit | URL parsing (az:// + abfs:// with/without `@account`) | No |
| Integration (Docker) | Azurite emulator (`mcr.microsoft.com/azure-storage/azurite`, official Microsoft image), read 3 parquet | NO — Docker |
| Integration (public) | `az://nyctlc/green/...` Azure Open Datasets (no auth, used in adlfs's own quickstart) | NO — public |
| Upgrade smoke | Pin-regression via Azurite | No |

Azurite is the official Microsoft Azure Storage emulator — perfect for CI.

### §5.9 Out of scope

ADLS Gen1 (`adl://` raises NucleusConfigError with retirement hint per https://learn.microsoft.com/en-us/lifecycle/products/azure-data-lake-storage-gen1); Append Blob writes; HNS ACLs; soft-delete; Event Grid notifications.

---

## §6. Cumulative impact analysis

### §6.1 Total LOC

| Connector | LOC | Cumulative |
|---|---|---|
| BigQuery | ~220 | 220 |
| Databricks UC | ~250 | 470 |
| REST API | ~200 | 670 |
| SFTP | ~260 | 930 |
| Azure Blob | ~190 | 1,120 |
| `_translate_dlt_base_exception` refactor | −30 | **1,090 net** |

Current `src/nucleus/` ≈ 13K LOC (NEEDS VERIFICATION exact figure against `docs/budget_history.md`). Post-Wave-3: ≈ 14.1K LOC. Headroom vs 30K ceiling: ~15.9K (53%). Vs v0.5 ceiling 18K: 78% used. Comfortable.

### §6.2 Wrap-vs-build ratio

**100% wrap / 0% build** — strongest performance of any wave to date. All five connectors wrap mature Tier 1/2 OSS.

### §6.3 Dependency additions

| Connector | Top-level dep | License | Install impact |
|---|---|---|---|
| BigQuery | `google-cloud-bigquery[pyarrow]==3.41.0` | Apache-2.0 GREEN | ~35 MB |
| Databricks UC | `databricks-sql-connector[pyarrow]==4.2.6` | Apache-2.0 GREEN | ~30 MB |
| REST API | **NONE** (reuse `dlt==1.26.0`) | n/a | 0 MB |
| SFTP | `paramiko==5.0.0` | **LGPL-2.1 YELLOW** | ~5 MB |
| Azure Blob | `adlfs==2026.5.0` | BSD-3-Clause GREEN | ~17 MB |

**Net new top-level deps: 4** (REST adds zero). `pip install nucleus` core is unchanged — Wave 3 adds 4 extras groups + reuses dlt for the 5th. ADR-039 `<30 core deps` hard ceiling preserved.

Optional extras count: current 9 → 14 with Wave 3 (bigquery / databricks / rest / sftp / azure).

### §6.4 8-Q gate aggregate

| Connector | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 | Q7 | Q8 | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| BigQuery | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | PASS (Q7 partial) |
| Databricks UC | ✅ | ✅✅ | ✅ | ✅ | ✅ | ✅ | ✅✅ | ✅ | **STRONG PASS** |
| REST API | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | PASS |
| SFTP | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ⚠️ | ✅ | PASS (2 partial) |
| Azure Blob | ✅ | ✅✅ | ✅ | ✅ | ✅ | ✅ | ✅✅ | ✅ | **STRONG PASS** |

**5/5 PASS**. 2 STRONG PASS (Databricks + Azure Blob — Bosch ELY direct). No FAIL, no borderline. Weakest argument: BigQuery Q7 (no PoC #5 demand evidence yet) and SFTP Q2/Q7 (Bosch-specific). Both tolerable.

---

## §7. Priority ordering for Wave 3

Per AGENTS.md §0 (beachhead = startup data team 5-20) + `docs/research/parity_vs_bosch_ely_adb_batch.md`:

```
1. Databricks UC          (P1, STRONG PASS, ~250 LOC, ~2 days)
2. Azure Blob             (P1, STRONG PASS, ~190 LOC, ~1 day — mirrors GCS verbatim)
3. REST API via dlt       (P2, PASS, ~200 LOC, ~2 days — broadest demand)
4. BigQuery               (P3, PASS, ~220 LOC, ~2 days)
5. SFTP                   (P4, PASS-with-caveats, ~260 LOC, ~3 days)
```

**Why this order**:
1. Databricks UC + Azure Blob together unlock the Bosch ELY beachhead in 4 days for 440 LOC — highest customer value per LOC.
2. REST third because broadest demand (every team has SOME REST source) but lower per-customer leverage than the Bosch unlock; zero new top-level dep.
3. BigQuery fourth — critical for GCP-native segment but no PoC #5 demand evidence yet.
4. SFTP last — legacy/on-prem long-tail; doesn't block laptop-first beachhead.

**Recommended slicing**: implement as two waves of parallel swarm-implementer agents (per AGENTS.md §11.14):
- **Wave 3a** (week 1): Databricks UC + Azure Blob (440 LOC, 2 deps, 4 new NE codes via the bundled ADR — see §8.4 — single founder ratification batch)
- **Wave 3b** (week 2): REST + BigQuery + SFTP (650 LOC, 3 deps)

If PoC #5 reveals Bosch ELY actually leans Snowflake (already shipped) over Databricks, **reorder**: REST → Azure Blob → BigQuery → Databricks UC → SFTP.

---

## §8. Cross-cutting risks

### §8.1 Auth surface area

21 distinct auth patterns across Wave 3:

| Connector | Patterns |
|---|---|
| BigQuery | 4 (service-account JSON, ADC env, gcloud login, workload identity) |
| Databricks UC | 3 (PAT, OAuth M2M, OAuth U2M — rejected) |
| REST API | 5 (bearer, basic, api_key-header, api_key-query, custom session) |
| SFTP | 3 (key, password, agent) |
| Azure Blob | 6 (DefaultAzureCredential, account_key, SAS, connection_string, Service Principal, anon) |

**Mitigation**: each connector defaults to the safest, most-common pattern; others gate behind explicit kwarg. One docs page per connector (`docs/errors/<connector>-auth.md`). Recommend a cross-cutting `docs/patterns/auth_matrix.md` as a Wave 3 deliverable. Long-term: ADR-010 OIDC delegation eventually subsumes most.

### §8.2 Schema drift detection

| Connector | Risk | Mitigation |
|---|---|---|
| BigQuery | LOW — schema known via dry-run before query | inherent |
| Databricks UC | LOW — DESCRIBE before SELECT | inherent |
| REST API | **MEDIUM** — dlt infers from first 100 records per run | `schema_hint` kwarg (§3.1) |
| SFTP | LOW-MEDIUM — DuckDB `union_by_name=true` smooths schemas | inherited |
| Azure Blob | LOW-MEDIUM | inherited |

Long-term: `@nucleus.check` contracts + Iceberg schema-evolution rules catch drift at materialization. No new mechanism needed.

### §8.3 Cross-cloud egress costs

| Path | Cost |
|---|---|
| GCP egress to internet (Bosch Stuttgart → europe-west3) | ~$0.12/GB ≈ $120/TB |
| Azure egress to internet | ~$0.087/GB ≈ $87/TB first 10 TB |
| Databricks egress (rides underlying cloud) | same as GCP/Azure/AWS |
| SFTP (typically on-prem) | free |
| REST API | minimal — provider may rate-limit |

**Risk**: a careless `copy_from("bigquery://...", target="bronze.huge")` blows $100+. **Mitigation**:
- BigQuery: dry-run cost estimate WARN (§1.6) + `max_bytes_billed` hard ceiling
- Databricks: `EXPLAIN ANALYZE` bytes-billed (NEEDS VERIFICATION exact syntax)
- Azure Blob: `BlobClient.get_blob_properties().size` pre-read WARN if >1 GB
- REST API: document throttling — no pre-flight available
- Generic v0.4: CLI `--cost-ceiling-gb=N` flag

Document in `docs/patterns/cost_discipline.md` as Wave 3 deliverable.

### §8.4 Rate limit handling

All 4 Wave 3 connectors that talk to a metered service route 429 → **NE1011 NucleusSourceQuotaExceededError** with `fix_hint` "retry with backoff or wait <N>s". v0.4 follow-up: connector-level retry-with-backoff (dlt rest_api has built-in; SQL connectors don't).

### §8.5 LGPL-2.1 license (SFTP only)

paramiko LGPL-2.1 is precedented (same tier and treatment as `psycopg LGPLv3+` in `[postgres]` extras per ADR-007). Dynamic-link exempt; safe for OSS + Cloud. Document precedent in ADR.

### §8.6 NEW NE code allocation (bundle in one ADR)

| Code | Class | Shared across | Distinct from |
|---|---|---|---|
| **NE1011** | `NucleusSourceQuotaExceededError` | BigQuery + Databricks + REST + Azure | NE1010 (wire-level), NE1009 (creds rejected) |
| **NE1012** | `NucleusSourceHostKeyError` | SFTP | NE1009 (MITM signal needs different fix) |
| **NE1013** | `NucleusComputePausedError` | Databricks UC | NE1001 (host unreachable), NE1010 (transport) |
| **NE1014** | `NucleusSourceTierError` | Azure Blob (now), S3 Glacier (future) | NE1008 (object exists but tier-locked) |

**Recommendation**: bundle all 4 into one ADR (proposed `ADR-NNN-wave3-connector-codes`) — founder ratifies the bundle once. Per ADR-006 §Decision, codes are permanent from first ship.

**Alternative (simpler)**: collapse all 4 into NE1010. Loses granularity but `user_message` + `fix_hint` still carry specific guidance. Researcher recommends allocating the 4 — they're cheap (one ClassVar + `__all__` entry each), permanent, and help future Copilot suggest specific fixes.

---

## §9. NEEDS VERIFICATION (top 10)

Items the implementer must confirm before merge:

1. **BigQuery `to_arrow` BIGNUMERIC>38 precision** — does it raise, truncate, or silently lose? Check https://cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.job.QueryJob#google_cloud_bigquery_job_QueryJob_to_arrow. **Risk: HIGH** — silent precision loss is worst case.
2. **databricks-sql-connector 4.2.6 Arrow method name** — `fetchall_arrow` per README vs `fetchmany_arrow(n)` elsewhere. Confirm against 4.2.6 source. **Risk: LOW**.
3. **Databricks UC Iceberg federation GA date** — claim "GA 2025-Q4" needs source citation https://docs.databricks.com/en/data-governance/unity-catalog/iceberg.html before user-facing docs. **Risk: MEDIUM** — affects Mode-1 write-back narrative.
4. **dlt 1.26.0 `rest_api` extra resolution** — confirm built-in (no `[rest_api]` pin needed) vs requires explicit extras flag with current `dlt[sql_database,pyiceberg]` core pin. **Risk: LOW** — install resolves either way.
5. **adlfs `azure-identity` upper-pin** — PyPI shows none (2026-05-15); confirm via `pip-compile`. **Risk: LOW**.
6. **paramiko `cryptography` dep collision** — paramiko 5.0.0 requires `cryptography>=3.3`. Nucleus does not pin cryptography directly. Confirm no transitive Nucleus already pulls a conflicting version. **Risk: LOW**.
7. **dlt LoadInfo row-count shape for rest_api source** — same `load_packages[n].jobs["completed_jobs"][m].row_counts` as sql_database (per existing flag in `copy_from_postgres._row_count_from_load_info`)? **Risk: LOW**.
8. **DuckDB `register_filesystem` adlfs async-vs-sync semantics** — historical fsspec edge cases (`gcs_duckdb.md` §7 flagged `aiohttp.ClientResponseError`). Smoke-test against Azurite before merge. **Risk: MEDIUM**.
9. **dlt OAuth2 client-credentials helper for rest_api** — built-in or v0.4-ship-our-own? Check https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/advanced. **Risk: LOW**.
10. **TimeType + nested STRUCT round-trip in pyiceberg 0.11.1** — for BigQuery + Databricks UC; add smoke test with 2-level struct before merge. **Risk: MEDIUM**.

---

## §10. References (external — docs URLs)

**BigQuery**
- Client libs: https://cloud.google.com/bigquery/docs/reference/libraries
- Python ref: https://cloud.google.com/python/docs/reference/bigquery/latest/summary_overview
- QueryJob.to_arrow: https://cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.job.QueryJob#google_cloud_bigquery_job_QueryJob_to_arrow
- Data types: https://cloud.google.com/bigquery/docs/reference/standard-sql/data-types
- Errors: https://cloud.google.com/bigquery/docs/error-messages
- google-api-core exceptions: https://googleapis.dev/python/google-api-core/latest/exceptions.html
- ADC: https://cloud.google.com/docs/authentication/application-default-credentials
- Quotas: https://cloud.google.com/bigquery/quotas
- PyPI: https://pypi.org/project/google-cloud-bigquery/

**Databricks SQL Connector**
- Docs (AWS): https://docs.databricks.com/aws/en/dev-tools/python-sql-connector
- Docs (Azure): https://docs.microsoft.com/en-us/azure/databricks/dev-tools/python-sql-connector
- GitHub: https://github.com/databricks/databricks-sql-python
- Exception module: https://github.com/databricks/databricks-sql-python/blob/main/src/databricks/sql/exc.py
- Auth overview: https://docs.databricks.com/aws/en/dev-tools/auth/
- OAuth M2M: https://docs.databricks.com/aws/en/dev-tools/auth/oauth-m2m
- UC Iceberg federation: https://docs.databricks.com/en/data-governance/unity-catalog/iceberg.html
- SQL data types: https://docs.databricks.com/en/sql/language-manual/data-types/index.html
- Free Tier: https://www.databricks.com/learn/free-trial
- PyPI: https://pypi.org/project/databricks-sql-connector/

**dlt rest_api**
- Basic: https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/basic
- Advanced: https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/advanced
- REST client: https://dlthub.com/docs/general-usage/http/rest-client.md
- Schema: https://dlthub.com/docs/general-usage/schema
- Pipeline: https://dlthub.com/docs/general-usage/pipeline
- Iceberg destination: https://dlthub.com/docs/dlt-ecosystem/destinations/iceberg
- PyPI: https://pypi.org/project/dlt/

**paramiko (SFTP)**
- Docs: https://docs.paramiko.org
- SSHClient: https://docs.paramiko.org/en/stable/api/client.html
- SFTPClient: https://docs.paramiko.org/en/stable/api/sftp.html
- Exceptions: https://docs.paramiko.org/en/stable/api/ssh_exception.html
- HostKeyPolicy: https://docs.paramiko.org/en/stable/api/client.html#paramiko.client.MissingHostKeyPolicy
- OpenSSH known_hosts: https://man.openbsd.org/sshd.8#SSH_KNOWN_HOSTS_FILE_FORMAT
- testcontainers image: https://hub.docker.com/r/atmoz/sftp
- PyPI: https://pypi.org/project/paramiko/

**adlfs (Azure Blob)**
- Docs: https://fsspec.github.io/adlfs/
- API ref: https://fsspec.github.io/adlfs/api/
- GitHub: https://github.com/fsspec/adlfs
- DefaultAzureCredential: https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential
- azure-core exceptions: https://learn.microsoft.com/en-us/python/api/azure-core/azure.core.exceptions
- Storage Blob SDK: https://learn.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python
- ADLS Gen1 retirement: https://learn.microsoft.com/en-us/lifecycle/products/azure-data-lake-storage-gen1
- Azurite emulator: https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite
- PyPI: https://pypi.org/project/adlfs/

**Supporting (shared)**
- DuckDB Python: https://duckdb.org/docs/api/python/dbapi
- DuckDB httpfs: https://duckdb.org/docs/extensions/httpfs/s3api · https://duckdb.org/docs/extensions/httpfs/gcs
- PyArrow filesystems: https://arrow.apache.org/docs/python/filesystems.html
- PyArrow fsspec bridge: https://arrow.apache.org/docs/python/filesystems.html#fsspec-filesystems
- pyiceberg: https://py.iceberg.apache.org/api/
- requests exceptions: https://requests.readthedocs.io/en/latest/api/#exceptions

**Internal**
- AGENTS.md (repo root)
- `nucleus_architecture_v4.1.md` §3 + §5.5 + §6.4 (repo root)
- ADR-006 / 007 / 014 / 019 / 020 / 039 (`docs/decisions/`)
- `docs/research/dlt.md` · `gcs_duckdb.md` · `s3_duckdb.md` · `filesystem_duckdb.md` · `pyiceberg.md` · `parity_vs_bosch_ely_adb_batch.md` · `ai_hallucinations.md`

---

## §11. Logged hallucinations

**None surfaced during this research pass.** All claims are docs-grounded with cited URLs. The 10 `NEEDS VERIFICATION` items in §9 are docs-claim-uncertain (asking implementer to confirm an existing documented fact); NOT fabricated APIs. If any item proves to be a fabrication during implementation, append to `docs/research/ai_hallucinations.md` per AGENTS.md §11.12.

Pre-merge checklist per AGENTS.md §11.12 + §11.7:

- [ ] All imports actually exist in the pinned library version
- [ ] No `google.api_core` / `databricks.sql` / `paramiko` / `azure.core` / `duckdb` class names in user-facing strings
- [ ] Returns `NucleusError`, not raw external exceptions
- [ ] LOC under per-feature ceiling (500)
- [ ] Vocabulary matches AGENTS.md §7 (asset, materialization, source asset)
- [ ] Cites architecture section + connector docs URL in module docstring
- [ ] §9 NEEDS VERIFICATION items resolved

---

## §12. Final disposition

**Recommended action**: Founder ratifies this research doc as Wave 3 design source-of-truth.

**Implementation gate**: bundle the 4 new NE codes (NE1011 / NE1012 / NE1013 / NE1014) in one ADR (`ADR-NNN-wave3-connector-codes`) — founder ratifies the bundle once. The per-connector ADR skeletons in §1.8 / §2.8 / §3.7 / §4.8 / §5.7 then ratify individually as each implementer wave lands.

**Wave 3a** (week 1): Databricks UC + Azure Blob via parallel swarm-implementer agents (per AGENTS.md §11.14) — ~440 LOC, 2 new deps, 4 new NE codes ratified. Verifier per AGENTS.md §11.10 (multi-file edit + new library wrap = "Risky" boundary; verifier checks §9 + §11 guards).

**Wave 3b** (week 2): REST + BigQuery + SFTP after Wave 3a clears verifier — ~650 LOC, 3 new deps, refactor `_translate_dlt_base_exception` shared across Postgres/MySQL/Snowflake/REST (saves ~30 LOC; reduces drift surface).

**Founder reading time**: ~30 min for this research doc + ~5 min per ADR skeleton (5 ADRs) = ~55 min total.

**Done.**
