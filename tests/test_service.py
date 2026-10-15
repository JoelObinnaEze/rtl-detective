import json
import time
import zipfile
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from backend.agent.workflow import RunEvent
from backend.api import CreateRunRequest
from backend.providers.nebius import DEFAULT_MODEL_ID, NebiusProvider
from backend.service import RunManager
from backend.verification.runner import SimulationParameters

ROOT = Path(__file__).parents[1]


def test_provider_is_ready_with_key_and_verified_default_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.delenv("NEBIUS_MODEL_ID", raising=False)
    manager = RunManager(tmp_path)

    provider = manager._provider()
    try:
        assert isinstance(provider, NebiusProvider)
        assert provider.model_id == DEFAULT_MODEL_ID
    finally:
        provider.client.close()
        manager.shutdown()


def test_examples_expose_opaque_ids_without_hidden_labels(tmp_path: Path) -> None:
    manager = RunManager(tmp_path)

    examples = manager.examples()

    assert len(examples) == 10
    assert examples[0]["id"].startswith("case-")
    assert all("expected" not in item and "source" not in item for item in examples)
    assert {item["contractId"] for item in examples} == {"fifo", "arbiter"}
    assert any(item.get("requesters") == 3 for item in examples if item["contractId"] == "arbiter")
    manager.shutdown()


def test_uploaded_rtl_fails_closed_when_container_worker_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("backend.service.docker_available", lambda: False)
    manager = RunManager(tmp_path)
    source = (ROOT / "benchmark/designs/correct/reference_fifo.sv").read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="isolated Docker worker"):
        manager.submit(CreateRunRequest(source=source, dataWidth=8, depth=3), None)
    manager.shutdown()


def test_uploaded_rtl_is_validated_before_worker_availability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("backend.service.docker_available", lambda: False)
    manager = RunManager(tmp_path)

    with pytest.raises(ValueError, match="module fifo"):
        manager.submit(CreateRunRequest(source="not SystemVerilog"), None)
    manager.shutdown()


@pytest.mark.parametrize(
    ("run_request", "expected_parameters"),
    [
        (CreateRunRequest(exampleId="case-002"), {"contract_id": "fifo", "data_width": 8, "depth": 3}),
        (
            CreateRunRequest(exampleId="arbiter-case-004"),
            {"contract_id": "arbiter", "requesters": 5},
        ),
    ],
)
def test_bundled_examples_use_manifest_parameters_when_not_overridden(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    run_request: CreateRunRequest,
    expected_parameters: dict[str, int | str],
) -> None:
    manager = RunManager(tmp_path)
    monkeypatch.setattr(manager, "_execute", lambda *_args: None)

    run_id = manager.submit(run_request, None)

    assert manager.get_run(run_id)["parameters"] == expected_parameters
    manager.shutdown()


def test_artifact_lookup_rejects_path_traversal(tmp_path: Path) -> None:
    manager = RunManager(tmp_path)

    with pytest.raises(KeyError):
        manager.artifact_path("missing", "../runs.db")
    manager.shutdown()


def test_terminal_status_is_not_visible_before_the_final_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_write_started = Event()
    release_artifact_write = Event()

    class FakeWorkflow:
        def __init__(self, **kwargs: object) -> None:
            self.on_event = kwargs["on_event"]

        def run(self, *_args: object) -> SimpleNamespace:
            self.on_event(RunEvent("validating", "Validated"))
            self.on_event(RunEvent("completed", "Done"))
            return SimpleNamespace(status="completed", verdict="no_failure_found_in_tested_cases")

    def block_artifact_write(*_args: object) -> None:
        artifact_write_started.set()
        assert release_artifact_write.wait(5)

    monkeypatch.setattr("backend.service.RepairWorkflow", FakeWorkflow)
    monkeypatch.setattr(RunManager, "_write_artifacts", staticmethod(block_artifact_write))
    manager = RunManager(tmp_path)
    try:
        run_id = manager.submit(CreateRunRequest(exampleId="case-005", dataWidth=8, depth=3), None)
        assert artifact_write_started.wait(5)

        pending = manager.get_run(run_id)
        assert pending["status"] == "validating"
        assert pending["verdict"] is None

        release_artifact_write.set()
        deadline = time.monotonic() + 5
        while manager.get_run(run_id)["verdict"] is None and time.monotonic() < deadline:
            time.sleep(0.01)
        final = manager.get_run(run_id)
        assert final["status"] == "completed"
        assert final["verdict"] == "no_failure_found_in_tested_cases"
    finally:
        release_artifact_write.set()
        manager.shutdown()


