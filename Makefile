# ============================================================================
# Nucleus — Makefile
# ============================================================================
# Cross-platform-ish dev shortcuts. On Windows, install GNU Make via
# `winget install GnuWin32.Make`, OR use the PowerShell equivalents shown
# next to each target.
#
# Standard targets you'll use daily:
#   make install        # set up dev environment
#   make test           # run unit tests
#   make lint           # ruff check + ruff format
#   make type           # mypy strict
#   make check          # all guards (pinning, layering, leak, vocab, LOC)
#   make ci             # everything CI runs (lint + type + test + check)
#   make clean          # remove caches
# ============================================================================

# Use bash on Unix; PowerShell on Windows can ignore SHELL line.
SHELL := /bin/bash

# Default Python — override with `make PYTHON=python3.12 install`.
PYTHON ?= python

# Virtual env location.
VENV_DIR ?= .venv

# Activation hint shown to the user.
ifeq ($(OS),Windows_NT)
	ACTIVATE_HINT := .\$(VENV_DIR)\Scripts\Activate.ps1
else
	ACTIVATE_HINT := source $(VENV_DIR)/bin/activate
endif

.DEFAULT_GOAL := help

.PHONY: help
help:  ## Show this help
	@echo "Nucleus — common dev tasks"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'
	@echo ""
	@echo "Activate venv: $(ACTIVATE_HINT)"

# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------

.PHONY: venv
venv:  ## Create a fresh virtual environment in .venv/
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "Activate with: $(ACTIVATE_HINT)"

.PHONY: install
install:  ## Install package + dev dependencies in editable mode (uses uv if available)
	@if command -v uv >/dev/null 2>&1; then \
		echo "Using uv (ADR-027)..."; \
		uv pip install -e ".[dev]"; \
	else \
		$(PYTHON) -m pip install --upgrade pip; \
		$(PYTHON) -m pip install -e ".[dev]"; \
	fi
	@echo "Done. Try: make test"

.PHONY: install-hooks
install-hooks:  ## Install pre-commit hooks
	$(PYTHON) -m pre_commit install
	@echo "Pre-commit installed. Hooks run on every git commit."

# ----------------------------------------------------------------------------
# Quality gates
# ----------------------------------------------------------------------------

.PHONY: lint
lint:  ## Run ruff check + ruff format --check
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

.PHONY: lint-fix
lint-fix:  ## Auto-fix lint issues (ruff check --fix + ruff format)
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m ruff format .

.PHONY: type
type:  ## Run mypy in strict mode (per pyproject.toml)
	$(PYTHON) -m mypy

.PHONY: test
test:  ## Run pytest (unit + smoke, skip integration/slow)
	$(PYTHON) -m pytest -m "not integration and not slow"

.PHONY: test-integration
test-integration:  ## Run integration tests (requires Postgres + MinIO services)
	$(PYTHON) -m pytest -m integration

.PHONY: test-all
test-all:  ## Run ALL tests including integration + slow
	$(PYTHON) -m pytest

.PHONY: coverage
coverage:  ## Run tests + open HTML coverage report
	$(PYTHON) -m pytest --cov-report=html
	@echo "Open: htmlcov/index.html"

# ----------------------------------------------------------------------------
# Constraint guards (engineering.md + AGENTS.md)
# ----------------------------------------------------------------------------

.PHONY: check-pinning
check-pinning:  ## Constraint #11 — pinned versions match docs/compatibility.md
	$(PYTHON) scripts/check_pinning.py

.PHONY: check-layering
check-layering:  ## engineering.md §3.1 — no upward layer imports
	$(PYTHON) scripts/check_layering.py

.PHONY: check-leak
check-leak:  ## v4.1 §6.4 — no Dagster imports outside coordination/
	$(PYTHON) scripts/dagster_leak_check.py

.PHONY: check-vocab
check-vocab:  ## engineering.md §15 — forbidden vocabulary
	$(PYTHON) scripts/check_vocabulary.py

.PHONY: loc-report
loc-report:  ## Constraint #8 — LOC budget report
	$(PYTHON) scripts/loc_budget.py --report

