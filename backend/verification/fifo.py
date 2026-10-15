from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .cases import directed_transactions, random_transactions
from .contract import FifoModel, Snapshot, Transaction, count_width

if TYPE_CHECKING:
    from backend.providers.nebius import TransactionAction
    from .runner import SimulationParameters


REQUIRED_IDENTIFIERS = (
    "fifo",
    "DATA_WIDTH",
    "DEPTH",
    "clk",
    "rst",
    "wr_en",
    "rd_en",
    "din",
    "dout",
    "full",
    "empty",
    "count",
)
SUMMARY = """Single-clock FIFO contract: synchronous active-high reset; registered dout; pre-edge acceptance;
full simultaneous read/write accepts read only; empty simultaneous accepts write only; partial simultaneous accepts both;
reset clears queue, count, and dout; explicit non-power-of-two wrapping; no fall-through."""
LIMITATION = "Only the selected canonical single-clock FIFO contract is supported by this pack."


@dataclass(frozen=True)
class FifoObservation:
    cycle: int
    dout: int
    full: bool
    empty: bool
    count: int


@dataclass(frozen=True)
class FifoFailure:
    cycle: int
    transaction: Transaction
    write_accepted: bool
    read_accepted: bool
    expected: dict[str, int | bool]
    observed: dict[str, int | bool]


def regression_transactions(parameters: SimulationParameters) -> list[Transaction]:
    transactions = directed_transactions(parameters.depth)
    transactions.extend(random_transactions(48, parameters.data_width, seed=1))
    return transactions


def transaction_from_action(action: TransactionAction) -> Transaction:
    return Transaction(rst=action.rst, wr_en=action.wr_en, rd_en=action.rd_en, din=action.din)


def parameter_summary(parameters: SimulationParameters) -> str:
    return f"DATA_WIDTH={parameters.data_width}, DEPTH={parameters.depth}"


def render_testbench(transactions: list[Transaction], parameters: SimulationParameters) -> str:
    drives = []
    for cycle, item in enumerate(transactions):
        masked_din = item.din & ((1 << parameters.data_width) - 1)
        drives.append(
            f"""    @(negedge clk);
    rst = {int(item.rst)}; wr_en = {int(item.wr_en)}; rd_en = {int(item.rd_en)}; din = {parameters.data_width}'h{masked_din:X};
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


def parse_observations(stdout: str) -> list[FifoObservation]:
    observations = []
    for line in stdout.splitlines():
        if not line.startswith("RTLDET|"):
            continue
        _, cycle, dout, full, empty, count = line.split("|")
        observations.append(
            FifoObservation(
                cycle=int(cycle),
                dout=int(dout),
                full=bool(int(full)),
                empty=bool(int(empty)),
                count=int(count),
            )
        )
    return observations


def compare(
    transactions: list[Transaction], parameters: SimulationParameters, observations: list[FifoObservation]
) -> list[FifoFailure]:
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
                FifoFailure(
                    cycle=snapshot.cycle,
                    transaction=snapshot.transaction,
                    write_accepted=snapshot.write_accepted,
                    read_accepted=snapshot.read_accepted,
                    expected=expected_state,
                    observed=observed_state,
                )
            )
    return failures
