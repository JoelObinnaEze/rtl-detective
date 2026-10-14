from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import shlex
import shutil
import subprocess

from .contract import FifoModel, Snapshot, Transaction, count_width


@dataclass(frozen=True)
class SimulationParameters:
    data_width: int = 8
    depth: int = 4

    def __post_init__(self) -> None:
        if not 1 <= self.data_width <= 64:
            raise ValueError("DATA_WIDTH must be between 1 and 64")
        if not 1 <= self.depth <= 1024:
            raise ValueError("DEPTH must be between 1 and 1024")


@dataclass(frozen=True)
class Observation:
    cycle: int
    dout: int
    full: bool
    empty: bool
    count: int


@dataclass(frozen=True)
class Failure:
    cycle: int
    transaction: Transaction
    write_accepted: bool
    read_accepted: bool
    expected: dict[str, int | bool]
    observed: dict[str, int | bool]


@dataclass(frozen=True)
class SimulationOutcome:
    status: str
    parameters: SimulationParameters
    failures: list[Failure]
    observations: list[Observation]
    stdout: str
    stderr: str
    simulator_version: str | None
    trace_path: Path | None


def render_testbench(transactions: list[Transaction], parameters: SimulationParameters) -> str:
    drives = []
    for cycle, item in enumerate(transactions):
        drives.append(
            f"""    @(negedge clk);
    rst = {int(item.rst)}; wr_en = {int(item.wr_en)}; rd_en = {int(item.rd_en)}; din = {parameters.data_width}'h{item.din:X};
    @(posedge clk); #1;
    $display(\"RTLDET|%0d|%0d|%0d|%0d|%0d\", {cycle}, dout, full, empty, count);"""
        )

    return f"""`timescale 1ns/1ps
module tb;
  localparam int DATA_WIDTH = {parameters.data_width};
  localparam int DEPTH = {parameters.depth};
  localparam int COUNT_WIDTH = {count_width(parameters.depth)};
  logic clk = 0;
  logic rst = 0;
  logic wr_en = 0;
  logic rd_en = 0;
  logic [DATA_WIDTH-1:0] din = '0;
  logic [DATA_WIDTH-1:0] dout;
  logic full;
  logic empty;
  logic [COUNT_WIDTH-1:0] count;

  fifo #(.DATA_WIDTH(DATA_WIDTH), .DEPTH(DEPTH)) dut (.*);
  always #5 clk = ~clk;

  initial begin
    $dumpfile(\"trace.vcd\");
    $dumpvars(0, tb);
{chr(10).join(drives)}
    $finish;
  end

  initial begin
    #{max(1000, len(transactions) * 20)};
    $fatal(1, \"simulation timeout\");
  end
endmodule
"""


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


def _parse_observations(stdout: str) -> list[Observation]:
    observations = []
    for line in stdout.splitlines():
        if not line.startswith("RTLDET|"):
            continue
        _, cycle, dout, full, empty, count = line.split("|")
        observations.append(
            Observation(
                cycle=int(cycle),
                dout=int(dout),
                full=bool(int(full)),
                empty=bool(int(empty)),
                count=int(count),
            )
        )
    return observations


def _compare(
    transactions: list[Transaction], parameters: SimulationParameters, observations: list[Observation]
) -> list[Failure]:
    model = FifoModel(parameters.data_width, parameters.depth)
    expected: list[Snapshot] = [model.step(item) for item in transactions]
    observed_by_cycle = {item.cycle: item for item in observations}
    failures = []
    for snapshot in expected:
        observed = observed_by_cycle.get(snapshot.cycle)
        expected_state = {
            "dout": snapshot.dout,
            "full": snapshot.full,
            "empty": snapshot.empty,
            "count": snapshot.count,
        }
        observed_state = (
            {"dout": observed.dout, "full": observed.full, "empty": observed.empty, "count": observed.count}
            if observed
            else {"dout": -1, "full": False, "empty": False, "count": -1}
        )
        if expected_state != observed_state:
            failures.append(
                Failure(
                    cycle=snapshot.cycle,
                    transaction=snapshot.transaction,
                    write_accepted=snapshot.write_accepted,
                    read_accepted=snapshot.read_accepted,
                    expected=expected_state,
                    observed=observed_state,
                )
            )
    return failures


def run_local_simulation(
    source: Path,
    transactions: list[Transaction],
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
        "0",
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
    observations = _parse_observations(simulated.stdout)
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

