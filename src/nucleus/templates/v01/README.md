# {project_name}

A Nucleus data project — generated {today}.

Built on the Nucleus local-first SDK + CLI: ship Iceberg-native pipelines
from a laptop, graduate cleanly to any Iceberg catalog when you outgrow it.

## Quick start

1. Boot the local stack (MinIO + filesystem catalog + asset registry):

   ```
   nucleus up
   ```

2. Materialize the example asset:

   ```
   nucleus run example.greeting
   ```

3. Query it:

   ```
   nucleus query "SELECT * FROM example.greeting"
   ```

## Local object storage

`docker-compose.yaml` declares a pinned MinIO container for laptop S3-compatible
blob storage (`minio/minio` on Docker Hub). Default dev credentials are
`minioadmin` / `minioadmin` — **never reuse these outside local development**.
Object files persist under `./data/minio/` (already covered by the `data/` gitignore rule).


- `assets/`              — `@nucleus.asset` definitions (your data products)
- `data/`                — local warehouse (gitignored)
- `nucleus_project.yaml` — project config (catalog, storage, lineage)

See https://nucleus.dev/quickstart for the 30-minute beachhead walkthrough
and `nucleus --help` for the full command surface.
