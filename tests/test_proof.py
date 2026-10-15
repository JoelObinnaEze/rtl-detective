from dataclasses import asdict
from pathlib import Path

from backend.agent.proof import IntegrityProof, RunLimits, derive_claim, summarize_outcome
from backend.verification.fifo import FifoFailure
from backend.verification.contract import Transaction
from backend.verification.runner import SimulationOutcome, SimulationParameters


def test_outcome_summary_contains_only_portable_executed_evidence() -> None:
    parameters = SimulationParameters(data_width=8, depth=3)
    failure = FifoFailure(
        cycle=4,
        transaction=Transaction(wr_en=True, din=7),
        write_accepted=True,
        read_accepted=False,
        expected={"count": 2},
        observed={"count": 1},
    )
    outcome = SimulationOutcome(
        "functional_mismatch",
        parameters,
        [failure],
        [],
        "",
        "",
        "Verilator 5.050",
        Path("C:/private/work/trace.vcd"),
    )

    summary = summarize_outcome(outcome, transaction_count=5, trace_artifact="trace.vcd")

    assert asdict(summary) == {
        "status": "functional_mismatch",
        "transaction_count": 5,
        "first_failure": {
            "cycle": 4,
            "transaction": {"rst": False, "wr_en": True, "rd_en": False, "din": 7},
            "write_accepted": True,
            "read_accepted": False,
            "expected": {"count": 2},
            "observed": {"count": 1},
        },
        "simulator_version": "Verilator 5.050",
        "trace_artifact": "trace.vcd",
    }
    assert "C:/private" not in str(asdict(summary))


def test_claim_requires_every_success_gate() -> None:
    assert (
        derive_claim(
            "candidate_passed_listed_tests",
            baseline_status="functional_mismatch",
            reproducer_status="passed",
            regression_status="passed",
            locked_assets_unchanged=True,
        )
        == "Candidate passed the reproducer and listed locked regression tests."
    )
    assert (
        derive_claim(
            "candidate_passed_listed_tests",
            baseline_status="functional_mismatch",
            reproducer_status="passed",
            regression_status="functional_mismatch",
            locked_assets_unchanged=True,
        )
        == "Failure reproduced; repair not verified."
    )
    assert (
        derive_claim(
            "candidate_passed_listed_tests",
            baseline_status="functional_mismatch",
            reproducer_status="passed",
            regression_status="passed",
            locked_assets_unchanged=False,
        )
        == "Failure reproduced; repair not verified."
    )


def test_proof_metadata_is_immutable_and_explicit() -> None:
    limits = RunLimits(max_patch_attempts=3, simulation_timeout_seconds=30)
    integrity = IntegrityProof("abc", {"oracle": "one"}, {"oracle": "one"})

    assert asdict(limits) == {"max_patch_attempts": 3, "simulation_timeout_seconds": 30}
    assert asdict(integrity)["locked_assets_unchanged"] is True
