from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from .packs import get_contract_pack

VERILATOR_IMAGE = "verilator/verilator:v5.050"


@dataclass(frozen=True)
class SimulationParameters:
    data_width: int = 8
    depth: int = 4
    contract_id: str = "fifo"
    requesters: int = 4

    def __post_init__(self) -> None:
        if not 1 <= self.data_width <= 64:
            raise ValueError("DATA_WIDTH must be between 1 and 64")
        if not 1 <= self.depth <= 1024:
            raise ValueError("DEPTH must be between 1 and 1024")
        if not 2 <= self.requesters <= 32:
            raise ValueError("REQUESTERS must be between 2 and 32")
        get_contract_pack(self.contract_id)


@dataclass(frozen=True)
class SimulationOutcome:
    status: str
    parameters: SimulationParameters
    failures: list[object]
    observations: list[object]
    stdout: str
    stderr: str
    simulator_version: str | None
    trace_path: Path | None


def render_testbench(transactions: list[object], parameters: SimulationParameters) -> str:
    return get_contract_pack(parameters.contract_id).render_testbench(transactions, parameters)


def _msys_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    remainder = resolved.as_posix().split(":", 1)[-1]
    return f"/{drive}{remainder}"


def _run(command: list[str], workspace: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def _verilator(command: list[str], workspace: Path, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    if os.name == "nt":
        bash = Path("C:/msys64/usr/bin/bash.exe")
        if bash.exists():
            windows_command = ["/ucrt64/bin/verilator" if value == "verilator" else value for value in command]
            args = " ".join(shlex.quote(value) for value in windows_command)
            script = f"export PATH=/ucrt64/bin:$PATH; cd {shlex.quote(_msys_path(workspace))} && {args}"
            return _run([str(bash), "-lc", script], workspace, timeout_seconds)
    return _run(command, workspace, timeout_seconds)


def _version(workspace: Path) -> str | None:
    try:
        result = _verilator(["verilator", "--version"], workspace, 10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or result.stderr.strip() or None


def _parse_observations(stdout: str, parameters: SimulationParameters) -> list[object]:
    return get_contract_pack(parameters.contract_id).parse_observations(stdout)


def _compare(
    transactions: list[object], parameters: SimulationParameters, observations: list[object]
) -> list[object]:
    return get_contract_pack(parameters.contract_id).compare(transactions, parameters, observations)


def run_local_simulation(
    source: Path,
    transactions: list[object],
    parameters: SimulationParameters,
    workspace: Path,
    timeout_seconds: int = 20,
) -> SimulationOutcome:
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, workspace / "dut.sv")
    (workspace / "tb.sv").write_text(render_testbench(transactions, parameters), encoding="utf-8")
    version = _version(workspace)
    if version is None:
        return SimulationOutcome("infrastructure_failure", parameters, [], [], "", "Verilator not found", None, None)

    compile_command = [
        "verilator",
        "--binary",
        "--timing",
        "--trace",
        "--top-module",
        "tb",
        "--Mdir",
        "obj_dir",
        "-j",
        "1",
        "--Wno-fatal",
        "dut.sv",
        "tb.sv",
        "-o",
        "sim",
    ]
    try:
        compiled = _verilator(compile_command, workspace, timeout_seconds)
    except subprocess.TimeoutExpired as error:
        return SimulationOutcome("simulation_timeout", parameters, [], [], error.stdout or "", error.stderr or "", version, None)
    except FileNotFoundError as error:
        return SimulationOutcome("infrastructure_failure", parameters, [], [], "", str(error), version, None)
    if compiled.returncode != 0:
        return SimulationOutcome(
            "compile_failure", parameters, [], [], compiled.stdout, compiled.stderr, version, None
        )

    executable = "./obj_dir/sim.exe" if os.name == "nt" else "./obj_dir/sim"
    try:
        simulated = _verilator([executable], workspace, timeout_seconds)
    except subprocess.TimeoutExpired as error:
        return SimulationOutcome("simulation_timeout", parameters, [], [], error.stdout or "", error.stderr or "", version, None)
    observations = _parse_observations(simulated.stdout, parameters)
    if simulated.returncode != 0:
        return SimulationOutcome(
            "infrastructure_failure",
            parameters,
            [],
            observations,
            simulated.stdout,
            simulated.stderr,
            version,
            workspace / "trace.vcd" if (workspace / "trace.vcd").exists() else None,
        )

    failures = _compare(transactions, parameters, observations)
    return SimulationOutcome(
        "functional_mismatch" if failures else "passed",
        parameters,
        failures,
        observations,
        simulated.stdout,
        compiled.stderr + simulated.stderr,
        version,
        workspace / "trace.vcd" if (workspace / "trace.vcd").exists() else None,
    )


def outcome_to_dict(outcome: SimulationOutcome) -> dict[str, object]:
    data = asdict(outcome)
    data["trace_path"] = str(outcome.trace_path) if outcome.trace_path else None
    return data


def docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def container_security_args(workspace: Path, name: str) -> list[str]:
    user = "65532:65532" if os.name == "nt" else f"{os.getuid()}:{os.getgid()}"
    return [
        "docker",
        "run",
        "--name",
        name,
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "--pids-limit",
        "128",
        "--ulimit",
        "fsize=67108864:67108864",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=67108864",
        "--env",
        "CCACHE_DISABLE=1",
        "--user",
        user,
        "--mount",
        f"type=bind,source={workspace.resolve()},target=/work",
    ]


def _docker_script(workspace: Path, script: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    name = f"rtl-detective-{uuid4().hex[:12]}"
    command = container_security_args(workspace, name) + [
        "--entrypoint",
        "/bin/sh",
        VERILATOR_IMAGE,
        "-lc",
        f"cd /work && {script}",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, timeout=10, check=False)
        process.kill()
        stdout, stderr = process.communicate()
        raise subprocess.TimeoutExpired(command, timeout_seconds, stdout, stderr)
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def run_container_simulation(
    source: Path,
    transactions: list[object],
    parameters: SimulationParameters,
    workspace: Path,
    timeout_seconds: int = 20,
) -> SimulationOutcome:
    if source.is_symlink():
        return SimulationOutcome(
            "invalid_input", parameters, [], [], "", "symlink sources are not supported", None, None
        )
    if not docker_available():
        return SimulationOutcome(
            "infrastructure_failure",
            parameters,
            [],
            [],
            "",
            "Docker worker is unavailable; untrusted RTL was not executed",
            None,
            None,
        )

    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, workspace / "dut.sv")
    testbench = workspace / "tb.sv"
    testbench.write_text(render_testbench(transactions, parameters), encoding="utf-8")
    locked_hash = sha256(testbench.read_bytes()).hexdigest()
    try:
        version_result = _docker_script(workspace, "verilator --version", 30)
        compiled = _docker_script(
            workspace,
            "verilator --binary --timing --trace --top-module tb --Mdir obj_dir -j 1 "
            "--Wno-fatal dut.sv tb.sv -o sim",
            timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return SimulationOutcome("simulation_timeout", parameters, [], [], error.stdout or "", error.stderr or "", None, None)
    version = version_result.stdout.strip() or f"container {VERILATOR_IMAGE}"
    if compiled.returncode != 0:
        status = "infrastructure_failure" if "docker:" in compiled.stderr.lower() else "compile_failure"
        return SimulationOutcome(status, parameters, [], [], compiled.stdout, compiled.stderr, version, None)

    try:
        simulated = _docker_script(workspace, "./obj_dir/sim", timeout_seconds)
    except subprocess.TimeoutExpired as error:
        return SimulationOutcome("simulation_timeout", parameters, [], [], error.stdout or "", error.stderr or "", version, None)
    if sha256(testbench.read_bytes()).hexdigest() != locked_hash:
        return SimulationOutcome(
            "infrastructure_failure",
            parameters,
            [],
            [],
            simulated.stdout,
            "locked testbench changed during simulation",
            version,
            None,
        )

    observations = _parse_observations(simulated.stdout, parameters)
    trace = workspace / "trace.vcd"
    if simulated.returncode != 0:
        return SimulationOutcome(
            "infrastructure_failure",
            parameters,
            [],
            observations,
            simulated.stdout,
            simulated.stderr,
            version,
            trace if trace.exists() else None,
        )
    failures = _compare(transactions, parameters, observations)
    return SimulationOutcome(
        "functional_mismatch" if failures else "passed",
        parameters,
        failures,
        observations,
        simulated.stdout,
        compiled.stderr + simulated.stderr,
        version,
        trace if trace.exists() else None,
    )

