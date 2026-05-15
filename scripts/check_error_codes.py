"""Error-code numbering check — ADR-006 §Verification plan.

AST-walks ``src/nucleus/errors.py`` to enumerate every ``NucleusError``
subclass. Asserts each subclass declares::

    error_code: ClassVar[str] = "NEx###"

matching ``^NE[1-5]\\d{3}$`` (per ADR-006 §Decision). Detects:

- subclasses missing the ``error_code`` ClassVar
- duplicate codes across the registry
- invalid format
- reserved-range usage (``NEx900``-``NEx999`` is internal-only per ADR-006
  §Reserved ranges)

``--bootstrap`` mode prints suggested codes for missing subclasses
without modifying any source. Founder applies during PoC #1 promotion
(AGENTS.md §11.1).

Usage
-----
    python scripts/check_error_codes.py
    python scripts/check_error_codes.py --bootstrap
    python scripts/check_error_codes.py --json

Exit codes
----------
    0  every subclass tagged + unique + valid (or --bootstrap completed)
    1  one or more subclasses missing error_code OR duplicate
    2  invalid format detected (incl. reserved-range surfaced as default)

NEEDS VERIFICATION (AGENTS.md §11.12)
-------------------------------------
``src/nucleus/errors.py`` currently has NO ``error_code`` ClassVar fields
(deferred per v4.1 §6.4 v4.1.2 note + errors.py:23-28). This check fails
on the current tree until PoC #1 promotion adds the codes. The CI step is
wired with ``continue-on-error: true`` for that reason. Promotion to
release blocker happens alongside ADR-006 ACCEPTED (per its Trigger §).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

REPO_ROOT = Path(__file__).resolve().parent.parent
ERRORS_FILE = REPO_ROOT / "src" / "nucleus" / "errors.py"

CODE_RE: Final[re.Pattern[str]] = re.compile(r"^NE[1-5]\d{3}$")
RESERVED_RE: Final[re.Pattern[str]] = re.compile(r"^NE[1-5]9\d{2}$")

# Initial code assignments from ADR-006 §Initial code assignment.
# Used by --bootstrap when a subclass is missing its error_code ClassVar.
# Subclasses not listed here surface as "NEEDS ASSIGNMENT" — founder picks
# the next free integer in the correct layer band per ADR-006 §Decision.
BOOTSTRAP_CODES: Final[dict[str, str]] = {
    "NucleusSourceConnectionError": "NE1001",
    "NucleusCommitConflictError": "NE1002",
    "NucleusCommitUnknownError": "NE1003",
    "NucleusSchemaEvolutionError": "NE1004",
    "NucleusIOError": "NE1005",
    "NucleusPermissionError": "NE1006",
    "NucleusSchemaError": "NE2001",
    "NucleusSQLSyntaxError": "NE2002",
    "NucleusResourceError": "NE2003",
    "NucleusInternalError": "NE3001",
    "NucleusAssetNotFound": "NE3002",
    "NucleusAssetNotMaterialized": "NE3003",
}


@dataclass
class Finding:
    classname: str
    line: int
    code: str | None
    kind: str  # "missing" | "invalid" | "duplicate" | "reserved" | "ok"
    detail: str


def _is_classvar_str(node: ast.AnnAssign) -> bool:
    """Match ``error_code: ClassVar[str] = "..."`` (or bare ``error_code: str``)."""
    if not isinstance(node.target, ast.Name) or node.target.id != "error_code":
        return False
    ann = node.annotation
    if isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name):
        return ann.value.id == "ClassVar"
    return isinstance(ann, ast.Name) and ann.id == "str"


def _string_value(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _nucleus_subclasses(tree: ast.Module) -> list[ast.ClassDef]:
    """Return classes whose MRO transitively includes ``NucleusError``."""
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    descended: set[str] = {"NucleusError"}
    # Fixed-point: repeatedly add classes whose direct base is already descended.
    changed = True
    while changed:
        changed = False
        for name, node in classes.items():
            if name in descended:
                continue
            base_names = [b.id for b in node.bases if isinstance(b, ast.Name)]
            if any(b in descended for b in base_names):
                descended.add(name)
                changed = True
    return [classes[n] for n in sorted(descended) if n != "NucleusError"]


def scan(errors_file: Path = ERRORS_FILE) -> list[Finding]:
    if not errors_file.exists():
        return []
    tree = ast.parse(errors_file.read_text(encoding="utf-8"), filename=str(errors_file))
    findings: list[Finding] = []
    seen_codes: dict[str, str] = {}  # code -> first classname

    for cls in _nucleus_subclasses(tree):
        code: str | None = None
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign) and _is_classvar_str(stmt):
                code = _string_value(stmt.value)
                break
        if code is None:
            findings.append(
                Finding(
                    cls.name,
                    cls.lineno,
                    None,
                    "missing",
                    "no `error_code: ClassVar[str]` in class body",
                )
            )
            continue
        if not CODE_RE.match(code):
            findings.append(
                Finding(
                    cls.name,
                    cls.lineno,
                    code,
                    "invalid",
                    f"code {code!r} does not match ^NE[1-5]\\d{{3}}$",
                )
            )
            continue
        if RESERVED_RE.match(code):
            findings.append(
                Finding(
                    cls.name,
                    cls.lineno,
                    code,
                    "reserved",
                    f"code {code} is in reserved internal range NEx900-NEx999",
                )
            )
            continue
        prev = seen_codes.get(code)
        if prev and prev != cls.name:
            findings.append(
                Finding(
                    cls.name, cls.lineno, code, "duplicate", f"code {code} already used by {prev}"
                )
            )
            continue
        seen_codes[code] = cls.name
        findings.append(Finding(cls.name, cls.lineno, code, "ok", "valid"))
    return findings


def bootstrap_suggestions(findings: list[Finding]) -> list[tuple[str, str, str]]:
    """For each missing/invalid finding, return (classname, suggested_code, note)."""
    out: list[tuple[str, str, str]] = []
    for f in findings:
        if f.kind not in ("missing", "invalid"):
            continue
        suggested = BOOTSTRAP_CODES.get(f.classname)
        note = (
            "per ADR-006 §Initial code assignment"
            if suggested
            else (
                "NEEDS ASSIGNMENT — pick next free code in correct layer band "
                "(NE1=physics, NE2=engines, NE3=coordination, NE4=intelligence, "
                "NE5=experience) per ADR-006 §Decision"
            )
        )
        out.append((f.classname, suggested or "NE?xxx", note))
    return out


def _render(findings: list[Finding], suggestions: list[tuple[str, str, str]] | None) -> str:
    bad = [f for f in findings if f.kind != "ok"]
    lines = [
        "Error-code check (ADR-006)",
        "=" * 62,
        f" subclasses found : {len(findings)}",
        f" missing / invalid: {len(bad)}",
        "",
    ]
    for f in findings:
        tag = "OK" if f.kind == "ok" else f.kind.upper()
        codeval = f.code if f.code else "—"
        lines.append(f"  [{tag:<9}] {f.classname:<32}  code={codeval:<8}  {f.detail}")
    if suggestions:
        lines += ["", "Bootstrap suggestions (apply during PoC #1 promotion):"]
        for clsname, code, note in suggestions:
            lines.append(f"  class {clsname}(NucleusError):")
            lines.append(f'      error_code: ClassVar[str] = "{code}"  # {note}')
    if bad and not suggestions:
        lines += [
            "",
            "Re-run with --bootstrap to print code suggestions per",
            "ADR-006 §Initial code assignment. Apply to src/nucleus/errors.py",
            "during PoC #1 promotion (AGENTS.md §11.1).",
        ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Error-code numbering check (ADR-006).")
    p.add_argument(
        "--bootstrap",
        action="store_true",
        help="Print suggested codes for missing/invalid subclasses, then exit 0.",
    )
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    args = p.parse_args(argv)

    if not ERRORS_FILE.exists():
        msg = f"check_error_codes: {ERRORS_FILE} does not exist — passing vacuously."
        if args.json:
            print(json.dumps({"ok": True, "verdict": "SKELETON", "reason": msg}, indent=2))
        else:
            print(msg)
        return 0

    findings = scan()
    suggestions = bootstrap_suggestions(findings) if args.bootstrap else None
    missing = [f for f in findings if f.kind in ("missing", "duplicate")]
    invalid = [f for f in findings if f.kind in ("invalid", "reserved")]

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not missing and not invalid,
                    "findings": [asdict(f) for f in findings],
                    "missing_or_duplicate": [asdict(f) for f in missing],
                    "invalid_or_reserved": [asdict(f) for f in invalid],
                    "bootstrap": [
                        {"classname": c, "code": k, "note": n} for c, k, n in (suggestions or [])
                    ],
                },
                indent=2,
            )
        )
    else:
        print(_render(findings, suggestions))

    if args.bootstrap:
        return 0
    if invalid:
        return 2
    if missing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
