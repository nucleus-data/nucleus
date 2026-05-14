# ruff: noqa: ARG001
"""Tests for ``nucleus down`` — nucleus_cli_spec.md §3.3."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

import nucleus.cli.main as cli_mod
from nucleus.cli._compose import ComposeRunner
from nucleus.cli.main import app

runner = CliRunner(mix_stderr=False)

_V2_RUNNER = ComposeRunner(argv_prefix=("docker", "compose"), is_v2=True)


@pytest.fixture
def project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = tmp_path / "demo"
    project.mkdir()
    (project / "nucleus_project.yaml").write_text(
        "project:\n"
        "  name: demo\n"
        "  version: 0.1.0\n"
        "storage:\n"
        "  warehouse: ./data/warehouse\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(project)
    return project


@pytest.fixture
def project_with_compose(project_dir: Path) -> Path:
    (project_dir / "docker-compose.yaml").write_text(
        "services:\n  minio:\n    image: minio/minio\n",
        encoding="utf-8",
    )
    return project_dir


def test_down_no_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = runner.invoke(app, ["down"])
    assert out.exit_code == 1
    assert "Error:" in out.stderr


def test_down_no_compose_raises(project_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    def boom() -> ComposeRunner:
        raise AssertionError("detect must not run without compose file")

    monkeypatch.setattr(cli_mod, "detect_compose_runner", boom)

    result = runner.invoke(app, ["down"])
    assert result.exit_code == 1
    assert "docker-compose.yaml" in result.stderr


def test_down_default_preserves_volume_flag(project_with_compose: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    calls: list[list[str]] = []

    def fake_run(
        _runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any
    ) -> Any:
        _ = kw
        calls.append(list(args))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)

    result = runner.invoke(app, ["down"])
    assert result.exit_code == 0
    assert calls == [["down"]]
    assert "preserved" in result.stdout


def test_down_volumes_removes(project_with_compose: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    calls: list[list[str]] = []

    def fake_run(
        _runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any
    ) -> Any:
        _ = kw
        calls.append(list(args))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)

    result = runner.invoke(app, ["down", "--volumes"])
    assert result.exit_code == 0
    assert calls == [["down", "-v"]]


def test_down_compose_failure(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    def fake_run(
        _runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any
    ) -> Any:
        _ = kw
        return SimpleNamespace(returncode=1, stdout="", stderr="cannot stop container")

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)

    result = runner.invoke(app, ["down"])
    assert result.exit_code == 1
    assert "Error:" in result.stderr


def test_down_docker_missing(
    monkeypatch: pytest.MonkeyPatch, project_with_compose: Path
) -> None:

    def boom() -> ComposeRunner:
        from nucleus.errors import NucleusEnvironmentError

        raise NucleusEnvironmentError(
            user_message="Docker is missing.",
            fix_hint="Install it.",
        )

    monkeypatch.setattr(cli_mod, "detect_compose_runner", boom)

    result = runner.invoke(app, ["down"])
    assert result.exit_code == 1
    assert "Error:" in result.stderr


def test_v1_runner_invokes_docker_compose_binary(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    v1 = ComposeRunner(argv_prefix=("docker-compose",), is_v2=False)
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: v1)

    recorded: dict[str, Any] = {}

    def capture(
        runner: ComposeRunner, cwd: Path, compose_file: Path, args: list[str], **kw: Any
    ) -> Any:
        _ = kw
        recorded["runner"] = runner
        recorded["argv0"] = runner.argv_prefix[0]
        recorded["args"] = args
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(cli_mod, "run_compose", capture)

    result = runner.invoke(app, ["down"])
    assert result.exit_code == 0
    assert recorded["argv0"] == "docker-compose"
    assert recorded["args"] == ["down"]


def test_volume_flag_with_success_message(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    monkeypatch.setattr(
        cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0)  # noqa: ARG005
    )

    out = runner.invoke(app, ["down", "--volumes"])
    assert out.exit_code == 0
    assert "removed" in out.stdout


def test_warehouse_file_survives_volumes_flag(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    monkeypatch.setattr(
        cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0)  # noqa: ARG005
    )

    warehouse = project_with_compose / "data" / "warehouse"
    warehouse.mkdir(parents=True)
    sentinel = warehouse / "keep_me.parquet"
    sentinel.write_bytes(b"abc")

    result = runner.invoke(app, ["down", "--volumes"])
    assert result.exit_code == 0
    assert sentinel.read_bytes() == b"abc"


def test_down_prints_nucleus_footer(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    monkeypatch.setattr(
        cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0)  # noqa: ARG005
    )

    out = runner.invoke(app, ["down"])
    assert "Nucleus down" in out.stdout


def test_down_network_error_on_pull_like_stderr(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    def fake_run(
        _runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any
    ) -> Any:
        _ = kw
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Error response from daemon: pull access denied for x",
        )

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)

    res = runner.invoke(app, ["down"])
    assert res.exit_code == 1


def test_down_port_style_error_still_surfaces(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)

    def fake_run(
        _runner: Any, _cwd: Path, _compose: Path, args: list[str], **kw: Any
    ) -> Any:
        _ = kw
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="port is already allocated",
        )

    monkeypatch.setattr(cli_mod, "run_compose", fake_run)

    res = runner.invoke(app, ["down"])
    assert res.exit_code == 1


def test_down_idempotent_success_zero(
    project_with_compose: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_mod, "detect_compose_runner", lambda: _V2_RUNNER)
    monkeypatch.setattr(
        cli_mod, "run_compose", lambda *a, **k: SimpleNamespace(returncode=0)  # noqa: ARG005
    )

    first = runner.invoke(app, ["down"])
    second = runner.invoke(app, ["down"])
    assert first.exit_code == second.exit_code == 0
