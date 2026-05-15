# ruff: noqa: ARG001
"""Tests for ``nucleus up`` — nucleus_cli_spec.md §3.2."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

import nucleus.cli.main as cli_mod
from nucleus.cli._compose import ComposeRunner
from nucleus.cli.main import app

runner = CliRunner(mix_stderr=False)

_V2_RUNNER = ComposeRunner(argv_prefix=("docker", "compose"), is_v2=True)
_V1_RUNNER = ComposeRunner(argv_prefix=("docker-compose",), is_v2=False)


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "nucleus_project.yaml").write_text(
        "project:\n  name: demo\n  version: 0.1.0\nstorage:\n  warehouse: ./data/warehouse\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    return project


@pytest.fixture
def project_with_compose(project_dir: Path) -> Path:
    text = "\n".join(("services:", "  minio:", "    image: minio/minio"))
    (project_dir / "docker-compose.yaml").write_text(f"{text}\n", encoding="utf-8")
    return project_dir


def test_no_project_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert "Error" in result.stderr


def test_missing_compose_yaml_raises(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert "docker-compose.yaml" in result.stderr
    assert "Error" in result.stderr


def test_docker_missing_raises(monkeypatch: pytest.MonkeyPatch, project_with_compose: Path) -> None:

    def boom() -> ComposeRunner:
        from nucleus.errors import NucleusEnvironmentError

        raise NucleusEnvironmentError(
            user_message="Docker is not installed or not on your PATH.",
            fix_hint="Install Docker.",
        )

    monkeypatch.setattr(cli_mod, "detect_compose_runner", boom)

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert "Error" in result.stderr
    assert "Docker is not installed" in result.stderr


def test_success_path_writes_warehouse(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    proc_calls: list[list[str]] = []

    def fake_run(_runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any) -> Any:
        _ = kw
        proc_calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)
    monkeypatch.setattr(cli_mod, "_wait_local_storage_ready", lambda _u: None)

    result = runner.invoke(app, ["up"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert proc_calls == [["up", "-d"]]
    assert "Local stack" in result.stdout
    assert "minio (S3 API)" in result.stdout
    warehouse = project_with_compose / "data" / "warehouse" / "catalog.db"
    assert warehouse.is_file()


@pytest.mark.parametrize("compose_runner_variant", [_V2_RUNNER, _V1_RUNNER])
def test_detect_runner_variants_used(
    project_with_compose: Path,
    monkeypatch: pytest.MonkeyPatch,
    compose_runner_variant: ComposeRunner,
) -> None:

    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: compose_runner_variant)
    monkeypatch.setattr(cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0))  # noqa: ARG005
    monkeypatch.setattr(cli_mod, "_wait_local_storage_ready", lambda _u: None)

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0, result.stderr


@pytest.mark.parametrize("invalid_cat", ["lakekeeper", "polaris"])
def test_unsupported_catalog(
    invalid_cat: str,
    project_with_compose: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    traces: list[int] = []

    def trap(*args: Any, **kwargs: Any) -> SimpleNamespace:
        traces.append(1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    monkeypatch.setattr(cli_mod, "run_compose", trap)

    result = runner.invoke(app, ["up", "--catalog", invalid_cat])
    assert result.exit_code == 1
    assert traces == []


def test_unsupported_profile(monkeypatch: pytest.MonkeyPatch, project_with_compose: Path) -> None:

    traces: list[int] = []

    def trap(*args: Any, **kwargs: Any) -> SimpleNamespace:
        traces.append(1)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    monkeypatch.setattr(cli_mod, "run_compose", trap)

    result = runner.invoke(app, ["up", "--profile", "staging"])
    assert result.exit_code == 1
    assert traces == []


def test_rebuild_issues_down_then_up(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    calls: list[list[str]] = []

    def fake_run(_runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any) -> Any:
        _ = kw
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)
    monkeypatch.setattr(cli_mod, "_wait_local_storage_ready", lambda _u: None)

    result = runner.invoke(app, ["up", "--rebuild"])
    assert result.exit_code == 0
    assert calls[:2] == [["down", "-v"], ["up", "-d"]]


def test_compose_failure_translates_environment(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    def fake_run(_runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any) -> Any:
        _ = kw
        if args == ["up", "-d"]:
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="failed to bind 0.0.0.0:9000 tcp: bind: address already in use",
            )

        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert "Error" in result.stderr


def test_image_pull_maps_to_network_error(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    def fake_run(_runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any) -> Any:
        _ = kw
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="manifest unknown: image tag not found during pull attempt",
        )

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert "Error" in result.stderr
    assert "pull" in result.stderr.lower() or "image" in result.stderr.lower()


def test_health_poll_timeout(project_with_compose: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    monkeypatch.setattr(cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0))  # noqa: ARG005

    def stubborn(_url: str) -> None:
        from nucleus.errors import NucleusTimeoutError

        raise NucleusTimeoutError(user_message="Local storage waited too long.", fix_hint="Retry.")

    monkeypatch.setattr(cli_mod, "_wait_local_storage_ready", stubborn)

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 1
    assert "Error" in result.stderr


def test_http_poll_uses_httpx(project_with_compose: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    monkeypatch.setattr(cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0))  # noqa: ARG005

    monkeypatch.setattr(cli_mod.time, "sleep", lambda _: None)

    calls = {"n": 0}

    def fake_get(_url: str, *_a: Any, **_kw: Any) -> Any:
        calls["n"] += 1
        if calls["n"] < 3:

            class R:
                status_code = 503

            return R()

        class R2:
            status_code = 200

        return R2()

    monkeypatch.setattr(httpx, "get", fake_get)

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0, result.stderr
    assert calls["n"] >= 3


def test_health_ready_immediately(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    monkeypatch.setattr(cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0))  # noqa: ARG005

    monkeypatch.setattr(cli_mod.time, "sleep", lambda _: None)

    def ok_get(_url: str, *_a: Any, **_kw: Any) -> Any:

        class R:
            status_code = 200

        return R()

    monkeypatch.setattr(httpx, "get", ok_get)

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0


COMPOSE_WITHOUT_MINIO = (
    'services:\n  other:\n    image: busybox:latest\n    command: ["sleep","infinity"]\n'
)


def test_skips_minio_poll_when_not_declared(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project_dir / "docker-compose.yaml").write_text(COMPOSE_WITHOUT_MINIO)
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    called = {"wait": False}

    def noop_wait(_url: str) -> None:
        called["wait"] = True

    monkeypatch.setattr(cli_mod, "_wait_local_storage_ready", noop_wait)
    monkeypatch.setattr(cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0))  # noqa: ARG005

    result = runner.invoke(app, ["up"])
    assert result.exit_code == 0
    assert called["wait"] is False


def test_rebuild_down_failure_raises(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    def fake_run(_runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any) -> Any:
        _ = kw
        if args == ["down", "-v"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="compose down exploded")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)

    result = runner.invoke(app, ["up", "--rebuild"])
    assert result.exit_code == 1
    assert "Error" in result.stderr
