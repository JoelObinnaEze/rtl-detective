import json
from pathlib import Path

import pytest

from backend.verification.cases import directed_transactions
from backend.verification.runner import SimulationParameters, run_local_simulation


ROOT = Path(__file__).parents[1]
CASES = json.loads((ROOT / "benchmark/manifests/cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_benchmark_matches_hidden_expected_outcome(case: dict[str, object], tmp_path: Path) -> None:
    parameters = SimulationParameters(data_width=int(case["data_width"]), depth=int(case["depth"]))
    outcome = run_local_simulation(
        ROOT / "benchmark" / str(case["source"]),
        directed_transactions(parameters.depth),
        parameters,
        tmp_path,
        timeout_seconds=30,
    )

    assert outcome.status == case["expected"], outcome.stderr

