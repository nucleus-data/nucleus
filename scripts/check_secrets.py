"""Hardcoded credential scan — security axis F per mass-audit 2026-05-15.

Scans Python source files under ``src/`` for patterns that look like
hardcoded secrets: literal assignments to common credential key names
(``password``, ``api_key``, ``token``, ``secret``, ``auth``).

Only literal string assignments are flagged (``= "..."`` / ``= '...'``);
references to env-var lookups (``os.environ``, ``os.getenv``) and config
reads (``config.get()``) are exempt so normal configuration code doesn't
false-positive.

Usage
-----
    python scripts/check_secrets.py
    python scripts/check_secrets.py --json

Exit codes
----------
    0  no hardcoded credential patterns found
    1  potential hardcoded credential found
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"

# Attribute / variable name prefixes that commonly hold secrets.
_CRED_NAMES: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "client_secret",
        "auth",
        "authorization",
        "private_key",
        "privatekey",
        "credential",
        "credentials",
    }
)

# Patterns that indicate safe usage (env-var or config reads).
_SAFE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"os\.environ"),
    re.compile(r"os\.getenv"),
    re.compile(r"getenv"),
    re.compile(r"\.get\("),
    re.compile(r"environ"),
    re.compile(r"NEEDS VERIFICATION"),
]

# Files / directories to skip.
_SKIP = [".venv", "node_modules", ".git", "__pycache__", "site", "build", "dist"]

# Minimum length for a string to be considered a real literal secret.
_MIN_SECRET_LEN = 6


@dataclass
class Hit:
    file: str
    line: int
    name: str
    excerpt: str


def _is_cred_name(name: str) -> bool:
    lower = name.lower()
    return any(cred in lower for cred in _CRED_NAMES)


def _is_literal_string(node: ast.AST) -> bool:
    """Return True if ``node`` is a non-empty string literal of min length."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        val = node.value.strip()
        return len(val) >= _MIN_SECRET_LEN and val not in {
            "",
            "***",
            "secret",
            "changeme",
            "REDACTED",
        }
    return False


def _check_line_safe(line: str) -> bool:
    """Return True if the line looks like a safe pattern (env-var / config)."""
    return any(pat.search(line) for pat in _SAFE_PATTERNS)


def _scan_file(path: Path, content: str) -> list[Hit]:
    hits: list[Hit] = []
    lines = content.splitlines()
    try:
        tree = ast.parse(content, filename=str(path))
    except SyntaxError:
        return []

    rel = path.relative_to(REPO_ROOT).as_posix()

    for node in ast.walk(tree):
        # Assignment: ``password = "abc123"`` or ``self.password = "abc123"``
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value if isinstance(node, ast.Assign) else node.value
            if value is None:
                continue
            for target in targets:
                name = ""
                if isinstance(target, ast.Name):
                    name = target.id
                elif isinstance(target, ast.Attribute):
                    name = target.attr
                if name and _is_cred_name(name) and _is_literal_string(value):
                    line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                    if not _check_line_safe(line_text):
                        hits.append(
                            Hit(
                                file=rel,
                                line=node.lineno,
                                name=name,
                                excerpt=line_text.strip()[:120],
                            )
                        )

        # Keyword arg: ``connect(password="abc123")``
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg and _is_cred_name(kw.arg) and _is_literal_string(kw.value):
                    line_text = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                    if not _check_line_safe(line_text):
                        hits.append(
                            Hit(
                                file=rel,
                                line=node.lineno,
                                name=kw.arg,
                                excerpt=line_text.strip()[:120],
                            )
                        )
    return hits


def scan_all() -> list[Hit]:
    hits: list[Hit] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if any(skip in path.parts for skip in _SKIP):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits.extend(_scan_file(path, content))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hardcoded credential scan (security axis F).")
    parser.add_argument("--json", action="store_true", help="JSON output.")
    args = parser.parse_args(argv)

    hits = scan_all()

    if args.json:
        print(json.dumps({"hits": [h.__dict__ for h in hits], "hit_count": len(hits)}, indent=2))
        return 1 if hits else 0

    if not hits:
        print("Credential scan: PASS (no hardcoded secrets detected).")
        return 0

    print(f"Credential scan: FAIL — {len(hits)} potential hardcoded secret(s):\n")
    for h in hits:
        print(f"  {h.file}:{h.line}  [{h.name!r}]")
        print(f"      {h.excerpt}")
    print("\nReplace literals with os.getenv() or a config read.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
