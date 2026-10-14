from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import zipfile

from backend.agent.workflow import RepairWorkflow, RunEvent, WorkflowReport
from backend.api import CreateRunRequest, TERMINAL_STATES
from backend.providers.nebius import NebiusProvider, ProviderError
from backend.storage import RunStore
from backend.verification.runner import (
    SimulationParameters,
    docker_available,
    run_container_simulation,
    run_local_simulation,
)
from backend.verification.security import validate_source
from backend.verification.trace import extract_signal_changes


class _UnavailableProvider:
    def verify_model(self) -> None:
        raise ProviderError("NEBIUS_API_KEY and NEBIUS_MODEL_ID are required for repair after a reproduced failure")

    def investigate(self, evidence: str):
        self.verify_model()

    def propose_patch(self, source_and_evidence: str):
        self.verify_model()


class RunManager:
    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root.resolve()
        self.runs_root = self.data_root / "runs"
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.store = RunStore(self.data_root / "runs.db")
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rtl-detective-worker")
        project_root = Path(__file__).parents[1]
        manifest_path = project_root / "benchmark/manifests/cases.json"
        self.benchmark_root = project_root / "benchmark"
        self._examples = json.loads(manifest_path.read_text(encoding="utf-8"))

    def examples(self) -> list[dict[str, object]]:
        return [
            {"id": item["id"], "dataWidth": item["data_width"], "depth": item["depth"]}
            for item in self._examples
        ]

    def submit(self, request: CreateRunRequest, idempotency_key: str | None) -> str:
        if request.example_id:
            item = next((entry for entry in self._examples if entry["id"] == request.example_id), None)
            if item is None:
                raise ValueError("unknown exampleId")
            source = (self.benchmark_root / item["source"]).read_text(encoding="utf-8")
            source_kind = "example"
        else:
            if not docker_available():
                raise RuntimeError("uploaded RTL requires the isolated Docker worker, which is unavailable")
            source = request.source or ""
            source_kind = "upload"
        validate_source(source)

        parameters = {"data_width": request.data_width, "depth": request.depth}
        request_hash = sha256(
            json.dumps(request.model_dump(by_alias=True), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        run_id = self.store.create_run(
            parameters,
            provider_mode="live",
            source_kind=source_kind,
            idempotency_key=idempotency_key,
            request_hash=request_hash if idempotency_key else None,
        )
        run_root = self.runs_root / run_id
        if run_root.exists():
            return run_id
        run_root.mkdir()
        source_path = run_root / "original.sv"
        source_path.write_text(source, encoding="utf-8")
        self.store.append_event(run_id, "queued", "Run accepted by the single-worker queue")
        self.executor.submit(self._execute, run_id, source_path, source_kind, request.data_width, request.depth)
        return run_id

    def _provider(self):
        if os.getenv("NEBIUS_API_KEY") and os.getenv("NEBIUS_MODEL_ID"):
            return NebiusProvider.from_env()
        return _UnavailableProvider()

    def _execute(self, run_id: str, source: Path, source_kind: str, data_width: int, depth: int) -> None:
        run_root = self.runs_root / run_id

        def on_event(event: RunEvent) -> None:
            self.store.append_event(run_id, event.state, event.message)
            if event.state not in TERMINAL_STATES:
                self.store.update_run(run_id, event.state)

        try:
            simulation_runner = run_container_simulation if source_kind == "upload" or docker_available() else run_local_simulation
            workflow = RepairWorkflow(
                provider=self._provider(),
                max_patch_attempts=int(os.getenv("MAX_PATCH_ATTEMPTS", "3")),
                simulation_timeout_seconds=int(os.getenv("SIMULATION_TIMEOUT_SECONDS", "30")),
                on_event=on_event,
                is_cancelled=lambda: self.store.is_cancelled(run_id),
                simulation_runner=simulation_runner,
            )
            report = workflow.run(
                source,
                SimulationParameters(data_width=data_width, depth=depth),
                run_root / "work",
            )
            self._write_artifacts(run_root, report)
            self.store.update_run(run_id, report.status, report.verdict)
        except Exception:
            self.store.append_event(run_id, "infrastructure_error", "Run failed inside the orchestrator")
            self.store.update_run(run_id, "infrastructure_error", "infrastructure_error")

    @staticmethod
    def _write_artifacts(run_root: Path, report: WorkflowReport) -> None:
        report_json = run_root / "report.json"
        report_json.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")
        first_failure = report.baseline.failures[0] if report.baseline.failures else None
        lines = [
            "# RTL Detective report",
            "",
            f"- Status: `{report.status}`",
            f"- Verdict: `{report.verdict}`",
            f"- Source SHA-256: `{report.source_hash}`",
            f"- Parameters: DATA_WIDTH={report.parameters.data_width}, DEPTH={report.parameters.depth}",
            f"- Simulator: {report.baseline.simulator_version or 'unavailable'}",
            "",
            "## Evidence",
            "",
            json.dumps(first_failure.expected if first_failure else "No mismatch", indent=2),
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in report.limitations],
        ]
        (run_root / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        if report.final_candidate:
            shutil.copyfile(report.final_candidate, run_root / "candidate.sv")
        if report.baseline.trace_path and report.baseline.trace_path.exists():
            trace = run_root / "trace.vcd"
            shutil.copyfile(report.baseline.trace_path, trace)
            (run_root / "trace-changes.json").write_text(
                json.dumps(extract_signal_changes(trace), indent=2), encoding="utf-8"
            )

        bundle = run_root / "artifact-bundle.zip"
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in run_root.rglob("*"):
                if not path.is_file() or path == bundle or "obj_dir" in path.parts:
                    continue
                if path.suffix.lower() in {".exe", ".o", ".d", ".cpp", ".h"}:
                    continue
                archive.write(path, path.relative_to(run_root))

    def get_run(self, run_id: str) -> dict[str, object]:
        return self.store.get_run(run_id)

    def cancel(self, run_id: str) -> None:
        self.store.request_cancel(run_id)
        self.store.append_event(run_id, "cancellation_requested", "Cancellation requested")

    def list_artifacts(self, run_id: str) -> list[dict[str, object]]:
        self.store.get_run(run_id)
        run_root = self.runs_root / run_id
        if not run_root.exists():
            return []
        return [
            {"name": path.name, "size": path.stat().st_size}
            for path in sorted(run_root.iterdir())
            if path.is_file()
        ]

    def artifact_path(self, run_id: str, name: str) -> Path:
        self.store.get_run(run_id)
        if not name or Path(name).name != name:
            raise KeyError(name)
        run_root = (self.runs_root / run_id).resolve()
        path = (run_root / name).resolve()
        if path.parent != run_root or not path.is_file():
            raise KeyError(name)
        return path

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)

