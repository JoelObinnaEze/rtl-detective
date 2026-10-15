from pathlib import Path

from backend.verification.arbiter import ArbiterModel, ArbiterTransaction
from backend.verification.packs import get_contract_pack
from backend.verification.runner import SimulationParameters, render_testbench, run_local_simulation
from backend.verification.security import validate_source


ROOT = Path(__file__).parents[1]


def test_round_robin_model_resets_and_rotates_between_requesters() -> None:
    model = ArbiterModel(requesters=3)

    assert model.step(ArbiterTransaction(rst=True, request=0b111)).grant == 0
    grants = [model.step(ArbiterTransaction(request=0b111)).grant for _ in range(4)]

    assert grants == [0b001, 0b010, 0b100, 0b001]


def test_arbiter_pack_builds_deterministic_regression_and_masks_requests() -> None:
    parameters = SimulationParameters(contract_id="arbiter", requesters=3)
    pack = get_contract_pack("arbiter")

    first = pack.regression_transactions(parameters)
    second = pack.regression_transactions(parameters)
    testbench = render_testbench([ArbiterTransaction(request=0b1111)], parameters)

    assert first == second
    assert first[0].rst is True
    assert "request = 3'h7;" in testbench
    assert "round_robin_arbiter #(.REQUESTERS(REQUESTERS)) dut" in testbench


def test_arbiter_source_requires_the_canonical_interface() -> None:
    source = (ROOT / "benchmark/designs/arbiter/correct/reference_arbiter.sv").read_text(encoding="utf-8")

    validate_source(source, "arbiter")


def test_correct_round_robin_arbiter_passes_real_simulation(tmp_path: Path) -> None:
    parameters = SimulationParameters(contract_id="arbiter", requesters=3)
    pack = get_contract_pack("arbiter")

    outcome = run_local_simulation(
        source=ROOT / "benchmark/designs/arbiter/correct/reference_arbiter.sv",
        transactions=pack.regression_transactions(parameters),
        parameters=parameters,
        workspace=tmp_path,
        timeout_seconds=30,
    )

    assert outcome.status == "passed", outcome.stderr
    assert outcome.failures == []


def test_fixed_priority_arbiter_produces_cycle_evidence(tmp_path: Path) -> None:
    parameters = SimulationParameters(contract_id="arbiter", requesters=3)
    pack = get_contract_pack("arbiter")

    outcome = run_local_simulation(
        source=ROOT / "benchmark/designs/arbiter/buggy/fixed_priority.sv",
        transactions=pack.regression_transactions(parameters),
        parameters=parameters,
        workspace=tmp_path,
        timeout_seconds=30,
    )

    assert outcome.status == "functional_mismatch", outcome.stderr
    assert outcome.failures[0].expected != outcome.failures[0].observed
