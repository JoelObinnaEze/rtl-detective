from pathlib import Path

import pytest

from backend.api import CreateRunRequest
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

