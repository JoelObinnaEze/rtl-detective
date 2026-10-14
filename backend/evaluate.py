from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path
import time

from backend.verification.cases import directed_transactions, random_transactions
from backend.verification.runner import SimulationParameters, outcome_to_dict, run_local_simulation


DATA_WIDTHS = (1, 8, 16)
DEPTHS = (1, 2, 3, 4, 7, 8)


def regression_matrix() -> list[SimulationParameters]:
    return [SimulationParameters(data_width=width, depth=depth) for width, depth in product(DATA_WIDTHS, DEPTHS)]


def run_matrix(source: Path, output_directory: Path, seeds: tuple[int, ...] = (1, 2, 3)) -> dict[str, object]:
    output_directory.mkdir(parents=True, exist_ok=True)
    records = []
    for parameters in regression_matrix():
        transactions = directed_transactions(parameters.depth)
        for seed in seeds:
            transactions.extend(random_transactions(64, parameters.data_width, seed))
        started = time.monotonic()
        outcome = run_local_simulation(
            source,
            transactions,
            parameters,
            output_directory / f"dw{parameters.data_width}-d{parameters.depth}",
            timeout_seconds=60,
        )
        records.append(
            {
                "data_width": parameters.data_width,
                "depth": parameters.depth,
                "seeds": list(seeds),
                "duration_ms": round((time.monotonic() - started) * 1000),
                "result": outcome_to_dict(outcome),
            }
        )
    passed = sum(record["result"]["status"] == "passed" for record in records)
    return {
        "definition": {
            "configurations": len(records),
            "seeds_per_configuration": len(seeds),
            "total_seeded_runs": len(records) * len(seeds),
        },
        "summary": {"passed_configurations": passed, "total_configurations": len(records)},
        "records": records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the published offline FIFO regression matrix")
    parser.add_argument("--source", type=Path, default=Path("benchmark/designs/correct/reference_fifo.sv"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluation"))
    args = parser.parse_args(argv)
    result = run_matrix(args.source, args.output)
    destination = args.output / "matrix-results.json"
    destination.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(destination.resolve())
    return 0 if result["summary"]["passed_configurations"] == result["summary"]["total_configurations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

