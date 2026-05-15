# `data/`

Working directory for the demo. Two kinds of files live here:

| Path                | Tracked? | Purpose                                                    |
| ------------------- | -------- | ---------------------------------------------------------- |
| `seed/*.csv`        | yes      | Deterministic seed data shipped with the example.          |
| `warehouse/`        | no       | Local Iceberg warehouse (created by `nucleus run`).        |
| `minio/`            | no       | MinIO object-storage volume (created by `nucleus up`).     |
| `postgres/`         | no       | Postgres data directory (created by `docker compose up`).  |

The seed CSVs are committed so a fresh clone can rehydrate Postgres without
running the generator. To regenerate them (with a different RNG seed, larger
volumes, etc.), edit `scripts/generate_seed.py` and re-run it.
