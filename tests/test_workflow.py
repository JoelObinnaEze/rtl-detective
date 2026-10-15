from dataclasses import dataclass
import difflib
from pathlib import Path

from backend.agent.workflow import RepairWorkflow
from backend.providers.nebius import (
    InvestigationAction,
    ModelReply,
    PatchAction,
    TransactionAction,
)
from backend.verification.runner import SimulationParameters


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

