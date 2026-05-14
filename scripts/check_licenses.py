"""License-tier check — ADR-007 §Verification plan.

Walks pinned runtime dependencies in ``pyproject.toml``, reads each
distribution's License metadata, classifies per ADR-007's GREEN /
YELLOW / RED tiers, and fails CI when a pinned package crosses into
RED or when a tier shift is detected against the previous lock.

Tier policy (ADR-007 §Decision)
-------------------------------
GREEN   Apache-2.0, MIT, BSD-2/3-Clause, ISC, CC0 / Public Domain
YELLOW  AGPLv3, GPLv3 (non-Affero), GPLv2 + classpath, LGPLv3, MPL-2.0
RED     Elastic 2.0, SSPL, BUSL, proprietary / source-available,
        "anti-capitalist" / Hippocratic / similar restricted licenses

GREEN may be adopted anywhere (OSS + Cloud + Enterprise).
YELLOW may run in OSS distribution; never bundled / managed-service in
Cloud per ADR-007. RED is BLOCKED for Cloud, opt-in only in OSS.

Locking + drift detection
-------------------------
``--record`` writes a snapshot to ``docs/license_lock.json`` (per-package
license + tier). Subsequent runs flag any package whose tier has shifted
compared to the prior snapshot — automatic-ADR trigger per ADR-007.

Usage
-----
    python scripts/check_licenses.py
    python scripts/check_licenses.py --format json
    python scripts/check_licenses.py --record

Exit codes
----------
    0  clean (no RED, no tier shifts)
    1  RED license detected on a pinned dep
    2  tier shift since previous lock

NEEDS VERIFICATION (AGENTS.md §11.12)
-------------------------------------
The exact ``importlib.metadata`` field that carries the SPDX licence
varies (``License``, ``License-Expression``, sometimes ``Classifier``
``License :: OSI Approved :: …``). We probe all three; review against
PyPI metadata before promoting this check to a release blocker
(v0.5 per ADR-007 §Verification plan).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Final

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
LICENSE_LOCK = REPO_ROOT / "docs" / "license_lock.json"

# Tier definitions per ADR-007 §Decision. Match the *normalised* license
# string (lower-cased, punctuation stripped) against substrings.
GREEN_PATTERNS: Final[tuple[str, ...]] = (
    "apache-2.0", "apache 2.0", "apache license 2", "apache software",
    "mit", "bsd-2-clause", "bsd-3-clause", "bsd 2", "bsd 3", "bsd license",
    "isc", "psf", "python software foundation", "cc0", "public domain",
    "unlicense",
)
YELLOW_PATTERNS: Final[tuple[str, ...]] = (
    "agpl", "affero", "gpl-2", "gpl-3", "gnu general public",
    "lgpl", "lesser general public", "mpl", "mozilla public",
)
RED_PATTERNS: Final[tuple[str, ...]] = (
    "elastic license", "elv2", "sspl", "server side public",
    "busl", "business source", "commons clause",
    "hippocratic", "anti-capitalist", "anti capitalist", "non-commercial",
    "proprietary",
)

# Standing pre-decisions baked in from ADR-007 §Standing pre-decisions.
# Used as a fallback when ``importlib.metadata`` cannot resolve a package
# (pre-Heartbeat installs without site-packages, CI scaffold mode, etc.).
BAKED_IN_LICENSES: Final[dict[str, str]] = {
    "duckdb": "MIT",
    "polars": "MIT",
    "pyarrow": "Apache-2.0",
    "pyiceberg": "Apache-2.0",
    "dagster": "Apache-2.0",
    "sqlalchemy": "MIT",
    # ADR-007 amendment 2026-05-14 — verified on PyPI / upstream LICENSE
    "openlineage-python": "Apache-2.0",
    "s3fs": "BSD-3-Clause",
    "orjson": "MPL-2.0 AND (Apache-2.0 OR MIT)",
    "psycopg": "LGPL-3.0-only",  # PyPI + classifier; matches ADR-007 Tier 2 boundary note
    "pymysql": "MIT",
    "jinja2": "BSD-3-Clause",
    "sqlglot": "MIT",
    "click": "BSD-3-Clause",
    "structlog": "Apache-2.0",
    "msgspec": "BSD-3-Clause",
    "typer": "MIT",
    "rich": "MIT",
    "opentelemetry-api": "Apache-2.0",
    "opentelemetry-sdk": "Apache-2.0",
}


@dataclass
class LicenseEntry:
    package: str
    version: str
    license: str
    tier: str
    source: str  # "metadata" | "baked-in" | "unknown"


@dataclass
class TierShift:
    package: str
    previous_tier: str
    current_tier: str
    previous_license: str
    current_license: str


def _normalise(s: str) -> str:
    return re.sub(r"[\s\-_]+", " ", s.lower()).strip()


def _classify(license_str: str) -> str:
    """Map a raw SPDX-ish licence string onto ADR-007 GREEN/YELLOW/RED/UNKNOWN."""
    if not license_str or license_str.strip().lower() in ("", "unknown", "none"):
        return "UNKNOWN"
    norm = _normalise(license_str)
    # RED takes precedence: dual-licensed deps must be classified by their
    # most restrictive option (ADR-007 §Risks row "Multi-license dependency").
    for pat in RED_PATTERNS:
        if pat in norm:
            return "RED"
    for pat in YELLOW_PATTERNS:
        if pat in norm:
            return "YELLOW"
    for pat in GREEN_PATTERNS:
        if pat in norm:
            return "GREEN"
    return "UNKNOWN"


def _pin_re() -> re.Pattern[str]:
    return re.compile(r"^(?P<pkg>[a-zA-Z][a-zA-Z0-9_.\-]*)(?:\[[^\]]+\])?==(?P<ver>[^;\s]+)")


def _extract_pins(pyproject: Path) -> dict[str, str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    pins: dict[str, str] = {}
    rx = _pin_re()
    for raw in data.get("project", {}).get("dependencies", []):
        m = rx.match(raw.strip())
        if m:
            pins[m["pkg"].lower()] = m["ver"]
    return pins


def _read_license(pkg: str) -> tuple[str, str]:
    """Return ``(license_string, source)`` where source ∈ {metadata, baked-in, unknown}."""
    # NEEDS VERIFICATION (ADR-007 §Risks "License-tier wrong"): probe all three
    # metadata fields. Some distributions populate only one.
    try:
        meta = importlib_metadata.metadata(pkg)
    except importlib_metadata.PackageNotFoundError:
        baked = BAKED_IN_LICENSES.get(pkg.lower())
        return (baked, "baked-in") if baked else ("UNKNOWN", "unknown")
    for field in ("License-Expression", "License"):
        val = meta.get(field)
        if val and val.strip().lower() not in ("", "unknown"):
            return val.strip(), "metadata"
    # Fall back to classifiers (e.g. "License :: OSI Approved :: Apache Software License").
    for cls in meta.get_all("Classifier") or []:
        if cls.startswith("License ::"):
            label = cls.split("::")[-1].strip()
            if label and label.lower() != "other":
                return label, "metadata"
    baked = BAKED_IN_LICENSES.get(pkg.lower())
    return (baked, "baked-in") if baked else ("UNKNOWN", "unknown")


def collect(pyproject: Path = PYPROJECT) -> list[LicenseEntry]:
    entries: list[LicenseEntry] = []
    for pkg, ver in _extract_pins(pyproject).items():
        lic, source = _read_license(pkg)
        if _classify(lic) == "UNKNOWN":
            fallback = BAKED_IN_LICENSES.get(pkg.lower())
            if fallback:
                lic, source = fallback, "baked-in"
        entries.append(LicenseEntry(pkg, ver, lic, _classify(lic), source))
    entries.sort(key=lambda e: (e.tier, e.package))
    return entries


def detect_shifts(entries: list[LicenseEntry], lock: Path = LICENSE_LOCK) -> list[TierShift]:
    if not lock.exists():
        return []
    try:
        prior = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    by_pkg = {e["package"]: e for e in prior.get("entries", []) if isinstance(e, dict)}
    shifts: list[TierShift] = []
    for cur in entries:
        prev = by_pkg.get(cur.package)
        if prev and prev.get("tier") != cur.tier:
            shifts.append(TierShift(
                package=cur.package,
                previous_tier=str(prev.get("tier", "?")),
                current_tier=cur.tier,
                previous_license=str(prev.get("license", "?")),
                current_license=cur.license,
            ))
    return shifts


def _record(entries: list[LicenseEntry], lock: Path = LICENSE_LOCK) -> None:
    lock.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": 1, "entries": [asdict(e) for e in entries]}
    lock.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render(entries: list[LicenseEntry], shifts: list[TierShift], reds: list[LicenseEntry]) -> str:
    lines = ["License-tier report (ADR-007)", "=" * 62,
             f" packages scanned : {len(entries)}",
             f" RED detected     : {len(reds)}",
             f" tier shifts      : {len(shifts)}", ""]
    lines.extend(
        f"  [{e.tier:<7}] {e.package}=={e.version}  {e.license}  ({e.source})"
        for e in entries
    )
    if reds:
        lines += ["", "BLOCKED (RED tier — ADR-007 §Tier 3):"]
        lines += [f"  - {e.package}: {e.license}" for e in reds]
    if shifts:
        lines += ["", "Tier shifts vs docs/license_lock.json:"]
        for s in shifts:
            lines.append(f"  - {s.package}: {s.previous_tier} -> {s.current_tier} "
                         f"({s.previous_license} -> {s.current_license})")
        lines.append("  Open ADR-NNN-tier-shift-<pkg> per ADR-007 §Upgrade detection trigger.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="License-tier check (ADR-007 §Verification plan).")
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument("--record", action="store_true",
                   help="Write docs/license_lock.json from current state and exit 0.")
    args = p.parse_args(argv)

    if not PYPROJECT.exists():
        print(f"check_licenses: missing {PYPROJECT}", file=sys.stderr)
        return 2

    entries = collect()
    reds = [e for e in entries if e.tier == "RED"]
    shifts = [] if args.record else detect_shifts(entries)

    if args.record:
        _record(entries)
        if args.format == "json":
            print(json.dumps({"ok": True, "recorded": str(LICENSE_LOCK),
                              "entries": [asdict(e) for e in entries]}, indent=2))
        else:
            print(f"Recorded {len(entries)} entries to {LICENSE_LOCK.relative_to(REPO_ROOT)}.")
        return 0

    if args.format == "json":
        print(json.dumps({
            "ok": not reds and not shifts,
            "entries": [asdict(e) for e in entries],
            "red": [asdict(e) for e in reds],
            "shifts": [asdict(s) for s in shifts],
        }, indent=2))
    else:
        print(_render(entries, shifts, reds))

    if reds:
        return 1
    if shifts:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
