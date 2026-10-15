from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import create_app


class StubManager:
    def __init__(self, artifact: Path) -> None:
        self.artifact = artifact
        self.cancelled: list[str] = []
        self.submitted: list[object] = []

    def submit(self, request: object, idempotency_key: str | None) -> str:
        assert idempotency_key == "intent-1"
        self.submitted.append(request)
        return "run-1"

    def get_run(self, run_id: str) -> dict[str, object]:
        if run_id != "run-1":
            raise KeyError(run_id)
        return {
            "id": run_id,
            "status": "completed",
            "verdict": "no_failure_found_in_tested_cases",
            "events": [{"sequence": 1, "state": "completed", "message": "Done"}],
        }

    def cancel(self, run_id: str) -> None:
        if run_id != "run-1":
            raise KeyError(run_id)
        self.cancelled.append(run_id)

    def examples(self) -> list[dict[str, object]]:
        return [{"id": "case-005", "dataWidth": 8, "depth": 3}]

    def list_artifacts(self, run_id: str) -> list[dict[str, object]]:
        return [{"name": self.artifact.name, "size": self.artifact.stat().st_size}]

    def artifact_path(self, run_id: str, name: str) -> Path:
        if run_id != "run-1" or name != self.artifact.name:
            raise KeyError(name)
        return self.artifact


def test_run_api_contract_and_security_headers(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    client = TestClient(create_app(StubManager(artifact)))

    response = client.post(
        "/api/runs",
        headers={"Idempotency-Key": "intent-1"},
        json={"exampleId": "case-005", "dataWidth": 8, "depth": 3},
    )

    assert response.status_code == 202
    assert response.json() == {"id": "run-1", "status": "queued"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/runs/run-1").json()["verdict"] == "no_failure_found_in_tested_cases"
    assert client.get("/api/examples").json()[0]["id"] == "case-005"


def test_create_run_requires_exactly_one_source(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    client = TestClient(create_app(StubManager(artifact)))

    response = client.post(
        "/api/runs",
        headers={"Idempotency-Key": "intent-1"},
        json={"exampleId": "case-005", "source": "module fifo; endmodule", "dataWidth": 8, "depth": 3},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_run_api_accepts_round_robin_arbiter_parameters(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    manager = StubManager(artifact)
    client = TestClient(create_app(manager))

    response = client.post(
        "/api/runs",
        headers={"Idempotency-Key": "intent-1"},
        json={"exampleId": "arbiter-case-003", "contractId": "arbiter", "requesters": 3},
    )

    assert response.status_code == 202
    request = manager.submitted[0]
    assert request.contract_id == "arbiter"
    assert request.requesters == 3


def test_cancel_and_artifact_download(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text('{"status":"completed"}', encoding="utf-8")
    manager = StubManager(artifact)
    client = TestClient(create_app(manager))

    assert client.post("/api/runs/run-1/cancel").status_code == 202
    assert manager.cancelled == ["run-1"]
    assert client.get("/api/runs/run-1/artifacts").json()[0]["name"] == "report.json"
    assert client.get("/api/runs/run-1/artifacts/report.json").text == '{"status":"completed"}'


def test_terminal_run_events_are_streamed_as_sse(tmp_path: Path) -> None:
    artifact = tmp_path / "report.json"
    artifact.write_text("{}", encoding="utf-8")
    client = TestClient(create_app(StubManager(artifact)))

    response = client.get("/api/runs/run-1/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: run_event" in response.text
    assert 'data: {"sequence": 1, "state": "completed", "message": "Done"}' in response.text
    assert "event: done" in response.text