def test_json_markdown_and_zip_share_the_same_proof(tmp_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "status": "completed",
        "verdict": "candidate_passed_listed_tests",
        "claim": "Candidate passed the reproducer and listed locked regression tests.",
        "source_hash": "source-hash",
        "parameters": {"contract_id": "fifo", "data_width": 8, "depth": 3},
        "integrity": {"locked_assets_unchanged": True},
        "baseline": {"stdout": "simulation output", "stderr": "compiler warning"},
        "baseline_summary": {"status": "functional_mismatch", "simulator_version": "Verilator 5.050"},
        "attempts": [
            {
                "investigation": {
                    "provider_request": {
                        "provider": "nebius\n- injected",
                        "model_id": "nvidia/model<script>alert(1)</script>",
                        "request_id": "req-1<img src=x>",
                    }
                },
                "candidate": {"source_sha256": "candidate-hash"},
                "verification": {
                    "reproducer": {"status": "passed"},
                    "regression": {"status": "passed"},
                },
            }
        ],
        "limitations": ["Simulation is not formal proof."],
    }
    report = SimpleNamespace(
        to_dict=lambda: payload,
        final_candidate=None,
        baseline=SimpleNamespace(trace_path=None, stdout="simulation output", stderr="compiler warning"),
    )

    RunManager._write_artifacts(tmp_path, report)

    serialized = (tmp_path / "report.json").read_text(encoding="utf-8")
    data = json.loads(serialized)
    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert data["claim"] in markdown
    assert data["verdict"] in markdown
    assert data["source_hash"] in markdown
    assert data["attempts"][0]["candidate"]["source_sha256"] in markdown
    assert data["baseline"]["stdout"] is None
    assert data["baseline"]["stdout_artifact"] == "baseline.stdout.txt"
    assert "simulation output" not in serialized
    assert "`nebius - injected` / `nvidia/model&lt;script&gt;alert(1)&lt;/script&gt;`" in markdown
    assert "\n- injected" not in markdown
    assert "<script>" not in markdown
    assert "<img" not in markdown
    assert "Reproducer: `passed`" in markdown
    assert "Locked regression: `passed`" in markdown
    assert str(tmp_path) not in serialized + markdown
    with zipfile.ZipFile(tmp_path / "artifact-bundle.zip") as archive:
        names = set(archive.namelist())
        assert set(data["artifacts"]) <= names
        assert json.loads(archive.read("report.json")) == data
        assert archive.read("report.md").decode() == markdown


def test_unexpected_orchestrator_failure_writes_sanitized_proof_before_terminal_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingWorkflow:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(self, *_args: object) -> None:
            raise RuntimeError(f"secret-token at {tmp_path}")

    monkeypatch.setattr("backend.service.RepairWorkflow", FailingWorkflow)
    monkeypatch.setattr("backend.service.docker_available", lambda: False)
    manager = RunManager(tmp_path)
    parameters = SimulationParameters(data_width=8, depth=3)
    run_id = manager.store.create_run(
        {"contract_id": "fifo", "data_width": 8, "depth": 3},
        provider_mode="live",
        source_kind="example",
    )
    run_root = manager.runs_root / run_id
    run_root.mkdir()
    source = run_root / "original.sv"
    source.write_text(
        (ROOT / "benchmark/designs/correct/reference_fifo.sv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    manager._execute(run_id, source, "example", parameters)

    data = json.loads((run_root / "report.json").read_text(encoding="utf-8"))
    serialized = json.dumps(data)
    assert manager.get_run(run_id)["status"] == "infrastructure_error"
    assert data["schema_version"] == 1
    assert data["status"] == "infrastructure_error"
    assert data["claim"] == "Repair not verified."
    assert data["run_limits"]["max_patch_attempts"] == 1
    assert data["integrity"]["source_sha256"]
    assert data["integrity"]["locked_assets_unchanged"] is False
    assert data["error"] == {"code": "ORCHESTRATOR_FAILURE", "message": "Run failed inside the orchestrator"}
    assert "secret-token" not in serialized
    assert str(tmp_path) not in serialized
    assert (run_root / "report.md").is_file()
    assert (run_root / "artifact-bundle.zip").is_file()
    manager.shutdown()

