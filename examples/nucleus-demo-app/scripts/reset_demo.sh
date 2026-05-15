#!/usr/bin/env bash
# Reset the Nucleus demo project to a pristine state.
#
# Tears down the docker-compose stack (with volumes), deletes the local
# warehouse + catalog files, and removes any cached run history. Safe to
# run from inside this directory.
#
# Usage:
#   bash scripts/reset_demo.sh

set -euo pipefail

cd "$(dirname "$0")/.."

echo ">>> docker compose down (removing volumes)"
docker compose down --volumes --remove-orphans 2>/dev/null || true

echo ">>> removing local warehouse + run history"
rm -rf data/warehouse
rm -rf data/minio
rm -rf data/postgres
rm -rf .nucleus

echo ">>> demo reset. To rehydrate:"
echo "    nucleus up"
echo "    python scripts/seed_postgres.py"
echo "    nucleus run bronze.orders   # then silver/gold in order"
