"""Docker Compose helpers for ``nucleus up`` / ``nucleus down``.

Per docs/specs/nucleus_architecture_v4.1.md §8 L4 (CLI wraps local runtime bring-up).
v0.1 ships ``docker-compose.yaml`` from ``nucleus init`` with a ``minio``
service only — REST catalog backends are out of scope (filesystem catalog).

Docs (AGENTS.md §11.12):
    - subprocess.run: https://docs.python.org/3/library/subprocess.html#subprocess.run
    - shutil.which: https://docs.python.org/3/library/shutil.html#shutil.which
    - Compose CLI: https://docs.docker.com/compose/reference/
    - PyYAML safe_load: https://pyyaml.org/wiki/PyYAMLDocumentation
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from nucleus.errors import (
    NucleusConfigError,
    NucleusEnvironmentError,
    NucleusNetworkError,
)

COMPOSE_FILENAME = "docker-compose.yaml"


@dataclass(frozen=True)
class ComposeRunner:
    """Resolved compose invocation (v2 plugin vs standalone v1 binary)."""

    argv_prefix: tuple[str, ...]
    #: True when invoking ``docker compose ...``.
    is_v2: bool


def project_compose_file(project_root: Path) -> Path:
    """Return the canonical compose path next to ``nucleus_project.yaml``."""
    return project_root / COMPOSE_FILENAME


def _load_compose_doc(compose_path: Path) -> dict[str, Any]:
    """Load compose YAML; filesystem errors propagate as ``OSError``."""
    raw = compose_path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(raw)
    return loaded if isinstance(loaded, dict) else {}


def compose_service_names(compose_path: Path) -> frozenset[str]:
    """Return service names declared under ``services:``."""
    try:
        data = _load_compose_doc(compose_path)
    except OSError as exc:
        raise NucleusEnvironmentError(
            user_message=f"Cannot read compose file at {compose_path}: {exc}",
            fix_hint="Check file permissions and disk health.",
            cause=exc,
        ) from exc
    except yaml.YAMLError as exc:
        raise NucleusConfigError(
            user_message=f"Compose file at {compose_path} is not valid YAML.",
            fix_hint="Repair the file or run `nucleus init <name>` in a fresh directory.",
            cause=exc,
        ) from exc

    services = data.get("services", {})
    if not isinstance(services, dict):
        return frozenset()
    return frozenset(k for k in services if isinstance(k, str))


def should_poll_minio_ready(compose_path: Path, service_names: frozenset[str]) -> bool:
    """Poll MinIO only when the compose file declares a matching service."""
    if not service_names:
        return False
    try:
        data = _load_compose_doc(compose_path)
    except (OSError, yaml.YAMLError):
        return any("minio" in n.lower() for n in service_names)

    services = data.get("services")
    if not isinstance(services, dict):
        return any("minio" in n.lower() for n in service_names)

    for name, spec in services.items():
        if isinstance(name, str) and name.lower() == "minio":
            return True
        if isinstance(spec, dict):
            img = spec.get("image")
            if isinstance(img, str) and "minio/minio" in img.lower():
                return True

    return any("minio" in str(n).lower() for n in service_names)


def minio_health_base_url(
    compose_path: Path,
    *,
    default_port: int = 9000,
) -> str:
    """Infer ``http://127.0.0.1:<host-port>`` for the MinIO S3 readiness URL."""
    try:
        data = _load_compose_doc(compose_path)
        services = data.get("services", {})
        if isinstance(services, dict):
            for svc_name, spec in services.items():
                if not isinstance(spec, dict):
                    continue
                candidate = isinstance(svc_name, str) and svc_name.lower() == "minio"
                img = spec.get("image", "")
                if candidate or (isinstance(img, str) and "minio/minio" in img.lower()):
                    port = _host_port_for_target(spec.get("ports"), 9000)
                    return f"http://127.0.0.1:{port or default_port}"
    except (OSError, yaml.YAMLError):
        pass
    return f"http://127.0.0.1:{default_port}"


def minio_console_url(compose_path: Path, *, default_port: int = 9001) -> str:
    """Browser console endpoint (typically host port mapped to container 9001)."""
    try:
        data = _load_compose_doc(compose_path)
        services = data.get("services", {})
        if isinstance(services, dict):
            for svc_name, spec in services.items():
                if not isinstance(spec, dict):
                    continue
                candidate = isinstance(svc_name, str) and svc_name.lower() == "minio"
                img = spec.get("image", "")
                if candidate or (isinstance(img, str) and "minio/minio" in img.lower()):
                    port = _host_port_for_target(spec.get("ports"), 9001)
                    return f"http://127.0.0.1:{port or default_port}"
    except (OSError, yaml.YAMLError):
        pass
    return f"http://127.0.0.1:{default_port}"


def _host_port_for_target(
    ports: Any,
    target_port: int,
) -> int | None:
    if ports is None or not isinstance(ports, list):
        return None
    for entry in ports:
        parsed = _parse_port_mapping(entry, target_port)
        if parsed is not None:
            return parsed
    return None


