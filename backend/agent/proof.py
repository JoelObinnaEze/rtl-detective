from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

from backend.verification.runner import SimulationOutcome


@dataclass(frozen=True)
class RunLimits:
    max_patch_attempts: int
    simulation_timeout_seconds: int


@dataclass(frozen=True)
class IntegrityProof:
    source_sha256: str
    locked_assets_before: dict[str, str]
    locked_assets_after: dict[str, str]
    locked_assets_unchanged: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "locked_assets_unchanged", self.locked_assets_before == self.locked_assets_after)


@dataclass(frozen=True)
class OutcomeSummary:
    status: str
    transaction_count: int
    first_failure: dict[str, object] | None
    simulator_version: str | None
    trace_artifact: str | None


def _artifact_reference(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
        raise ValueError("artifact references must be relative paths")
    return path.as_posix()


def summarize_outcome(
    outcome: SimulationOutcome,
    transaction_count: int,
    trace_artifact: str | None,
) -> OutcomeSummary:
    first_failure = asdict(outcome.failures[0]) if outcome.failures else None
    return OutcomeSummary(
        status=outcome.status,
        transaction_count=transaction_count,
        first_failure=first_failure,
        simulator_version=outcome.simulator_version,
        trace_artifact=_artifact_reference(trace_artifact),
    )


def derive_claim(
    verdict: str,
    *,
    baseline_status: str,
    reproducer_status: str | None,
    regression_status: str | None,
    locked_assets_unchanged: bool,
) -> str:
    if verdict == "candidate_passed_listed_tests":
        if (
            reproducer_status == "passed"
            and regression_status == "passed"
            and locked_assets_unchanged
        ):
            return "Candidate passed the reproducer and listed locked regression tests."
    elif verdict == "no_failure_found_in_tested_cases" and baseline_status == "passed":
        return "No failure found in tested cases."
    if baseline_status == "functional_mismatch":
        return "Failure reproduced; repair not verified."
    return "Repair not verified."
