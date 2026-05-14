"""Project context extractor — private to ``nucleus.intelligence``.

Collects project metadata for the Copilot system prompt.

Privacy rules (ADR-011 §3 + ADR-015 §4 — FIVE mandatory redactions):
  1. NO raw SQL strings → replaced with ``<SQL_REDACTED>``
  2. NO row counts as attributes
  3. NO OS username or hostname → replaced with ``<USER>`` / ``<HOST>``
  4. NO absolute paths → relativized to project_root
  5. NO stack traces with local variable values → message lines only

Hard cap: total context ≤ 4 KB; truncate fields if exceeded.

Architecture ref: ``nucleus_architecture_v4.1.md`` §7.2 + ADR-015 §4
Docs: https://py.iceberg.apache.org/api/catalog/  (pyiceberg==0.11.1)
"""

from __future__ import annotations

import contextlib
import getpass
import json
import logging
import re
import socket
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

_logger = logging.getLogger(__name__)

# Privacy rule #1: replace any SQL-looking fragment.
_SQL_RE = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH)\b", re.IGNORECASE)
# Privacy rule #3: username + hostname substitutes.
_USERNAME_PLACEHOLDER = "<USER>"
_HOSTNAME_PLACEHOLDER = "<HOST>"
# Hard cap: 4 KB total context.
_CONTEXT_SIZE_CAP_BYTES = 4 * 1024


def _redact(text: str, project_root: Path) -> str:
    """Apply all five privacy redaction rules to a string."""
    if not text:
        return text
    # Rule 4: relativize absolute paths.
    try:
        root_str = str(project_root.resolve())
        text = text.replace(root_str, "<PROJECT>")
    except (ValueError, OSError):
        pass
    # Rule 1: redact SQL.
    if _SQL_RE.search(text):
        return "<SQL_REDACTED>"
    # Rule 3: redact username + hostname.
    with contextlib.suppress(Exception):
        text = text.replace(getpass.getuser(), _USERNAME_PLACEHOLDER)
    with contextlib.suppress(Exception):
        text = text.replace(socket.gethostname(), _HOSTNAME_PLACEHOLDER)
    return text


def _safe_yaml_str(config: dict[str, Any], project_root: Path) -> str:
    """Serialize project config to a redacted YAML string ≤ 600 bytes."""
    # Remove any sensitive keys before serializing.
    safe: dict[str, Any] = {
        k: v for k, v in config.items()
        if k not in {"copilot", "secrets", "env"}
    }
    try:
        raw = yaml.dump(safe, default_flow_style=False, allow_unicode=True)
    except Exception:
        raw = str(safe)
    raw = _redact(raw, project_root)
    return raw[:600]


def _read_catalog_assets(project_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Scan the Iceberg catalog for asset keys, columns, and freshness.

    Returns an empty list on any error (catalog not yet created, etc.).
    Docs: https://py.iceberg.apache.org/api/catalog/  (pyiceberg==0.11.1)
    """
    try:
        from pyiceberg.catalog import load_catalog
    except ImportError:
        return []
    try:
        storage = config.get("storage") or {}
        raw_warehouse = storage.get("warehouse", "./data/warehouse")
        warehouse_dir = (
            Path(raw_warehouse)
            if Path(raw_warehouse).is_absolute()
            else (project_root / raw_warehouse).resolve()
        )
        catalog_db = warehouse_dir / "catalog.db"
        if not catalog_db.exists():
            return []
        catalog = load_catalog(
            "default",
            type="sql",
            uri=f"sqlite:///{catalog_db.resolve().as_posix()}",
            warehouse=f"file://{warehouse_dir.resolve().as_posix()}",
        )
        assets: list[dict[str, Any]] = []
        for ns_tuple in catalog.list_namespaces():
            ns = ns_tuple[0] if ns_tuple else ""
            if not ns:
                continue
            for ident in catalog.list_tables(ns):
                tbl = ident[-1]
                try:
                    ice_table = catalog.load_table(ident)
                    snap = ice_table.current_snapshot()
                    freshness = snap.timestamp_ms / 1000 if snap else None
                    import datetime
                    freshness_iso = (
                        datetime.datetime.fromtimestamp(freshness, tz=datetime.UTC)
                        .isoformat()
                        if freshness
                        else "never"
                    )
                    col_names = [f.name for f in ice_table.schema().fields][:10]
                    assets.append({
                        "key": f"{ns}.{tbl}",
                        "column_names": col_names,
                        "freshness_iso": freshness_iso,
                    })
                except Exception:
                    assets.append({"key": f"{ns}.{tbl}", "column_names": [], "freshness_iso": "unknown"})
        return assets[:50]
    except Exception as exc:
        _logger.debug("gather_context: catalog scan skipped: %s", exc)
        return []


def _read_recent_errors(project_root: Path, limit: int = 3) -> list[dict[str, str]]:
    """Read the last ``limit`` FAIL events from ``.nucleus/lineage/*.ndjson``.

    Privacy rule #5: extracts only the error message line, never locals.
    """
    lineage_dir = project_root / ".nucleus" / "lineage"
    if not lineage_dir.exists():
        return []
    errors: list[dict[str, str]] = []
    ndjson_files = sorted(lineage_dir.glob("*.ndjson"), key=lambda p: p.stat().st_mtime, reverse=True)
    ndjson_files += sorted(lineage_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for fpath in ndjson_files:
        try:
            lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for raw_line in reversed(lines):
            if not raw_line.strip():
                continue
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if event.get("eventType") != "FAIL":
                continue
            # Extract message from error facet — rule #5: message only.
            error_facet = (
                (event.get("run") or {})
                .get("facets", {})
                .get("errorMessage", {})
            )
            msg = error_facet.get("message") or str(event.get("run", {}).get("facets", ""))
            ts = event.get("eventTime", "")[:19]
            msg = _redact(msg[:200], project_root)
            errors.append({"timestamp": ts, "message": msg})
            if len(errors) >= limit:
                return errors
    return errors


def gather_context(project_root: Path) -> dict[str, Any]:
    """Build the context dict injected into the Copilot system prompt.

    Returns a JSON-serializable dict with keys:
        project_yaml  (str, redacted YAML fragment ≤ 600 B)
        assets        (list of {key, column_names, freshness_iso})
        asset_count   (int)
        recent_errors (list of {timestamp, message})

    Privacy (ADR-011 §3 + ADR-015 §4): all five redaction rules applied.
    Hard cap: 4 KB total; fields truncated after cap is reached.
    """
    config: dict[str, Any] = {}
    config_path = project_root / "nucleus_project.yaml"
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            config = {}

    project_yaml = _safe_yaml_str(config, project_root)
    assets = _read_catalog_assets(project_root, config)
    recent_errors = _read_recent_errors(project_root)

    ctx: dict[str, Any] = {
        "project_yaml": project_yaml,
        "assets": assets,
        "asset_count": len(assets),
        "recent_errors": recent_errors,
    }

    # Hard cap: 4 KB total serialized size.
    serialized = json.dumps(ctx, default=str)
    if len(serialized.encode()) > _CONTEXT_SIZE_CAP_BYTES:
        _logger.warning(
            "gather_context: context exceeded 4 KB (%d B); truncating assets.",
            len(serialized.encode()),
        )
        while assets and len(json.dumps(ctx, default=str).encode()) > _CONTEXT_SIZE_CAP_BYTES:
            assets.pop()
        ctx["assets"] = assets
        ctx["asset_count"] = len(assets)

    return ctx
