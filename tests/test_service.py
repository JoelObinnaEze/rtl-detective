from pathlib import Path
from threading import Event
import time
from types import SimpleNamespace

import pytest

from backend.api import CreateRunRequest
from backend.agent.workflow import RunEvent
from backend.service import RunManager


ROOT = Path(__file__).parents[1]


def test_examples_expose_opaque_ids_without_hidden_labels(tmp_path: Path) -> None:
    manager = RunManager(tmp_path)

    examples = manager.examples()

    assert len(examples) == 6
    assert examples[0]["id"].startswith("case-")
    assert all("expected" not in item and "source" not in item for item in examples)
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