def _parse_port_mapping(entry: Any, target_port: int) -> int | None:  # noqa: PLR0911
    if isinstance(entry, dict):
        tgt = entry.get("target")
        pub = entry.get("published")
        if isinstance(tgt, int) and tgt == target_port:
            return int(pub) if isinstance(pub, int) else None
        return None
    if not isinstance(entry, str | int):
        return None
    text = str(entry).strip().strip('"').strip("'")
    if ":" not in text:
        return None
    left, _, right = text.rpartition(":")

    host_part = left.rsplit("/", maxsplit=1)[-1]
    try:
        host_p = int(host_part)
    except ValueError:
        return None
    ctr_raw = right.split("/")[0]
    try:
        ctr_p = int(ctr_raw)
    except ValueError:
        return None
    return host_p if ctr_p == target_port else None


def detect_compose_runner() -> ComposeRunner:
    """Resolve ``docker compose`` v2 if present, otherwise ``docker-compose`` v1."""
    docker_exe = shutil.which("docker")
    if not docker_exe:
        raise NucleusEnvironmentError(
            user_message="Docker is not installed or not on your PATH.",
            fix_hint=(
                "Install Docker Desktop or Docker Engine — see https://docs.docker.com/get-docker/"
            ),
        )

    try:
        probe = subprocess.run(
            [docker_exe, "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if probe.returncode == 0:
            return ComposeRunner(argv_prefix=(docker_exe, "compose"), is_v2=True)
    except (OSError, subprocess.TimeoutExpired):
        pass

    legacy = shutil.which("docker-compose")
    if legacy:
        try:
            chk = subprocess.run(
                [legacy, "version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if chk.returncode == 0:
                return ComposeRunner(argv_prefix=(legacy,), is_v2=False)
        except (OSError, subprocess.TimeoutExpired):
            pass

    raise NucleusEnvironmentError(
        user_message="Docker Compose is not available.",
        fix_hint=(
            "Install Compose v2 (bundled with modern Docker Desktop) or the "
            "standalone `docker-compose` v1 binary — see "
            "https://docs.docker.com/compose/install/"
        ),
    )


def build_compose_command(
    runner: ComposeRunner,
    compose_file: Path,
    compose_args: list[str],
) -> list[str]:
    """Build argv for ``compose`` subcommands (``up``, ``down``, …)."""
    fpath = str(compose_file.resolve())
    return [*runner.argv_prefix, "-f", fpath, *compose_args]


def run_compose(
    runner: ComposeRunner,
    cwd: Path,
    compose_file: Path,
    compose_args: list[str],
    *,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    """Run compose in ``cwd``."""

    cmd = build_compose_command(runner, compose_file, compose_args)
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd.resolve()),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise NucleusEnvironmentError(
            user_message=("The container runtime stopped responding during a Compose command."),
            fix_hint=(
                "Check that Docker is healthy (`docker ps`). If compose is wedged, "
                "restart Docker and retry."
            ),
            cause=exc,
        ) from exc
    except OSError as exc:
        raise NucleusEnvironmentError(
            user_message=f"Could not invoke the Compose CLI: {exc}",
            fix_hint="Verify Docker is installed and reachable, then retry.",
            cause=exc,
        ) from exc


_STDERR_PREVIEW_LINES = 5

_SIMPLE_PORT = re.compile(r"\b(\d{2,5})/tcp\b")


def first_five_stderr_lines(combined_stderr: str) -> str:
    """Trim stderr to five lines — user-visible snippet."""

    lines = [ln.strip() for ln in (combined_stderr or "").splitlines() if ln.strip()]
    return "\n".join(lines[:_STDERR_PREVIEW_LINES]).strip()


def translate_compose_process_failure(
    completed: subprocess.CompletedProcess[str],
) -> NucleusEnvironmentError | NucleusNetworkError:
    """Map compose exit codes + stderr to typed Nucleus errors."""

    haystack = "\n".join(filter(None, [completed.stderr or "", completed.stdout or ""]))
    lowered = haystack.lower()
    snippet = first_five_stderr_lines(completed.stderr or completed.stdout or "")

    pull_markers = (
        "pull access denied",
        "manifest unknown",
        "repository does not exist",
        "unable to retrieve image pull",
        "failed to solve",
        "error pulling image",
        "failed to fetch",
    )
    if any(m in lowered for m in pull_markers):
        return NucleusNetworkError(
            user_message=("Could not pull one or more container images for the local stack."),
            fix_hint=(
                "Check your network and registry access. If you are offline, fetch "
                "images while connected."
            ),
        )

    port_markers = (
        "address already in use",
        "port is already allocated",
        "already in use",
        "bind:",
    )
    if any(m in lowered for m in port_markers):
        port_note = ""
        m = _SIMPLE_PORT.search(completed.stderr or completed.stdout or "")
        if m:
            port_note = f"Port {m.group(1)} (TCP) may be occupied."
        um = (
            "A TCP port needed by your compose services appears to be in use. " + port_note
        ).strip()

        return NucleusEnvironmentError(
            user_message=um,
            fix_hint=(
                "Free ports 9000 / 9001 (defaults for MinIO) or edit the "
                "`ports:` section in docker-compose.yaml."
            ),
        )

    body = snippet or ""
    headline = "The container runtime reported an error when applying your compose stack." + (
        f"\n{body}" if body else ""
    )
    return NucleusEnvironmentError(
        user_message=headline.strip(),
        fix_hint=(
            "Run `docker compose up` manually from your project root for full logs "
            "(see https://docs.docker.com/compose/reference/)."
        ),
    )
