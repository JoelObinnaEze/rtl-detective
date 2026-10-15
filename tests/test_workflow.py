from dataclasses import dataclass
import difflib
from pathlib import Path

from backend.agent.workflow import RepairWorkflow
from backend.providers.nebius import (
    InvestigationAction,
    ModelReply,
    PatchAction,
    ProviderError,
    TransactionAction,
)
from backend.verification.fifo import FifoFailure
from backend.verification.contract import Transaction
from backend.verification.runner import SimulationOutcome, SimulationParameters


ROOT = Path(__file__).parents[1]


@dataclass
class FakeProvider:
    source: str
    investigation_calls: int = 0
    patch_calls: int = 0

    def verify_model(self) -> None:
        pass

    def investigate(self, evidence: str) -> ModelReply[InvestigationAction]:
        self.investigation_calls += 1
        assert "observed" in evidence
        action = InvestigationAction(
            hypothesis="Both count assignments execute; the read assignment wins.",
            evidence_cycles=[6],
            transactions=[
                TransactionAction(rst=True),
                TransactionAction(wr_en=True, din=1),
                TransactionAction(wr_en=True, din=2),
                TransactionAction(wr_en=True, rd_en=True, din=3),
            ],
        )
        return ModelReply(action, "fake", "fake/nemotron", 1, {"total_tokens": 1}, "investigate-1")

    def propose_patch(self, source_and_evidence: str) -> ModelReply[PatchAction]:
        self.patch_calls += 1
        fixed = self.source.replace(
            "        count <= count + 1'b1;\n",
            "",
        ).replace(
            "        count <= count - 1'b1;\n      end\n",
            "      end\n      case ({write_accepted, read_accepted})\n"
            "        2'b10: count <= count + 1'b1;\n"
            "        2'b01: count <= count - 1'b1;\n"
            "        default: count <= count;\n"
            "      endcase\n",
        )
        diff = "".join(
            difflib.unified_diff(
                self.source.splitlines(keepends=True),
                fixed.splitlines(keepends=True),
                fromfile="a/dut.sv",
                tofile="b/dut.sv",
            )
        )
        action = PatchAction(diagnosis="The two nonblocking count assignments conflict.", diff=diff)
        return ModelReply(action, "fake", "fake/nemotron", 1, {"total_tokens": 1}, "patch-1")


class RejectingPatchProvider(FakeProvider):
    def propose_patch(self, source_and_evidence: str) -> ModelReply[PatchAction]:
        self.patch_calls += 1
        action = PatchAction(
            diagnosis="The model attempted to edit a locked testbench.",
            diff="diff --git a/tb.sv b/tb.sv\n--- a/tb.sv\n+++ b/tb.sv\n@@ -1 +1 @@\n-old\n+new\n",
        )
        return ModelReply(action, "fake", "fake/nemotron", 2, {"total_tokens": 2}, "patch-rejected")


class FailingPatchProvider(FakeProvider):
    def propose_patch(self, source_and_evidence: str) -> ModelReply[PatchAction]:
        raise ProviderError("provider unavailable")


def mismatch(parameters: SimulationParameters) -> SimulationOutcome:
    failure = FifoFailure(
        cycle=3,
        transaction=Transaction(wr_en=True, rd_en=True, din=3),
        write_accepted=True,
        read_accepted=True,
        expected={"count": 2},
        observed={"count": 1},
    )
    return SimulationOutcome(
        "functional_mismatch",
        parameters,
        [failure],
        [],
        "",
        "",
        "Verilator 5.050",
        Path("C:/private/work/trace.vcd"),
    )


def passed(parameters: SimulationParameters) -> SimulationOutcome:
    return SimulationOutcome("passed", parameters, [], [], "", "", "Verilator 5.050", None)


