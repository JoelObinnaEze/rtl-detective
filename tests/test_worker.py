from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

import pytest

from backend.verification.runner import (
    SimulationParameters,
    container_security_args,
    docker_available,
    run_container_simulation,
    run_local_simulation,
)


def test_docker_availability_probe_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*_args: object, **kwargs: object) -> SimpleNamespace:
        assert kwargs["timeout"] == 1
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr("backend.verification.runner.subprocess.run", unavailable)

    assert not docker_available()


def test_container_worker_is_networkless_read_only_and_resource_bounded(tmp_path: Path) -> None:
    args = container_security_args(tmp_path, "worker-1")
    command = " ".join(args)

    assert "--network none" in command
    assert "--read-only" in args
    assert "--cap-drop ALL" in command
    assert "no-new-privileges:true" in command
    assert "--memory 512m" in command
    assert "--cpus 1" in command
    assert "--pids-limit 128" in command
    assert "fsize=67108864:67108864" in command
    assert "--env CCACHE_DISABLE=1" in command
    assert "--user" in args
    assert all("NEBIUS" not in value for value in args)
    assert str(tmp_path.resolve()) in command


def test_local_verilator_compile_uses_one_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []
    source = tmp_path / "source.sv"
    source.write_text("module dut; endmodule", encoding="utf-8")

    monkeypatch.setattr("backend.verification.runner._version", lambda _workspace: "Verilator")

    def record(command: list[str], _workspace: Path, _timeout: int) -> CompletedProcess[str]:
        commands.append(command)
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("backend.verification.runner._verilator", record)

    run_local_simulation(source, [], SimulationParameters(), tmp_path / "run")

    assert commands[0][commands[0].index("-j") + 1] == "1"


def test_container_verilator_compile_uses_one_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripts: list[str] = []
    source = tmp_path / "source.sv"
    source.write_text("module dut; endmodule", encoding="utf-8")

    monkeypatch.setattr("backend.verification.runner.docker_available", lambda: True)

    def record(_workspace: Path, script: str, _timeout: int) -> CompletedProcess[str]:
        scripts.append(script)
        return CompletedProcess([], 0, "Verilator", "")

    monkeypatch.setattr("backend.verification.runner._docker_script", record)

    run_container_simulation(source, [], SimulationParameters(), tmp_path / "run")

    assert " -j 1 " in scripts[1]

