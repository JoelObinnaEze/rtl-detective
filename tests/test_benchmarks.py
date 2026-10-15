import json
from pathlib import Path

import pytest

from backend.verification.packs import get_contract_pack
from backend.verification.runner import SimulationParameters, run_local_simulation


ROOT = Path(__file__).parents[1]
CASES = json.loads((ROOT / "benchmark/manifests/cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_benchmark_matches_hidden_expected_outcome(case: dict[str, object], tmp_path: Path) -> None:
    contract_id = str(case.get("contract_id", "fifo"))
    parameters = SimulationParameters(
        contract_id=contract_id,
        data_width=int(case.get("data_width", 8)),
        depth=int(case.get("depth", 4)),
        requesters=int(case.get("requesters", 4)),
    )
    pack = get_contract_pack(contract_id)
    outcome = run_local_simulation(
        ROOT / "benchmark" / str(case["source"]),
        pack.regression_transactions(parameters),
        parameters,
        tmp_path,
        timeout_seconds=30,
    )

    assert outcome.status == case["expected"], outcome.stderr


def test_benchmark_covers_both_contract_packs() -> None:
    assert {case.get("contract_id", "fifo") for case in CASES} == {"fifo", "arbiter"}

