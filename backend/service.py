from __future__ import annotations

import json
import logging
import os
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from hashlib import sha256
from html import escape
from pathlib import Path
from threading import BoundedSemaphore, Lock

from backend.agent.proof import RunLimits
from backend.agent.workflow import RepairWorkflow, RunEvent, WorkflowReport
from backend.api import TERMINAL_STATES, CreateRunRequest
from backend.providers.nebius import DEFAULT_MODEL_ID, NebiusProvider, ProviderError
from backend.storage import RunStore
from backend.verification.runner import (
    SimulationParameters,
    docker_available,
    run_container_simulation,
    run_local_simulation,
)
from backend.verification.security import hash_locked_assets, validate_source
from backend.verification.trace import extract_signal_changes

logger = logging.getLogger(__name__)


class _UnavailableProvider:
    def verify_model(self) -> None:
        raise ProviderError("NEBIUS_API_KEY is required for repair after a reproduced failure")

    def investigate(self, evidence: str):
        self.verify_model()

    def propose_patch(self, source_and_evidence: str):
        self.verify_model()


def _markdown_code(value: object) -> str:
    text = " ".join(str(value if value is not None else "unavailable").splitlines())
    return f"`{escape(text).replace('`', '&#96;')}`"


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


class RunManager:
    def __init__(self, data_root: Path) -> None:
        self.limits = RunLimits(
            max_patch_attempts=_bounded_env_int("MAX_PATCH_ATTEMPTS", 1, 1, 3),
            simulation_timeout_seconds=_bounded_env_int("SIMULATION_TIMEOUT_SECONDS", 30, 1, 300),
        )
        self.max_pending_runs = _bounded_env_int("MAX_PENDING_RUNS", 4, 1, 32)
        self._run_slots = BoundedSemaphore(self.max_pending_runs)
        self._submission_lock = Lock()
        self.data_root = data_root.resolve()
        self.runs_root = self.data_root / "runs"
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.store = RunStore(self.data_root / "runs.db")
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rtl-detective-worker")
        project_root = Path(__file__).parents[1]
        manifest_path = project_root / "benchmark/manifests/cases.json"
        self.benchmark_root = project_root / "benchmark"
        self._examples = json.loads(manifest_path.read_text(encoding="utf-8"))
        self._recover_incomplete_runs()

    def examples(self) -> list[dict[str, object]]:
        examples = []
        for item in self._examples:
            contract_id = item.get("contract_id", "fifo")
            public = {"id": item["id"], "contractId": contract_id}
            if contract_id == "arbiter":
                public["requesters"] = item["requesters"]
            else:
                public.update({"dataWidth": item["data_width"], "depth": item["depth"]})
            examples.append(public)
        return examples

    def health(self) -> dict[str, object]:
        configured = bool(os.getenv("NEBIUS_API_KEY"))
        return {
            "status": "ok" if configured else "degraded",
            "repairReady": configured,
            "provider": {
                "name": "Nebius Token Factory",
                "configured": configured,
                "modelId": os.getenv("NEBIUS_MODEL_ID") or DEFAULT_MODEL_ID,
            },
            "worker": {
                "uploadsReady": docker_available(),
                "maxPendingRuns": self.max_pending_runs,
            },
        }

    def submit(self, request: CreateRunRequest, idempotency_key: str | None) -> str:
        data_width = request.data_width
        depth = request.depth
        requesters = request.requesters
        if request.example_id is not None:
            item = next((entry for entry in self._examples if entry["id"] == request.example_id), None)
            if item is None:
                raise ValueError("unknown exampleId")
            contract_id = str(item.get("contract_id", "fifo"))
            if "contract_id" in request.model_fields_set and request.contract_id != contract_id:
                raise ValueError("contractId does not match the selected example")
            if contract_id == "arbiter" and "requesters" not in request.model_fields_set:
                requesters = int(item["requesters"])
            elif contract_id == "fifo":
                if "data_width" not in request.model_fields_set:
                    data_width = int(item["data_width"])
                if "depth" not in request.model_fields_set:
                    depth = int(item["depth"])
            source = (self.benchmark_root / item["source"]).read_text(encoding="utf-8")
            source_kind = "example"
        else:
            contract_id = request.contract_id
            source = request.source or ""
            source_kind = "upload"
        parameters = SimulationParameters(
            contract_id=contract_id,
            data_width=data_width,
            depth=depth,
            requesters=requesters,
        )
        validate_source(source, contract_id)
        if source_kind == "upload" and not docker_available():
            raise RuntimeError("uploaded RTL requires the isolated Docker worker, which is unavailable")

        stored_parameters: dict[str, int | str] = {"contract_id": contract_id}
        if contract_id == "arbiter":
            stored_parameters["requesters"] = requesters
        else:
            stored_parameters.update({"data_width": data_width, "depth": depth})
        request_hash = sha256(
            json.dumps(request.model_dump(by_alias=True), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with self._submission_lock:
            if not self._run_slots.acquire(blocking=False):
                raise RuntimeError("run queue is full; retry after an active run completes")
            slot_owned = True
            try:
                run_id = self.store.create_run(
                    stored_parameters,
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
                self.executor.submit(self._execute_queued, run_id, source_path, source_kind, parameters)
                slot_owned = False
                return run_id
            finally:
                if slot_owned:
                    self._run_slots.release()

    def _execute_queued(
        self, run_id: str, source: Path, source_kind: str, parameters: SimulationParameters
    ) -> None:
        try:
            self._execute(run_id, source, source_kind, parameters)
        finally:
            self._run_slots.release()

    def _provider(self):
        if os.getenv("NEBIUS_API_KEY"):
            return NebiusProvider.from_env()
        return _UnavailableProvider()

    def _execute(
        self, run_id: str, source: Path, source_kind: str, parameters: SimulationParameters
    ) -> None:
        run_root = self.runs_root / run_id

        def on_event(event: RunEvent) -> None:
            self.store.append_event(run_id, event.state, event.message)
            if event.state not in TERMINAL_STATES:
                self.store.update_run(run_id, event.state)

        try:
            simulation_runner = run_container_simulation if source_kind == "upload" or docker_available() else run_local_simulation
            workflow = RepairWorkflow(
                provider=self._provider(),
                max_patch_attempts=self.limits.max_patch_attempts,
                simulation_timeout_seconds=self.limits.simulation_timeout_seconds,
                on_event=on_event,
                is_cancelled=lambda: self.store.is_cancelled(run_id),
                simulation_runner=simulation_runner,
            )
            report = workflow.run(
                source,
                parameters,
                run_root / "work",
            )
            self._write_artifacts(run_root, report)
            self.store.update_run(run_id, report.status, report.verdict)
        except Exception:  # Worker boundary must persist a terminal record.
            logger.exception("run %s failed inside the orchestrator", run_id)
            try:
                self._write_failure_artifacts(run_root, source, parameters, self.limits)
            except Exception:  # Status must still become terminal.
                logger.exception("run %s fallback artifact write failed", run_id)
            self.store.append_event(run_id, "infrastructure_error", "Run failed inside the orchestrator")
            self.store.update_run(run_id, "infrastructure_error", "infrastructure_error")

    def _recover_incomplete_runs(self) -> None:
        for record in self.store.list_incomplete_runs(TERMINAL_STATES):
            run_id = str(record["id"])
            run_root = self.runs_root / run_id
            run_root.mkdir(parents=True, exist_ok=True)
            values = record["parameters"]
            assert isinstance(values, dict)
            parameters = SimulationParameters(
                contract_id=str(values.get("contract_id", "fifo")),
                data_width=int(values.get("data_width", 8)),
                depth=int(values.get("depth", 4)),
                requesters=int(values.get("requesters", 4)),
            )
            try:
                self._write_failure_artifacts(
                    run_root,
                    run_root / "original.sv",
                    parameters,
                    self.limits,
                    error_code="RUN_INTERRUPTED",
                    error_message="Service restarted before the run reached a terminal state",
                )
            except Exception:  # Recovery must still unblock polling clients.
                logger.exception("run %s restart recovery artifact write failed", run_id)
            self.store.append_event(
                run_id,
                "infrastructure_error",
                "Run interrupted by a service restart",
            )
            self.store.update_run(run_id, "infrastructure_error", "run_interrupted")

    @staticmethod
    def _write_artifacts(run_root: Path, report: WorkflowReport) -> None:
        if report.final_candidate:
            shutil.copyfile(report.final_candidate, run_root / "candidate.sv")
        if report.baseline.trace_path and report.baseline.trace_path.exists():
            trace = run_root / "trace.vcd"
            shutil.copyfile(report.baseline.trace_path, trace)
            (run_root / "trace-changes.json").write_text(
                json.dumps(extract_signal_changes(trace), indent=2), encoding="utf-8"
            )
        payload = report.to_dict()
        baseline = payload.get("baseline")
        if isinstance(baseline, dict):
            for stream in ("stdout", "stderr"):
                content = getattr(report.baseline, stream)
                artifact = f"baseline.{stream}.txt" if content else None
                if artifact:
                    (run_root / artifact).write_text(content, encoding="utf-8")
                baseline[stream] = None
                baseline[f"{stream}_artifact"] = artifact
        RunManager._write_report_bundle(run_root, payload)

    @staticmethod
    def _write_failure_artifacts(
        run_root: Path,
        source: Path,
        parameters: SimulationParameters,
        limits: RunLimits,
        error_code: str = "ORCHESTRATOR_FAILURE",
        error_message: str = "Run failed inside the orchestrator",
    ) -> None:
        source_hash = sha256(source.read_bytes()).hexdigest() if source.is_file() else None
        locked_after = hash_locked_assets(Path(__file__).parents[1])
        payload: dict[str, object] = {
            "schema_version": 1,
            "status": "infrastructure_error",
            "verdict": "infrastructure_error",
            "claim": "Repair not verified.",
            "source_hash": source_hash,
            "parameters": asdict(parameters),
            "run_limits": asdict(limits),
            "baseline": None,
            "baseline_summary": {
                "status": "not_completed",
                "transaction_count": 0,
                "first_failure": None,
                "simulator_version": None,
                "trace_artifact": None,
            },
            "attempts": [],
            "events": [],
            "integrity": {
                "source_sha256": source_hash,
                "locked_assets_before": {},
                "locked_assets_after": locked_after,
                "locked_assets_unchanged": False,
            },
            "limitations": [f"{error_message}. A complete verification report is unavailable."],
            "error": {
                "code": error_code,
                "message": error_message,
            },
        }
        RunManager._write_report_bundle(run_root, payload)

    @staticmethod
    def _write_report_bundle(run_root: Path, payload: dict[str, object]) -> None:
        artifact_names = [
            name
            for name in (
                "baseline.stderr.txt",
                "baseline.stdout.txt",
                "candidate.sv",
                "original.sv",
                "report.json",
                "report.md",
                "trace-changes.json",
                "trace.vcd",
            )
            if name in {"report.json", "report.md"} or (run_root / name).is_file()
        ]
        payload["artifacts"] = artifact_names
        (run_root / "report.json").write_bytes(json.dumps(payload, indent=2).encode())
        (run_root / "report.md").write_bytes(RunManager._markdown_report(payload).encode())

        bundle = run_root / "artifact-bundle.zip"
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in run_root.rglob("*"):
                if not path.is_file() or path == bundle or "obj_dir" in path.parts:
                    continue
                if path.suffix.lower() in {".exe", ".o", ".d", ".cpp", ".h"}:
                    continue
                archive.write(path, path.relative_to(run_root))

    @staticmethod
    def _markdown_report(payload: dict[str, object]) -> str:
        integrity = payload.get("integrity") if isinstance(payload.get("integrity"), dict) else {}
        baseline = payload.get("baseline_summary") if isinstance(payload.get("baseline_summary"), dict) else {}
        lines = [
            "# RTL Detective report",
            "",
            f"- Status: `{payload.get('status')}`",
            f"- Verdict: `{payload.get('verdict')}`",
            f"- Claim: {payload.get('claim')}",
            f"- Source SHA-256: `{payload.get('source_hash')}`",
            f"- Baseline: `{baseline.get('status', 'not available')}`",
            f"- Simulator: {baseline.get('simulator_version') or 'unavailable'}",
            f"- Locked assets unchanged: `{integrity.get('locked_assets_unchanged', False)}`",
        ]
        for index, attempt in enumerate(payload.get("attempts", []), start=1):
            if not isinstance(attempt, dict):
                continue
            investigation = attempt.get("investigation")
            candidate = attempt.get("candidate")
            verification = attempt.get("verification")
            lines.extend(["", f"## Attempt {index}", ""])
            if isinstance(investigation, dict):
                request = investigation.get("provider_request")
                if isinstance(request, dict):
                    lines.append(
                        f"- Provider: {_markdown_code(request.get('provider'))} / "
                        f"{_markdown_code(request.get('model_id'))}"
                    )
                    lines.append(f"- Request: {_markdown_code(request.get('request_id'))}")
            if isinstance(candidate, dict):
                lines.append(f"- Candidate SHA-256: `{candidate.get('source_sha256') or 'rejected'}`")
            if isinstance(verification, dict):
                reproducer = verification.get("reproducer")
                regression = verification.get("regression")
                if isinstance(reproducer, dict):
                    lines.append(f"- Reproducer: `{reproducer.get('status')}`")
                if isinstance(regression, dict):
                    lines.append(f"- Locked regression: `{regression.get('status')}`")
        lines.extend(["", "## Artifacts", ""])
        lines.extend(f"- `{name}`" for name in payload.get("artifacts", []))
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {item}" for item in payload.get("limitations", []))
        return "\n".join(lines) + "\n"

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