.PHONY: check
check: check-pinning check-layering check-leak check-vocab loc-report  ## Run all constraint guards

# ----------------------------------------------------------------------------
# CI mirror — what CI runs locally
# ----------------------------------------------------------------------------

.PHONY: ci
ci: check lint type test  ## Run everything CI runs (before pushing)
	@echo ""
	@echo "All CI checks passed locally."

# ----------------------------------------------------------------------------
# Housekeeping
# ----------------------------------------------------------------------------

.PHONY: clean
clean:  ## Remove caches and build artifacts
	rm -rf .mypy_cache .pytest_cache .ruff_cache htmlcov build dist
	rm -rf .nucleus warehouse catalog.db catalog.db-*
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
	@echo "Cleaned."

.PHONY: clean-all
clean-all: clean  ## Also remove the virtual environment
	rm -rf $(VENV_DIR)

# ----------------------------------------------------------------------------
# Documentation (MkDocs Material — ADR-021)
# ----------------------------------------------------------------------------
# Docs: https://squidfunk.github.io/mkdocs-material/
# Install: pip install -e ".[docs]"
# Windows PowerShell equivalent: .\.venv\Scripts\python.exe -m mkdocs serve

.PHONY: docs-install
docs-install:  ## Install docs extras (mkdocs-material + plugins)
	$(PYTHON) -m pip install -e ".[docs]"
	@echo "Docs deps installed. Try: make docs-serve"

.PHONY: docs-serve
docs-serve:  ## Serve docs locally at http://localhost:8000
	$(PYTHON) -m mkdocs serve

.PHONY: docs-build
docs-build:  ## Build docs (strict — zero warnings required)
	$(PYTHON) -m mkdocs build --strict --site-dir _site_test
	@echo "Docs built to _site_test/. Run 'make docs-clean' to remove."

.PHONY: docs-clean
docs-clean:  ## Remove the docs build artifacts
	rm -rf _site_test site
	@echo "Docs build artifacts removed."

# ----------------------------------------------------------------------------
# verify-all — comprehensive gate (mass-audit 2026-05-15)
# Runs all 11 governance scripts + full pytest + LOC budget check.
# Usage: make verify-all
# ----------------------------------------------------------------------------

.PHONY: verify-all
verify-all:  ## Run all 12 governance scripts + pytest + LOC budget
	@echo "=== Nucleus verify-all gate ==="
	python scripts/check_vocabulary.py
	python scripts/check_pinning.py
	python scripts/dagster_leak_check.py
	python scripts/check_error_codes.py
	python scripts/check_api_stability.py
	python scripts/check_layering.py
	python scripts/check_licenses.py
	python scripts/loc_budget.py
	python scripts/check_secrets.py
	python scripts/check_circular_imports.py
	python scripts/check_docstrings.py
	python scripts/check_lazy_imports.py
	python -m pytest tests/ -q --tb=short --no-cov
	@echo ""
	@echo "verify-all PASSED."

# ----------------------------------------------------------------------------
# v0.2 CI / community shortcuts (ADR-022)
# ----------------------------------------------------------------------------

.PHONY: release-check
release-check:  ## semver + changelog + governance (pytest skipped; see scripts/release.py)
	$(PYTHON) scripts/release.py --dry-run --no-pytest

.PHONY: pre-commit-install
pre-commit-install:  ## Install git hooks from `.pre-commit-config.yaml`
	$(PYTHON) -m pre_commit install

.PHONY: docker-build
docker-build:  ## Build `nucleus:local` image from docker/Dockerfile.nucleus
	docker build -f docker/Dockerfile.nucleus -t nucleus:local .

.PHONY: docker-demo
docker-demo:  ## Start MinIO + nucleus demo stack (docker-compose.demo.yml)
	docker compose -f docker-compose.demo.yml up --build

.PHONY: governance-all
governance-all:  ## Run vocabulary + pinning scripts (narrow governance slice)
	$(PYTHON) scripts/check_vocabulary.py
	$(PYTHON) scripts/check_pinning.py
