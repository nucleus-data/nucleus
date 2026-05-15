---
title: Install Issues
description: Diagnose and fix pip install failures for Nucleus.
---

# Install Issues

## Wrong Python version

```
ERROR: Requires-Python >=3.11,<3.13 but running Python 3.10
```

**Fix:** Install Python 3.11 and create a fresh venv:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

On macOS: `brew install python@3.11`
On Windows: Download from [python.org/downloads](https://www.python.org/downloads/)

## pip can't find a compatible version

```
ERROR: Could not find a version that satisfies the requirement duckdb==1.1.3
```

**Fix:** Upgrade pip first:

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

If on an older pip, the index may not return the right versions.

## Build wheel fails (native extensions)

```
error: command 'gcc' failed with exit status 1
```

Some packages (psycopg, duckdb) ship binary wheels but fall back to source compilation on unsupported platforms.

**Fix:**
- Use Python 3.11 (binary wheels are available)
- On Linux: `sudo apt-get install python3-dev libpq-dev`
- On macOS: `xcode-select --install`

## DuckDB fails to import after install

```
ImportError: DLL load failed while importing duckdb
```

**Windows only:** Install the [Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).

## Missing extras (mkdocstrings, etc.)

If you need to build docs:

```bash
pip install -e ".[docs]"
```

## Verify install

```bash
nucleus version
# Should show nucleus + all pinned dependencies
```

If `nucleus: command not found`, the venv is not activated:

```bash
source .venv/bin/activate   # macOS/Linux
.\.venv\Scripts\Activate.ps1  # Windows PowerShell
```