def test_correct_fifo_finishes_without_model_or_patch(tmp_path: Path) -> None:
    source_path = ROOT / "benchmark/designs/correct/reference_fifo.sv"
    provider = FakeProvider(source_path.read_text(encoding="utf-8"))

    report = RepairWorkflow(provider=provider, max_patch_attempts=3).run(
        source_path,
        SimulationParameters(data_width=8, depth=3),
        tmp_path,
    )

    assert report.status == "completed"
    assert report.verdict == "no_failure_found_in_tested_cases"
    assert report.attempts == []
    assert provider.investigation_calls == 0
    assert provider.patch_calls == 0
    serialized = report.to_dict()
    assert serialized["schema_version"] == 1
    assert serialized["run_limits"] == {
        "max_patch_attempts": 3,
        "simulation_timeout_seconds": 30,
    }
    assert serialized["claim"] == "No failure found in tested cases."
    assert serialized["integrity"]["locked_assets_unchanged"] is True
    assert serialized["baseline_summary"]["status"] == "passed"
    assert serialized["baseline"]["trace_path"] == "trace.vcd"
    assert str(tmp_path) not in str(serialized)


def test_reproduced_bug_is_patched_and_independently_retested(tmp_path: Path) -> None:
    source_path = ROOT / "benchmark/designs/buggy/simultaneous_count.sv"
    provider = FakeProvider(source_path.read_text(encoding="utf-8"))

    report = RepairWorkflow(provider=provider, max_patch_attempts=3).run(
        source_path,
        SimulationParameters(data_width=8, depth=3),
        tmp_path,
    )

    assert report.status == "completed"
    assert report.verdict == "candidate_passed_listed_tests"
    assert len(report.attempts) == 1
    assert report.attempts[0].reproducer_status == "passed"
    assert report.attempts[0].regression_status == "passed"
    assert report.locked_hashes_before == report.locked_hashes_after
    assert provider.investigation_calls == 1
    assert provider.patch_calls == 1
    serialized = report.to_dict()
    attempt = serialized["attempts"][0]
    assert attempt["investigation"]["evidence_cycles"] == [6]
    assert attempt["investigation"]["transactions"] == [
        {"rst": True, "wr_en": False, "rd_en": False, "din": 0},
        {"rst": False, "wr_en": True, "rd_en": False, "din": 1},
        {"rst": False, "wr_en": True, "rd_en": False, "din": 2},
        {"rst": False, "wr_en": True, "rd_en": True, "din": 3},
    ]
    assert attempt["investigation"]["outcome"]["status"] == "functional_mismatch"
    assert attempt["investigation"]["provider_request"]["request_id"] == "investigate-1"
    assert attempt["candidate"]["source_sha256"]
    assert attempt["candidate"]["rejection_reason"] is None
    assert attempt["verification"]["reproducer"]["status"] == "passed"
    assert attempt["verification"]["regression"]["status"] == "passed"
    assert serialized["claim"] == "Candidate passed the reproducer and listed locked regression tests."


def test_rejected_patch_keeps_investigation_evidence_without_a_candidate_claim(tmp_path: Path) -> None:
    source_path = ROOT / "benchmark/designs/buggy/simultaneous_count.sv"
    provider = RejectingPatchProvider(source_path.read_text(encoding="utf-8"))
    parameters = SimulationParameters(data_width=8, depth=3)

    report = RepairWorkflow(
        provider=provider,
        max_patch_attempts=1,
        simulation_runner=lambda *_args: mismatch(parameters),
    ).run(source_path, parameters, tmp_path)

    attempt = report.to_dict()["attempts"][0]
    assert attempt["investigation"]["outcome"]["status"] == "functional_mismatch"
    assert attempt["candidate"]["source_sha256"] is None
    assert "dut.sv" in attempt["candidate"]["rejection_reason"]
    assert attempt["verification"] is None
    assert report.claim == "Failure reproduced; repair not verified."


