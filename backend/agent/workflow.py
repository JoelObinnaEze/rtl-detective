from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Callable, Protocol

from backend.providers.nebius import InvestigationAction, ModelReply, PatchAction, ProviderError
from backend.verification.packs import ContractPack, get_contract_pack
from backend.verification.runner import (
    SimulationOutcome,
    SimulationParameters,
    outcome_to_dict,
    run_local_simulation,
)
from backend.verification.security import PatchRejected, apply_candidate_patch, hash_locked_assets, validate_source


class Provider(Protocol):
    def verify_model(self) -> None: ...
    def investigate(self, evidence: str) -> ModelReply[InvestigationAction]: ...
    def propose_patch(self, source_and_evidence: str) -> ModelReply[PatchAction]: ...


@dataclass(frozen=True)
class RunEvent:
    state: str
    message: str


@dataclass(frozen=True)
class AttemptReport:
    attempt: int
    hypothesis: str
    diagnosis: str | None
    diff: str | None
    investigation_status: str
    reproducer_status: str | None
    regression_status: str | None
    provider_requests: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowReport:
    status: str
    verdict: str
    source_hash: str
    parameters: SimulationParameters
    baseline: SimulationOutcome
    attempts: list[AttemptReport]
    events: list[RunEvent]
    locked_hashes_before: dict[str, str]
    locked_hashes_after: dict[str, str]
    final_candidate: Path | None
    limitations: list[str]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["baseline"] = outcome_to_dict(self.baseline)
        data["final_candidate"] = str(self.final_candidate) if self.final_candidate else None
        return data


def _provider_record(reply: ModelReply[object]) -> dict[str, object]:
    return {
        "provider": reply.provider,
        "model_id": reply.model_id,
        "latency_ms": reply.latency_ms,
        "usage": reply.usage,
        "request_id": reply.request_id,
    }


def _evidence(source: str, outcome: SimulationOutcome, pack: ContractPack, note: str = "") -> str:
    failure = outcome.failures[0] if outcome.failures else None
    return "\n".join(
        [
            pack.summary,
            f"Parameters: {pack.parameter_summary(outcome.parameters)}",
            f"Simulation status: {outcome.status}",
            f"Failure: {asdict(failure) if failure else 'none'}",
            f"Additional result: {note}",
            "Untrusted DUT source follows:",
            source[:24_000],
        ]
    )


