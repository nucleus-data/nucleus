---
title: Installation
description: Install Nucleus and its dependencies on macOS, Linux, or Windows.
---

# Installation

## System requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.11 | 3.11 |
| RAM | 4 GB | 8 GB |
| Disk | 2 GB free | 10 GB free |
| Docker Desktop | Optional | Required for full local stack |
| OS | macOS 12+, Ubuntu 22.04+, Windows 10/11 (WSL2) | — |

!!! note "Python version"
    Python 3.11 is the primary supported interpreter. Python 3.12 is tested but not the CI primary. Python 3.13 is not yet validated. See [`docs/internal/compatibility.md`](https://github.com/nucleus-data/nucleus/blob/main/docs/internal/compatibility.md).

## Install

=== "From PyPI (stable)"

    ```bash
    pip install nucleus
    ```

    PyPI packaging is in progress for v0.1. Until the first public release lands:

=== "From source (current)"

    ```bash
    git clone https://github.com/nucleus-data/nucleus.git
    cd nucleus
    python3.11 -m venv .venv
    source .venv/bin/activate        # Windows: .\.venv\Scripts\Activate.ps1
    pip install -e ".[dev]"
    ```

=== "With extras"

    ```bash
    # Core only
    pip install nucleus

    # Core + observability (OpenTelemetry SDK exporter)
    pip install "nucleus[observability]"

    # Core + advanced SQL lineage (sqlglot, for column-level lineage)
    pip install "nucleus[lineage-advanced]"

    # Everything (CI/development)
    pip install "nucleus[all]"
    ```

## Verify installation

```bash
nucleus version
```

Expected output (exact versions depend on your install):

```
nucleus          0.1.0
duckdb           1.1.3
polars           1.18.0
pyarrow          18.1.0
pyiceberg        0.11.1
dagster          1.9.5
```

If any version is missing, run `pip install -e ".[dev]"` again.

## Docker Desktop (for local storage)

Nucleus uses [SeaweedFS](https://github.com/seaweedfs/seaweedfs) (default) or MinIO (opt-in alternate) as the local S3-compatible object store. Docker Desktop must be running before `nucleus up`.

=== "macOS"

    [Download Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)

=== "Windows (WSL2)"

    [Download Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

    !!! tip "WSL2 backend"
        Enable the WSL2 backend in Docker Desktop settings. Nucleus performance on Windows is significantly better under WSL2 than native PowerShell.

=== "Linux"

    ```bash
    # Ubuntu / Debian
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    newgrp docker
    ```

## Extras matrix

| Extra | What it adds | When to use |
|-------|-------------|-------------|
| *(none)* | Core SDK + CLI + DuckDB + Polars + Iceberg | Default |
| `observability` | OpenTelemetry SDK + exporters | v0.5+ collector wiring |
| `lineage-advanced` | sqlglot for column-level lineage | v0.5+ column lineage |
| `dev` | pytest, mypy, ruff, pre-commit | Contributors |
| `docs` | MkDocs Material + plugins | Docs contributors |
| `all` | Everything | CI |

## Troubleshooting install

See [Install Issues](../troubleshooting/install-issues.md) and [Corporate Proxy](../troubleshooting/proxy-corporate-network.md) guides.
