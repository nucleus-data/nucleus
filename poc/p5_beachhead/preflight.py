"""Beachhead pre-flight check for external testers.

Run this BEFORE starting the 30-minute beachhead scenario in
poc/p5_beachhead/SCENARIO.md. Catches environment issues at the front
door so the timed run isn't wasted.

Per poc/p5_beachhead/DESIGN.md and SETUP.md.

Docs:
- SETUP.md §1-§7 (Windows path)
- SETUP.md §M1-§M8 (macOS path)
- AGENTS.md §11.7, §11.13
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import platform
import shutil
import socket
import subprocess
import sys
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HARNESS_ACTIVE = Path.cwd() / "poc5_results" / ".active.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    with contextlib.suppress(AttributeError, OSError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


@dataclass
class CheckResult:
    name: str
    status: str
    message: str
    details_url: str = ""


def _r(name: str, status: str, msg: str, url: str = "") -> CheckResult:
    return CheckResult(name, status, msg, url)


# ----------------------------------------------------------------------------
# Helpers (never raise; never hang)
# ----------------------------------------------------------------------------


def _is_wsl() -> bool:
    """Linux-under-WSL detection via /proc/version. False on non-Linux."""
    if platform.system() != "Linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """subprocess.run wrapper that never raises. Returns (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        return 127, "", f"command not found: {exc}"
    except subprocess.TimeoutExpired as exc:
        return 124, "", f"timed out after {timeout}s: {exc}"
    return proc.returncode, proc.stdout, proc.stderr


def _docker(args: list[str], timeout: int = 30) -> tuple[int, str, str, str]:
    """Try ``docker``; on Windows fall back to ``wsl -e docker`` per founder pattern."""
    rc, out, err = _run(["docker", *args], timeout=timeout)
    via = "docker"
    if rc != 0 and platform.system() == "Windows":
        rc, out, err = _run(["wsl", "-e", "docker", *args], timeout=timeout)
        via = "wsl -e docker"
    return rc, out, err, via


def _port_free(port: int) -> tuple[bool, str]:
    """Probe ``localhost:port`` via TCP bind. Never raises."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)
    try:
        sock.bind(("localhost", port))
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        sock.close()
    return True, ""


def _total_memory_gib() -> float | None:
    """Best-effort cross-platform total RAM in GiB; None when undetectable."""
    system = platform.system()
    try:
        if system == "Linux":
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 * 1024)
        elif system == "Darwin":
            rc, out, _ = _run(["sysctl", "-n", "hw.memsize"], timeout=5)
            if rc == 0 and out.strip().isdigit():
                return int(out.strip()) / (1024**3)
        elif system == "Windows":
            return _win_total_memory_gib()
    except (OSError, ValueError, AttributeError):
        return None
    return None


def _win_total_memory_gib() -> float | None:
    """Total physical RAM on Windows via kernel32.GetPhysicallyInstalledSystemMemory."""
    import ctypes

    kb = ctypes.c_ulonglong()
    ok = ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kb))
    return kb.value / (1024**2) if ok else None


def _has_module(module: str) -> bool:
    """True if ``module`` is importable without actually importing it."""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


# ----------------------------------------------------------------------------
# Block 1 — Host environment
# ----------------------------------------------------------------------------


def check_os() -> CheckResult:
    sys_name = platform.system()
    if sys_name in ("Windows", "Darwin", "Linux"):
        wsl = " (WSL2)" if _is_wsl() else ""
        return _r("1. OS", PASS, f"{sys_name}{wsl} {platform.release()}", "SETUP.md")
    return _r("1. OS", WARN, f"unrecognized OS {sys_name!r}", "SETUP.md")


def check_python_version() -> CheckResult:
    v = sys.version_info
    actual = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor == 11:
        return _r("2. Python 3.11", PASS, f"Python {actual}", "SETUP.md §M1")
    hint = {
        "Windows": "winget install Python.Python.3.11",
        "Darwin": "brew install python@3.11",
        "Linux": "use your distro's python3.11 package",
    }.get(platform.system(), "install Python 3.11.x from python.org")
    return _r("2. Python 3.11", FAIL, f"got {actual}; fix: {hint}", "SETUP.md §M1")


def check_virtualenv() -> CheckResult:
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return _r("3. Virtualenv", PASS, f"venv: {sys.prefix}", "SETUP.md §M2")
    return _r("3. Virtualenv", WARN, "system Python; activate .venv", "SETUP.md §M2")


def check_disk_space() -> CheckResult:
    try:
        free = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    except OSError as exc:
        return _r("4. Disk space", WARN, f"could not determine: {exc}", "SETUP.md")
    if free < 5:
        return _r("4. Disk space", WARN, f"only {free:.1f} GiB free; recommend ≥5", "SETUP.md")
    return _r("4. Disk space", PASS, f"{free:.1f} GiB free in {REPO_ROOT}", "SETUP.md")


def check_memory() -> CheckResult:
    gib = _total_memory_gib()
    if gib is None:
        return _r("5. Memory", WARN, "could not determine RAM (stdlib-only)", "SETUP.md §M3")
    if gib < 4:
        return _r("5. Memory", WARN, f"only {gib:.1f} GiB RAM; recommend ≥4", "SETUP.md §M3")
    return _r("5. Memory", PASS, f"{gib:.1f} GiB RAM", "SETUP.md §M3")


# ----------------------------------------------------------------------------
# Block 2 — Project setup
# ----------------------------------------------------------------------------


def check_venv_exists() -> CheckResult:
    venv = REPO_ROOT / ".venv"
    if venv.is_dir():
        return _r("6. .venv exists", PASS, str(venv), "SETUP.md §M2")
    return _r("6. .venv exists", FAIL, "no .venv; run `python -m venv .venv`", "SETUP.md §M2")


def check_deps_installed() -> CheckResult:
    required = ("pyiceberg", "dagster", "polars", "duckdb", "pyarrow", "psutil")
    missing = [m for m in required if not _has_module(m)]
    if missing:
        msg = f"missing: {', '.join(missing)}; run `pip install -e .[dev]`"
        return _r("7. Project deps", FAIL, msg, "SETUP.md §M4")
    return _r("7. Project deps", PASS, f"importable: {', '.join(required)}", "SETUP.md §M4")


def check_pyproject() -> CheckResult:
    pyp = REPO_ROOT / "pyproject.toml"
    if not pyp.is_file():
        return _r("8. pyproject.toml", FAIL, f"missing: {pyp}", "SETUP.md")
    try:
        data = tomllib.loads(pyp.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError) as exc:
        return _r("8. pyproject.toml", FAIL, f"malformed: {exc}", "SETUP.md")
    name = data.get("project", {}).get("name", "?")
    return _r("8. pyproject.toml", PASS, f"parsed; project.name={name!r}", "SETUP.md")


def check_git_clean() -> CheckResult:
    rc, out, err = _run(["git", "status", "--porcelain"], timeout=10)
    if rc != 0:
        return _r("9. Git clean", WARN, f"git status failed: {err.strip() or rc}", "SETUP.md")
    dirty = [ln for ln in out.splitlines() if ln.strip()]
    if dirty:
        return _r("9. Git clean", WARN, f"{len(dirty)} uncommitted path(s)", "SETUP.md")
    return _r("9. Git clean", PASS, "clean working tree", "SETUP.md")


# ----------------------------------------------------------------------------
# Block 3 — Docker / WSL
# ----------------------------------------------------------------------------


def check_docker_present() -> CheckResult:
    rc, out, err, via = _docker(["--version"], timeout=15)
    if rc == 0:
        return _r("10. Docker", PASS, f"{via}: {out.strip()}", "SETUP.md §M3")
    return _r("10. Docker", FAIL, f"not invocable ({via}: {err.strip() or rc})", "SETUP.md §M3")


def check_docker_daemon() -> CheckResult:
    rc, _out, err, via = _docker(["ps"], timeout=15)
    if rc == 0:
        return _r("11. Daemon", PASS, f"{via} ps OK", "SETUP.md §M3")
    fix = "Docker Desktop" if platform.system() in ("Windows", "Darwin") else "docker daemon"
    msg = f"down via {via}: {err.strip() or rc}; start {fix}"
    return _r("11. Daemon", FAIL, msg, "SETUP.md §M3 / §M7")


def check_dockerhub_reachable() -> CheckResult:
    rc, _out, err, via = _docker(["pull", "--quiet", "hello-world"], timeout=60)
    if rc == 0:
        return _r("12. Docker Hub", PASS, f"{via}: pulled hello-world", "SETUP.md §7")
    msg = f"{via} pull failed: {err.strip()[:120] or rc}; set NO_PROXY if behind proxy"
    return _r("12. Docker Hub", WARN, msg, "SETUP.md §7")


# ----------------------------------------------------------------------------
# Block 4 — Storage substrate
# ----------------------------------------------------------------------------


def check_seaweedfs_pullable() -> CheckResult:
    rc, _out, err, via = _docker(["pull", "chrislusf/seaweedfs:4.23"], timeout=180)
    if rc == 0:
        return _r("13. SeaweedFS", PASS, f"{via}: 4.23 present", "docker-compose.yml")
    return _r("13. SeaweedFS", FAIL, f"pull failed: {err.strip()[:120] or rc}", "SETUP.md §7")


def check_port_9000() -> CheckResult:
    free, msg = _port_free(9000)
    if free:
        return _r("14. Port 9000", PASS, "localhost:9000 bindable", "SETUP.md §M7")
    return _r("14. Port 9000", FAIL, f"occupied ({msg}); stop conflict", "SETUP.md §M7")


def check_port_8181() -> CheckResult:
    free, msg = _port_free(8181)
    if free:
        return _r("15. Port 8181", PASS, "localhost:8181 bindable", "docs/research/seaweedfs.md")
    return _r("15. Port 8181", FAIL, f"occupied ({msg})", "docs/research/seaweedfs.md")


# ----------------------------------------------------------------------------
# Block 5 — Nucleus PoC sanity
# ----------------------------------------------------------------------------


_POC_TARGETS: tuple[tuple[int, int, str, str], ...] = (
    (16, 1, "poc.p1_error_translation.translator", "poc/p1_error_translation/"),
    (17, 2, "poc.p2_ctx_sql.resolver", "poc/p2_ctx_sql/"),
    (18, 3, "poc.p3_ingest.ingest", "poc/p3_ingest/"),
    (19, 4, "poc.p4_boot_time.measure", "poc/p4_boot_time/"),
)


def _make_poc_check(cid: int, n: int, module: str, doc: str) -> Callable[[], CheckResult]:
    label = f"{cid}. PoC #{n} imports"

    def check() -> CheckResult:
        ok = _has_module(module)
        suffix = "importable" if ok else "not importable"
        return _r(label, PASS if ok else FAIL, f"{module} {suffix}", doc)

    check.__name__ = f"check_poc{n}_imports"
    return check


def check_pytest_collect() -> CheckResult:
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", "--no-cov"]
    cmd += ["poc/p1_error_translation", "poc/p2_ctx_sql"]
    rc, _out, err = _run(cmd, timeout=60)
    if rc == 0:
        return _r("20. pytest collect", PASS, "PoC #1+#2 pytest --collect-only succeeded", "poc/")
    return _r("20. pytest collect", WARN, f"failed (rc={rc}): {err.strip()[:120]}", "poc/")


# ----------------------------------------------------------------------------
# Block 6 — Beachhead specifics
# ----------------------------------------------------------------------------


def check_nucleus_cli() -> CheckResult:
    rc, out, _err = _run([sys.executable, "-m", "nucleus", "--version"], timeout=20)
    if rc == 0:
        return _r("21. nucleus CLI", PASS, f"-m nucleus -> {out.strip()}", "nucleus_cli_spec.md")
    nucleus = shutil.which("nucleus")
    if nucleus:
        rc2, out2, _e = _run([nucleus, "--version"], timeout=20)
        if rc2 == 0:
            return _r("21. nucleus CLI", PASS, f"nucleus -> {out2.strip()}", "nucleus_cli_spec.md")
    return _r("21. nucleus CLI", FAIL, "not invocable; run `pip install -e .[dev]`", "SETUP.md §M5")


def check_harness() -> CheckResult:
    if not _has_module("poc.p5_beachhead.harness"):
        return _r("22. harness", FAIL, "not importable", "poc/p5_beachhead/harness.py")
    if HARNESS_ACTIVE.is_file():
        msg = f"left-over session: {HARNESS_ACTIVE}; delete or finish it"
        return _r("22. harness", WARN, msg, "poc/p5_beachhead/harness.py")
    return _r("22. harness", PASS, "no left-over session", "poc/p5_beachhead/harness.py")


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------


_BLOCK_1 = (check_os, check_python_version, check_virtualenv, check_disk_space, check_memory)
_BLOCK_2 = (check_venv_exists, check_deps_installed, check_pyproject, check_git_clean)
_BLOCK_3 = (check_docker_present, check_docker_daemon, check_dockerhub_reachable)
_BLOCK_4 = (check_seaweedfs_pullable, check_port_9000, check_port_8181)
_BLOCK_5_TAIL = (check_pytest_collect,)
_BLOCK_6 = (check_nucleus_cli, check_harness)
_BLOCK_5_POCS = tuple(_make_poc_check(*spec) for spec in _POC_TARGETS)
ALL_CHECKS: tuple[Callable[[], CheckResult], ...] = (
    _BLOCK_1 + _BLOCK_2 + _BLOCK_3 + _BLOCK_4 + _BLOCK_5_POCS + _BLOCK_5_TAIL + _BLOCK_6
)
DOCKER_CHECK_IDS = {10, 11, 12, 13}  # Block 3 + image pull from Block 4


def run_checks(quick: bool) -> list[CheckResult]:
    out: list[CheckResult] = []
    for idx, fn in enumerate(ALL_CHECKS, start=1):
        if quick and idx in DOCKER_CHECK_IDS:
            out.append(_r(f"{idx}. {fn.__name__}", WARN, "skipped (--quick)"))
            continue
        try:
            out.append(fn())
        except Exception as exc:
            out.append(_r(fn.__name__, FAIL, f"raised {type(exc).__name__}: {exc}"))
    return out


def summarize(results: list[CheckResult]) -> dict[str, int]:
    return {s: sum(1 for r in results if r.status == s) for s in (PASS, WARN, FAIL)}


def render_text(results: list[CheckResult], summary: dict[str, int]) -> str:
    bar = "=" * 72
    lines = [
        bar,
        " Nucleus -- Beachhead Pre-flight (PoC #5)",
        f" Host: {platform.system()} {platform.release()} · Python {sys.version.split()[0]}",
        bar,
        "",
    ]
    for r in results:
        marker = {PASS: "[PASS]", WARN: "[WARN]", FAIL: "[FAIL]"}.get(r.status, "[????]")
        lines.append(f" {marker}  {r.name}\n          {r.message}")
        if r.details_url:
            lines.append(f"          see: {r.details_url}")
        lines.append("")
    lines += [
        bar,
        f" Summary: {summary[PASS]} PASS · {summary[WARN]} WARN · {summary[FAIL]} FAIL",
        " Exit 0 = safe · 1 = at least one FAIL · 2 = script crash",
        bar,
    ]
    return "\n".join(lines)


def render_json(results: list[CheckResult], summary: dict[str, int], code: int) -> str:
    payload = {
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
            "is_wsl": _is_wsl(),
        },
        "summary": summary,
        "exit_code": code,
        "checks": [asdict(r) for r in results],
    }
    return json.dumps(payload, indent=2, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="preflight",
        description="Verify a tester's machine is ready for the PoC #5 30-min beachhead scenario.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    parser.add_argument("--quick", action="store_true", help="skip Docker checks (offline mode)")
    args = parser.parse_args(argv)

    try:
        results = run_checks(quick=args.quick)
    except Exception as exc:
        sys.stderr.write(f"preflight crashed: {type(exc).__name__}: {exc}\n")
        return 2

    summary = summarize(results)
    code = 1 if summary.get(FAIL, 0) > 0 else 0
    out = render_json(results, summary, code) if args.json else render_text(results, summary)
    sys.stdout.write(out + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