class RepairWorkflow:
    def __init__(
        self,
        provider: Provider,
        max_patch_attempts: int = 3,
        simulation_timeout_seconds: int = 30,
        on_event: Callable[[RunEvent], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
        simulation_runner: Callable[
            [Path, list[object], SimulationParameters, Path, int], SimulationOutcome
        ] = run_local_simulation,
    ) -> None:
        if not 1 <= max_patch_attempts <= 3:
            raise ValueError("max_patch_attempts must be between 1 and 3")
        self.provider = provider
        self.max_patch_attempts = max_patch_attempts
        self.simulation_timeout_seconds = simulation_timeout_seconds
        self.on_event = on_event
        self.is_cancelled = is_cancelled or (lambda: False)
        self.simulation_runner = simulation_runner

    def run(self, source_path: Path, parameters: SimulationParameters, workspace: Path) -> WorkflowReport:
        workspace.mkdir(parents=True, exist_ok=True)
        source = source_path.read_text(encoding="utf-8")
        pack = get_contract_pack(parameters.contract_id)
        validate_source(source, pack.id)
        original = workspace / "original.sv"
        original.write_text(source, encoding="utf-8")
        source_hash = sha256(original.read_bytes()).hexdigest()
        project_root = Path(__file__).parents[2]
        locked_before = hash_locked_assets(project_root)
        events: list[RunEvent] = []

        def emit(state: str, message: str) -> None:
            event = RunEvent(state, message)
            events.append(event)
            if self.on_event:
                self.on_event(event)

        emit("validating", f"Source and {pack.name} interface validated")
        if self.is_cancelled():
            return self._finish("cancelled", "cancelled", source_hash, parameters, self._empty(parameters), [], events, locked_before, None)

        transactions = pack.regression_transactions(parameters)
        emit("baseline", "Running locked directed and seeded randomized tests")
        baseline = self.simulation_runner(
            original,
            transactions,
            parameters,
            workspace / "baseline",
            self.simulation_timeout_seconds,
        )
        if baseline.status == "passed":
            emit("completed", "No failure found in the listed tests; no patch requested")
            return self._finish(
                "completed",
                "no_failure_found_in_tested_cases",
                source_hash,
                parameters,
                baseline,
                [],
                events,
                locked_before,
                None,
            )
        if baseline.status == "compile_failure":
            emit("invalid_input", "The DUT did not compile")
            return self._finish("invalid_input", "compile_error", source_hash, parameters, baseline, [], events, locked_before, None)
        if baseline.status != "functional_mismatch":
            emit("infrastructure_error", f"Baseline ended with {baseline.status}")
            return self._finish(
                "infrastructure_error", baseline.status, source_hash, parameters, baseline, [], events, locked_before, None
            )

        attempts: list[AttemptReport] = []
        feedback = ""
        try:
            self.provider.verify_model()
            for number in range(1, self.max_patch_attempts + 1):
                if self.is_cancelled():
                    emit("cancelled", "Run cancelled before the next model call")
                    return self._finish("cancelled", "cancelled", source_hash, parameters, baseline, attempts, events, locked_before, None)

                emit("investigating", f"Requesting bounded investigation {number}")
                investigation = self.provider.investigate(_evidence(source, baseline, pack, feedback))
                targeted = [pack.transaction_from_action(item) for item in investigation.value.transactions]
                investigation_outcome = self.simulation_runner(
                    original,
                    targeted,
                    parameters,
                    workspace / f"attempt-{number}" / "investigation",
                    self.simulation_timeout_seconds,
                )
                records = [_provider_record(investigation)]
                if investigation_outcome.status != "functional_mismatch":
                    attempts.append(
                        AttemptReport(
                            number,
                            investigation.value.hypothesis,
                            None,
                            None,
                            investigation_outcome.status,
                            None,
                            None,
                            records,
                        )
                    )
                    feedback = "The proposed investigation did not reproduce a mismatch."
                    continue

                emit("patching", f"Failure reproduced; requesting candidate patch {number}")
                patch_reply = self.provider.propose_patch(
                    _evidence(source, investigation_outcome, pack, investigation.value.hypothesis)
                )
                records.append(_provider_record(patch_reply))
                candidate_dir = workspace / f"attempt-{number}" / "candidate"
                try:
                    candidate = apply_candidate_patch(original, patch_reply.value.diff, candidate_dir, pack.id)
                except PatchRejected as error:
                    attempts.append(
                        AttemptReport(
                            number,
                            investigation.value.hypothesis,
                            patch_reply.value.diagnosis,
                            patch_reply.value.diff,
                            investigation_outcome.status,
                            "patch_rejected",
                            None,
                            records,
                        )
                    )
                    feedback = str(error)
                    continue

                emit("regression", f"Evaluating candidate {number} against reproducer and locked tests")
                reproducer = self.simulation_runner(
                    candidate,
                    targeted,
                    parameters,
                    workspace / f"attempt-{number}" / "reproducer",
                    self.simulation_timeout_seconds,
                )
                regression = self.simulation_runner(
                    candidate,
                    transactions,
                    parameters,
                    workspace / f"attempt-{number}" / "regression",
                    self.simulation_timeout_seconds,
                )
                attempts.append(
                    AttemptReport(
                        number,
                        investigation.value.hypothesis,
                        patch_reply.value.diagnosis,
                        patch_reply.value.diff,
                        investigation_outcome.status,
                        reproducer.status,
                        regression.status,
                        records,
                    )
                )
                if reproducer.status == regression.status == "passed":
                    emit("completed", "Candidate passed the reproducer and listed locked regression tests")
                    return self._finish(
                        "completed",
                        "candidate_passed_listed_tests",
                        source_hash,
                        parameters,
                        baseline,
                        attempts,
                        events,
                        locked_before,
                        candidate,
                    )
                feedback = f"Candidate results: reproducer={reproducer.status}, regression={regression.status}."
        except ProviderError as error:
            emit("infrastructure_error", f"Provider error: {error}")
            return self._finish(
                "infrastructure_error", "provider_error", source_hash, parameters, baseline, attempts, events, locked_before, None
            )

        emit("unresolved", "No candidate passed before the attempt limit")
        return self._finish("unresolved", "repair_not_verified", source_hash, parameters, baseline, attempts, events, locked_before, None)

    @staticmethod
    def _empty(parameters: SimulationParameters) -> SimulationOutcome:
        return SimulationOutcome("cancelled", parameters, [], [], "", "", None, None)

    @staticmethod
    def _finish(
        status: str,
        verdict: str,
        source_hash: str,
        parameters: SimulationParameters,
        baseline: SimulationOutcome,
        attempts: list[AttemptReport],
        events: list[RunEvent],
        locked_before: dict[str, str],
        candidate: Path | None,
    ) -> WorkflowReport:
        project_root = Path(__file__).parents[2]
        locked_after = hash_locked_assets(project_root)
        if locked_after != locked_before:
            status, verdict, candidate = "infrastructure_error", "locked_assets_changed", None
        return WorkflowReport(
            status=status,
            verdict=verdict,
            source_hash=source_hash,
            parameters=parameters,
            baseline=baseline,
            attempts=attempts,
            events=events,
            locked_hashes_before=locked_before,
            locked_hashes_after=locked_after,
            final_candidate=candidate,
            limitations=[
                "Simulation demonstrates only the listed configurations and seeds; it is not a formal proof.",
                get_contract_pack(parameters.contract_id).limitation,
            ],
        )

