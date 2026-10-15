from pathlib import Path

from backend.verification.cases import directed_transactions, random_transactions
from backend.verification.contract import Transaction
from backend.verification.runner import (
    SimulationParameters,
    render_testbench,
    run_local_simulation,
)

ROOT = Path(__file__).parents[1]


def test_directed_sequence_exercises_contract_boundaries_and_wraparound() -> None:
    transactions = directed_transactions(depth=3)

    assert transactions[0].rst is True
    assert any(item.wr_en and item.rd_en for item in transactions)
    assert sum(item.wr_en for item in transactions) >= 9
    assert sum(item.rd_en for item in transactions) >= 9
    assert any(item.rst for item in transactions[1:])


def test_random_sequence_is_seeded_and_starts_with_reset() -> None:
    first = random_transactions(cycles=20, data_width=8, seed=42)
    second = random_transactions(cycles=20, data_width=8, seed=42)

    assert first == second
    assert first[0].rst is True


def test_testbench_masks_stimulus_to_the_declared_data_width() -> None:
    testbench = render_testbench(
        [Transaction(rst=False, wr_en=True, rd_en=False, din=0xA5)],
        SimulationParameters(data_width=1, depth=3),
    )

    assert "din = 1'h1;" in testbench
    assert "1'hA5" not in testbench


def test_correct_fifo_passes_non_power_of_two_contract(tmp_path: Path) -> None:
    outcome = run_local_simulation(
        source=ROOT / "benchmark/designs/correct/reference_fifo.sv",
        transactions=directed_transactions(depth=3),
        parameters=SimulationParameters(data_width=8, depth=3),
        workspace=tmp_path,
        timeout_seconds=30,
    )

    assert outcome.status == "passed", outcome.stderr
    assert outcome.failures == []
    assert outcome.trace_path is not None and outcome.trace_path.exists()


def test_buggy_simultaneous_count_update_produces_cycle_evidence(tmp_path: Path) -> None:
    outcome = run_local_simulation(
        source=ROOT / "benchmark/designs/buggy/simultaneous_count.sv",
        transactions=directed_transactions(depth=3),
        parameters=SimulationParameters(data_width=8, depth=3),
        workspace=tmp_path,
        timeout_seconds=30,
    )

    assert outcome.status == "functional_mismatch", outcome.stderr
    failure = outcome.failures[0]
    assert failure.cycle >= 0
    assert failure.expected != failure.observed
    assert failure.transaction.wr_en or failure.transaction.rd_en