def test_failed_locked_regression_cannot_produce_a_success_claim(tmp_path: Path) -> None:
    source_path = ROOT / "benchmark/designs/buggy/simultaneous_count.sv"
    provider = FakeProvider(source_path.read_text(encoding="utf-8"))
    parameters = SimulationParameters(data_width=8, depth=3)
    outcomes = iter([mismatch(parameters), mismatch(parameters), passed(parameters), mismatch(parameters)])

    report = RepairWorkflow(
        provider=provider,
        max_patch_attempts=1,
        simulation_runner=lambda *_args: next(outcomes),
    ).run(source_path, parameters, tmp_path)

    attempt = report.to_dict()["attempts"][0]
    assert attempt["verification"]["reproducer"]["status"] == "passed"
    assert attempt["verification"]["regression"]["status"] == "functional_mismatch"
    assert report.verdict == "repair_not_verified"
    assert report.claim == "Failure reproduced; repair not verified."


def test_provider_failure_preserves_completed_investigation(tmp_path: Path) -> None:
    source_path = ROOT / "benchmark/designs/buggy/simultaneous_count.sv"
    provider = FailingPatchProvider(source_path.read_text(encoding="utf-8"))
    parameters = SimulationParameters(data_width=8, depth=3)

    report = RepairWorkflow(
        provider=provider,
        max_patch_attempts=1,
        simulation_runner=lambda *_args: mismatch(parameters),
    ).run(source_path, parameters, tmp_path)

    attempt = report.to_dict()["attempts"][0]
    assert attempt["investigation"]["outcome"]["status"] == "functional_mismatch"
    assert attempt["candidate"] is None
    assert attempt["verification"] is None
    assert attempt["error"] == "provider unavailable"
    assert report.status == "infrastructure_error"
    assert report.claim == "Failure reproduced; repair not verified."


def test_later_attempt_preserves_non_reproducing_investigation(tmp_path: Path) -> None:
    source_path = ROOT / "benchmark/designs/buggy/simultaneous_count.sv"
    provider = FakeProvider(source_path.read_text(encoding="utf-8"))
    parameters = SimulationParameters(data_width=8, depth=3)
    outcomes = iter(
        [mismatch(parameters), passed(parameters), mismatch(parameters), passed(parameters), passed(parameters)]
    )

    report = RepairWorkflow(
        provider=provider,
        max_patch_attempts=2,
        simulation_runner=lambda *_args: next(outcomes),
    ).run(source_path, parameters, tmp_path)

    attempts = report.to_dict()["attempts"]
    assert len(attempts) == 2
    assert attempts[0]["investigation"]["outcome"]["status"] == "passed"
    assert attempts[0]["candidate"] is None
    assert attempts[1]["verification"]["regression"]["status"] == "passed"
    assert report.verdict == "candidate_passed_listed_tests"


def test_cancellation_keeps_prior_attempt_evidence(tmp_path: Path) -> None:
    source_path = ROOT / "benchmark/designs/buggy/simultaneous_count.sv"
    provider = FakeProvider(source_path.read_text(encoding="utf-8"))
    parameters = SimulationParameters(data_width=8, depth=3)
    cancellation_checks = iter([False, False, True])
    outcomes = iter([mismatch(parameters), passed(parameters)])

    report = RepairWorkflow(
        provider=provider,
        max_patch_attempts=2,
        is_cancelled=lambda: next(cancellation_checks),
        simulation_runner=lambda *_args: next(outcomes),
    ).run(source_path, parameters, tmp_path)

    attempts = report.to_dict()["attempts"]
    assert report.status == "cancelled"
    assert len(attempts) == 1
    assert attempts[0]["investigation"]["outcome"]["status"] == "passed"
    assert report.claim == "Failure reproduced; repair not verified."


def test_correct_arbiter_uses_its_contract_without_a_model_call(tmp_path: Path) -> None:
    source_path = ROOT / "benchmark/designs/arbiter/correct/reference_arbiter.sv"
    provider = FakeProvider(source_path.read_text(encoding="utf-8"))

    report = RepairWorkflow(provider=provider).run(
        source_path,
        SimulationParameters(contract_id="arbiter", requesters=3),
        tmp_path,
    )

    assert report.status == "completed"
    assert report.parameters.contract_id == "arbiter"
    assert report.verdict == "no_failure_found_in_tested_cases"
    assert "round-robin arbiter" in report.limitations[1]
    assert provider.investigation_calls == 0

