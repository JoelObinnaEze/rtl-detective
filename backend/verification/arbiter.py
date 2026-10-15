from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.providers.nebius import TransactionAction
    from .runner import SimulationParameters


REQUIRED_IDENTIFIERS = (
    "round_robin_arbiter",
    "REQUESTERS",
    "clk",
    "rst",
    "request",
    "grant",
)
SUMMARY = """Round-robin arbiter contract: synchronous active-high reset; registered one-hot-or-zero grant;
requests are sampled before the rising edge; selection starts at the saved priority and wraps by requester index;
a successful grant advances priority to the following requester; no request produces zero grant and holds priority."""
LIMITATION = "Only the selected canonical registered round-robin arbiter contract is supported by this pack."


@dataclass(frozen=True)
class ArbiterTransaction:
    rst: bool = False
    request: int = 0


@dataclass(frozen=True)
class ArbiterSnapshot:
    cycle: int
    transaction: ArbiterTransaction
    grant: int


@dataclass(frozen=True)
class ArbiterObservation:
    cycle: int
    grant: int


@dataclass(frozen=True)
class ArbiterFailure:
    cycle: int
    transaction: ArbiterTransaction
    expected: dict[str, int | bool]
    observed: dict[str, int | bool]


class ArbiterModel:
    def __init__(self, requesters: int) -> None:
        if not 2 <= requesters <= 32:
            raise ValueError("REQUESTERS must be between 2 and 32")
        self.requesters = requesters
        self._mask = (1 << requesters) - 1
        self._priority = 0
        self._cycle = -1

    def step(self, transaction: ArbiterTransaction) -> ArbiterSnapshot:
        self._cycle += 1
        if transaction.rst:
            self._priority = 0
            grant = 0
        else:
            grant = 0
            request = transaction.request & self._mask
            for offset in range(self.requesters):
                index = (self._priority + offset) % self.requesters
                if request & (1 << index):
                    grant = 1 << index
                    self._priority = (index + 1) % self.requesters
                    break
        return ArbiterSnapshot(self._cycle, transaction, grant)


def directed_transactions(requesters: int) -> list[ArbiterTransaction]:
    mask = (1 << requesters) - 1
    transactions = [ArbiterTransaction(rst=True, request=mask), ArbiterTransaction()]
    transactions.extend(ArbiterTransaction(request=1 << index) for index in range(requesters))
    transactions.extend(ArbiterTransaction(request=mask) for _ in range(requesters * 2))
    odd = sum(1 << index for index in range(1, requesters, 2))
    even = mask ^ odd
    transactions.extend([ArbiterTransaction(request=odd), ArbiterTransaction(request=even)] * requesters)
    transactions.extend([ArbiterTransaction(rst=True, request=mask), ArbiterTransaction()])
    return transactions


def random_transactions(cycles: int, requesters: int, seed: int) -> list[ArbiterTransaction]:
    if cycles < 1:
        raise ValueError("cycles must be at least 1")
    random = Random(seed)
    transactions = [ArbiterTransaction(rst=True)]
    for _ in range(cycles - 1):
        transactions.append(
            ArbiterTransaction(rst=random.random() < 0.03, request=random.getrandbits(requesters))
        )
    return transactions


def regression_transactions(parameters: SimulationParameters) -> list[ArbiterTransaction]:
    transactions = directed_transactions(parameters.requesters)
    transactions.extend(random_transactions(48, parameters.requesters, seed=1))
    return transactions


def transaction_from_action(action: TransactionAction) -> ArbiterTransaction:
    return ArbiterTransaction(rst=action.rst, request=action.request or 0)


def parameter_summary(parameters: SimulationParameters) -> str:
    return f"REQUESTERS={parameters.requesters}"


def render_testbench(transactions: list[ArbiterTransaction], parameters: SimulationParameters) -> str:
    drives = []
    mask = (1 << parameters.requesters) - 1
    for cycle, item in enumerate(transactions):
        request = item.request & mask
        drives.append(
            f"""    @(negedge clk);
    rst = {int(item.rst)}; request = {parameters.requesters}'h{request:X};
    @(posedge clk); #1;
    $display(\"RTLDET|%0d|%0d\", {cycle}, grant);"""
        )

    return f"""`timescale 1ns/1ps
module tb;
  localparam int REQUESTERS = {parameters.requesters};
  logic clk = 0;
  logic rst = 0;
  logic [REQUESTERS-1:0] request = '0;
  logic [REQUESTERS-1:0] grant;

  round_robin_arbiter #(.REQUESTERS(REQUESTERS)) dut (.*);
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


def parse_observations(stdout: str) -> list[ArbiterObservation]:
    observations = []
    for line in stdout.splitlines():
        if not line.startswith("RTLDET|"):
            continue
        _, cycle, grant = line.split("|")
        observations.append(ArbiterObservation(cycle=int(cycle), grant=int(grant)))
    return observations


def compare(
    transactions: list[ArbiterTransaction],
    parameters: SimulationParameters,
    observations: list[ArbiterObservation],
) -> list[ArbiterFailure]:
    model = ArbiterModel(parameters.requesters)
    expected = [model.step(item) for item in transactions]
    observed_by_cycle = {item.cycle: item for item in observations}
    failures = []
    for snapshot in expected:
        observed = observed_by_cycle.get(snapshot.cycle)
        expected_state: dict[str, int | bool] = {"grant": snapshot.grant}
        observed_state: dict[str, int | bool] = {"grant": observed.grant if observed else -1}
        if expected_state != observed_state:
            failures.append(
                ArbiterFailure(
                    cycle=snapshot.cycle,
                    transaction=snapshot.transaction,
                    expected=expected_state,
                    observed=observed_state,
                )
            )
    return failures
