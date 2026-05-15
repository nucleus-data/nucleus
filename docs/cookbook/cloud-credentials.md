# Cloud Credentials Cookbook

Secure credential setup for each Nucleus data source.

> **Principle (AGENTS.md Hard Constraint 6)**: Nucleus does not own identity. Delegate to your secret store (environment variables for local development, OIDC and vault-backed injection for production). See [`docs/decisions/ADR-010-oidc-delegation-policy-v03.md`](../decisions/ADR-010-oidc-delegation-policy-v03.md) for the v0.3+ OIDC policy.

> **Foundational patterns**: [`docs/patterns/secret_management.md`](../patterns/secret_management.md) (how `ctx.secrets`, `.env`, and redaction work).

> **Development**: Keep secrets in `.env.local` at the project root (gitignored). **Production**: inject secrets at process start from your vault (see [Vault integration patterns](#vault-integration-patterns)).

## What Nucleus reads from the environment (verified)

The Stage-1 ingest helpers under `src/nucleus/ctx/copy_from_*.py` behave as follows:

| Source | Env vars read by Nucleus ingest code | How credentials reach the driver |
| --- | --- | --- |
| PostgreSQL | *(none)* | Full URL string passed to `ctx.copy_from(..., source=...)` / `ingest_postgres_to_iceberg(conn_str=...)` |
| MySQL | *(none)* | Same: URL string only |
| Snowflake | *(none)* | Same: `snowflake://...` URL string only |
| Amazon S3 | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (surfaced in user-facing fix hints for auth/network paths) | DuckDB **httpfs** + standard AWS credential chain ([`copy_from_s3.py`](../../src/nucleus/ctx/copy_from_s3.py)) |
| Google Cloud Storage | `GOOGLE_APPLICATION_CREDENTIALS` (surfaced in user-facing fix hints) | **Application Default Credentials** via `gcsfs` ([`copy_from_gcs.py`](../../src/nucleus/ctx/copy_from_gcs.py)) |
| Local filesystem | *(none)* | POSIX permissions on paths you supply |

**Naming follow-up (consistency)**: Only the object-store branches name concrete `AWS_*` / `GOOGLE_APPLICATION_CREDENTIALS` variables in-repo. SQL sources expect you to **build the URL** in your CLI wrapper, shell, or `@nucleus.source` function. A future `NUCLEUS_*` prefix convention would be purely ergonomic unless wired in code.

---

## Source 1 — PostgreSQL

### Connection string format

`ctx.copy_from` and `ingest_postgres_to_iceberg` accept a SQLAlchemy-style URL. Nucleus normalises:

- `postgres://...` and `postgresql://...` → `postgresql+psycopg://...` (psycopg3 driver per SQLAlchemy)

Examples:

```text
postgresql://nucleus_reader:<PASSWORD>@db.example.com:5432/app_db?sslmode=require
postgres://nucleus_reader:<PASSWORD>@localhost:5432/app_db?sslmode=require
```

TLS: use `?sslmode=require` (or stricter modes) in the URL. See [PostgreSQL SSL libpq docs](https://www.postgresql.org/docs/current/libpq-ssl.html).

### Dev setup (`.env.local` + URL construction)

Nucleus does **not** read split `PG*` variables for you. A typical pattern is to store pieces in `.env.local` and expand them when invoking ingest or in Python:

```bash
# .env.local — gitignored (convention; not read automatically by ingest_postgres_to_iceberg)
PGHOST=localhost
PGPORT=5432
PGUSER=nucleus_reader
PGPASSWORD=<password>
PGDATABASE=app_db
```

Example (POSIX shell) appending TLS:

```bash
SOURCE_URL="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT}/${PGDATABASE}?sslmode=require"
```

Use URL-encoding if the password contains reserved characters (`encodeURIComponent` in Node, `urllib.parse.quote` in Python, etc.).

### Minimum-privilege Postgres role

Run as a privileged admin. Example grants for read-only ingest of existing relations in `public`:

```sql
create role nucleus_reader login password '<strong-password>';
grant connect on database app_db to nucleus_reader;
\c app_db
grant usage on schema public to nucleus_reader;
grant select on all tables in schema public to nucleus_reader;
alter default privileges in schema public grant select on tables to nucleus_reader;
```

Optional: logical replication / CDC (future incremental patterns outside Stage-1 single-table reads) may require `replication` privileges — scope that only when your ingest path requires it.

### Production

Mount secrets from Vault / cloud secret manager into the environment or a short-lived file, then build the same URL string (see [Vault integration patterns](#vault-integration-patterns)). Deploy context: [`docs/cookbook/production-deployment.md`](production-deployment.md).

### Common Nucleus errors (ingest)

Error codes are defined in [`src/nucleus/errors.py`](../../src/nucleus/errors.py). Typical mappings from [`_translate_dlt_postgres_exception`](../../src/nucleus/coordination/error_translation.py):

| Code | Meaning | What to check |
| --- | --- | --- |
| **NE1001** (`NucleusSourceConnectionError`) | Host, port, DNS, or database name | Network path; database exists; URL host/port |
| **NE1009** (`NucleusSourceAuthError`) | Rejected credentials | User / password in URL |
| **NE1010** (`NucleusNetworkError`) | TLS / SSL handshake | `sslmode`, CA files (`sslrootcert`), corporate TLS inspection |
| **NE1008** (`NucleusSourceNotFound`) | Relation missing | `table=` / schema qualification (`public.orders`) |
| **NE1004** (`NucleusSchemaEvolutionError`) | Column drift mid-ingest | Source DDL changed during read |

**NE2003** (`NucleusResourceError`) is a **resource limit** (for example memory), not authentication — see object-store sections.

---

## Source 2 — MySQL

### Connection string format

Prefix must be `mysql://` or `mysql+pymysql://`. Nucleus normalises bare `mysql://` → `mysql+pymysql://`.

```text
mysql://nucleus_reader:<PASSWORD>@db.example.com:3306/app_db
mysql+pymysql://nucleus_reader:<PASSWORD>@db.example.com:3306/app_db?ssl_disabled=false
```

Use TLS parameters appropriate to your server ([MySQL encrypted connections](https://dev.mysql.com/doc/refman/8.0/en/encrypted-connections.html)).

Qualified source names: pass `db.table` as the `table` argument to override the database segment from the URL, matching [`copy_from_mysql.py`](../../src/nucleus/ctx/copy_from_mysql.py).

### Dev setup (`.env.local` + URL construction)

```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=nucleus_reader
MYSQL_PASSWORD=<password>
MYSQL_DATABASE=app_db
```

Build the URL your application passes to `ctx.copy_from` / `ingest_mysql_to_iceberg`.

### Minimum-privilege MySQL user

```sql
create user 'nucleus_reader'@'%' identified by '<strong-password>';
grant select on app_db.* to 'nucleus_reader'@'%';
```

Narrow the host pattern from `'%'` to your runner IP / subnet where possible.

### Production

Same vault-injection pattern as Postgres; build the URL at startup.

### Common Nucleus errors (ingest)

From [`_translate_dlt_mysql_exception`](../../src/nucleus/coordination/error_translation.py): **NE1009** for access denied (**1045**), **NE1001** for unknown database (**1049**) or connect failures (**2003**), **NE1010** for SSL issues, **NE1008** for missing table (**1146**).

---

## Source 3 — Snowflake

Snowflake supports password authentication and **key-pair authentication**. Snowflake documents key-pair setup here: [Key-pair authentication](https://docs.snowflake.com/en/user-guide/key-pair-auth). SQL property syntax for assigning keys: [ALTER USER](https://docs.snowflake.com/en/sql-reference/sql/alter-user) (`RSA_PUBLIC_KEY`, `RSA_PUBLIC_KEY_2` for rotation).

### Nucleus v0.2 ingest path (password in URL today)

[`ingest_snowflake_to_iceberg`](../../src/nucleus/ctx/copy_from_snowflake.py) accepts URLs shaped for **Snowflake SQLAlchemy**, e.g.:

```text
snowflake://nucleus_reader:<PASSWORD>@orgname-accountname/analytics/public?warehouse=compute_wh&role=nucleus_reader_role
```

The path segments are `database` / `schema`. Optional query params include `warehouse` and `role`. See [Snowflake SQLAlchemy](https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy).

**Key-pair / JWT for the Snowflake Python connector is the production recommendation on the Snowflake side**, but the current Nucleus Stage-1 helper documents username-and-password via URL only. Until a later release wires connector-level private-key parameters through the same entry point, treat key-pair below as **account hardening + forward-looking** (JWT may already work if you pass a compatible URL or extend your own thin wrapper using the official connector docs).

### Generate RSA key pair (official OpenSSL flow)

Per Snowflake docs:

**Unencrypted private key (development-only; protect the file):**

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out nucleus_snowflake.p8 -nocrypt
```

**Encrypted private key (preferred on disk):**

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -v2 des3 -inform PEM -out nucleus_snowflake.p8
```

**Public key:**

```bash
openssl rsa -in nucleus_snowflake.p8 -pubout -out nucleus_snowflake.pub
```

**Register with Snowflake** — strip PEM headers/footers and paste the base64 body only:

```sql
alter user nucleus_user set rsa_public_key='MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...';
```

Verify fingerprint per [Snowflake key-pair troubleshooting](https://docs.snowflake.com/en/user-guide/key-pair-auth-troubleshooting).

### Minimum-privilege Snowflake role

```sql
create role nucleus_reader_role;
grant usage on warehouse compute_wh to role nucleus_reader_role;
grant usage on database analytics to role nucleus_reader_role;
grant usage on schema analytics.public to role nucleus_reader_role;
grant select on all tables in schema analytics.public to role nucleus_reader_role;
grant role nucleus_reader_role to user nucleus_user;
```

Unquoted identifiers fold to uppercase in Snowflake; the sample uses lowercase in DDL for readability.

### Key rotation (dual-register, then retire)

Snowflake supports two active keys (`RSA_PUBLIC_KEY` and `RSA_PUBLIC_KEY_2`) during rotation ([rotation topic](https://docs.snowflake.com/en/user-guide/key-pair-auth#configuring-key-pair-rotation)):

1. Generate a new pair locally.
2. `alter user nucleus_user set rsa_public_key_2='<new-key>'` (whichever slot is free).
3. Point clients at the new private key; smoke-test a query session.
4. `alter user nucleus_user unset rsa_public_key;` (or unset the old slot) once traffic moved.
5. Archive old private material securely.

---

## Source 4 — Amazon S3

### Environment variables

[`ingest_s3_to_iceberg`](../../src/nucleus/ctx/copy_from_s3.py) relies on DuckDB **httpfs** reading the **standard AWS environment variable names** cited in user-facing hints:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`

The same module notes `~/.aws/credentials` may be used via the normal chain. For behaviour details see [DuckDB httpfs / S3](https://duckdb.org/docs/extensions/httpfs/s3api).

### IAM policy (read-only to a prefix)

Minimal JSON policy (resource ARNs must match your bucket name). Schema per [IAM JSON policy elements](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements.html).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "NucleusReadObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::my-data-bucket",
        "arn:aws:s3:::my-data-bucket/*"
      ]
    }
  ]
}
```

Validate before deploy:

```bash
aws iam validate-policy --policy-document file://nucleus-s3-reader.json
```

### Dev / scripted IAM user

```bash
# .env.local
export AWS_ACCESS_KEY_ID=<access-key-id>
export AWS_SECRET_ACCESS_KEY=<secret-access-key>
export AWS_DEFAULT_REGION=us-east-1
```

### Production (IAM role, not long-lived keys)

Attach an instance profile (EC2), [IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) (EKS), or another workload identity so nothing long-lived sits on disk. See [IAM security best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html).

### S3-compatible endpoints (MinIO and others)

Nucleus `ingest_s3_to_iceberg` does **not** set DuckDB `s3_endpoint` / URL-style session parameters for you. For MinIO or other S3-compatible services you typically configure DuckDB httpfs (for example `s3_endpoint`, `s3_url_style`, `s3_use_ssl`) per [DuckDB S3 documentation](https://duckdb.org/docs/extensions/httpfs/s3api). Treat this as an advanced integration until a first-class option ships in `ctx.copy_from`.

---

## Source 5 — Google Cloud Storage

### URI scheme in Nucleus

The dispatcher accepts **`gs://`** (not `gcs://`). Example: `gs://my-bucket/data/orders.parquet`.

### Service account key file (dev / CI)

[`ingest_gcs_to_iceberg`](../../src/nucleus/ctx/copy_from_gcs.py) uses `gcsfs.GCSFileSystem()`, which resolves **Application Default Credentials**. The error translator explicitly points operators at:

- `GOOGLE_APPLICATION_CREDENTIALS` — path to a service account JSON key file

Official overview: [Service accounts](https://cloud.google.com/iam/docs/service-account-overview).

Example workflow:

```bash
gcloud iam service-accounts create nucleus-reader --display-name="Nucleus read-only"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:nucleus-reader@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
gcloud iam service-accounts keys create nucleus-reader.json \
  --iam-account="nucleus-reader@${PROJECT_ID}.iam.gserviceaccount.com"

export GOOGLE_APPLICATION_CREDENTIALS="/path/to/nucleus-reader.json"
```

### Production (no JSON keys on disk)

Prefer [Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity) on GKE, attached service accounts on Compute Engine, or other ADC sources that avoid downloadable long-lived JSON. `gcloud auth application-default login` is for developer workstations only.

### Common Nucleus errors (ingest)

**NE1009** for permission failures (HTTP 403), **NE1008** for missing objects, **NE1010** for networking / throttling, **NE2003** (`NucleusResourceError`) if DuckDB exceeds memory while scanning large globs — tighten partition sizes or raise engine limits per project config.

---

## Source 6 — Filesystem (local + NFS)

No cloud credentials. Use POSIX permissions (owner / group / mode) and mount options appropriate to your org.

**SELinux / AppArmor**: if reads return **NE1006** (`NucleusPermissionError`) despite correct Unix modes, check confined-domain policies on the path (common on RHEL / Fedora).

**Paths**: `file:///absolute/path/data.parquet`, relative paths, or globs — see [`copy_from_filesystem.py`](../../src/nucleus/ctx/copy_from_filesystem.py).

---

## Vault integration patterns

Nucleus does not embed Vault / cloud SDKs for secret fetch in the Stage-1 helpers. Standard pattern: your process entrypoint exports variables **before** importing Nucleus or invoking the CLI.

### Pattern 1 — HashiCorp Vault (env-var injection at startup)

```bash
export PGPASSWORD="$(vault kv get -field=password secret/data/nucleus/postgres)"
```

Build `postgresql://...` from those exports.

### Pattern 2 — AWS Secrets Manager

```bash
export PGPASSWORD="$(aws secretsmanager get-secret-value \
  --secret-id nucleus/postgres \
  --query SecretString --output text | jq -r .password)"
```

### Pattern 3 — GCP Secret Manager

```bash
export PGPASSWORD="$(gcloud secrets versions access latest --secret=nucleus-postgres-password)"
```

### Pattern 4 — Azure Key Vault (future + OIDC)

v0.3+ catalog and control-plane flows align with OIDC per ADR-010; pair Azure AD workload identity with Key Vault references when your platform team standardises the bootstrap.

---

## Key rotation policies

| Source | Suggested frequency | Mechanism |
| --- | --- | --- |
| PostgreSQL / MySQL | Quarterly (or on staff churn) | `alter role ... password`, `alter user ... identified by` |
| Snowflake | Quarterly | Dual `RSA_PUBLIC_KEY` / `RSA_PUBLIC_KEY_2` rotation per Snowflake docs |
| AWS IAM user keys | 90 days or less (org policy) | `aws iam create-access-key`, switch, `delete-access-key` |
| GCP service account keys | Avoid; if used, quarterly | Create new key JSON, redeploy, delete old key version |
| Vault tokens | Per policy | TTL, renewal, ephemeral sidecars |

---

## Audit logging

- **Nucleus lineage**: OpenLineage-backed materialization events record *what ran*; secrets must never appear in facets (see [`docs/patterns/secret_management.md`](../patterns/secret_management.md)).
- **Source systems**: enable Postgres `log_connections` / corporate DA tools, MySQL audit plugins, Snowflake `ACCOUNT_USAGE` views, S3 Server Access Logging, GCS Cloud Audit logs — federate in your SIEM.

---

## Anti-patterns (do not do)

- Commit `.env.local` or service account JSON (verify `.gitignore`).
- Use superuser / `ACCOUNTADMIN` style credentials for read-only ingest roles.
- Share the same password or key across dev/stage/prod.
- Disable TLS for Postgres or MySQL because "it is internal" — treat internal VLANs as hostile at the compliance layer.
- Paste secrets into `nucleus_project.yaml` / `nucleus.toml` tracked in git — non-secret config only.
- Rely on long-lived AWS user access keys on long-lived VMs — bind IAM roles instead.
- Assume **NE2003** means bad password — it signals **resource pressure** (`NucleusResourceError`), not auth.

---

## See also

- [`docs/patterns/secret_management.md`](../patterns/secret_management.md) — foundational secret patterns and `ctx.secrets`
- [`docs/cookbook/production-deployment.md`](production-deployment.md) — deployment context
- [`docs/cookbook/ai-copilot-setup.md`](ai-copilot-setup.md) — LLM provider credentials (Copilot path)
- [`AGENTS.md`](../../AGENTS.md) Hard Constraint 6 — no custom identity store inside Nucleus
- [`docs/decisions/ADR-010-oidc-delegation-policy-v03.md`](../decisions/ADR-010-oidc-delegation-policy-v03.md) — OIDC delegation policy
