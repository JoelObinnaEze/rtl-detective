# Spec: Proof Engine

Module id: `proof-engine`

Status: approved on October 14, 2026

Parent: [CAPABILITY_MAP.md](CAPABILITY_MAP.md)

## Objective

Turn the existing bounded RTL repair workflow into an auditable, proof-carrying agent. A hardware engineer or hackathon judge must be able to answer, from one saved report:

1. What contract and source were tested?
2. What exact failure was observed?
3. What bounded stimulus did the NVIDIA model propose, and did it reproduce a mismatch?
4. What diagnosis and candidate diff did the model produce?
5. Did the candidate pass that reproducer and the independently locked regression suite?
6. Which simulator, model, requests, limits, hashes, and artifacts support those claims?

The engine must expose concise, verifiable reasoning summaries without storing or requesting private chain-of-thought. It must continue to report only `failure_reproduced`, `candidate_passed_listed_tests`, `no_failure_found_in_tested_cases`, or `repair_not_verified`-equivalent claims supported by executed evidence.

### User stories

- As an RTL engineer, I can replay the exact bounded stimulus that exposed a defect.
- As a reviewer, I can trace every repair claim to simulator output and locked-test results.
- As a judge, I can see that Nemotron is part of a multi-step write/run/test/iterate workflow rather than a decorative API call.
- As a maintainer, I can evolve the report without breaking existing API consumers.

## Tech Stack

- Python `>=3.11`.
- FastAPI `0.143.1`, Pydantic through the pinned FastAPI dependency set, and HTTPX `0.28.1`.
- Verilator image `verilator/verilator:v5.050`; trusted bundled cases may use a compatible local Verilator `5.050` installation.
- SQLite through the Python standard library for run/event state.
- Existing `vcdvcd==2.6.0` trace extraction.
- Existing vanilla HTML, CSS, and JavaScript consumer; UI changes belong to `judge-workbench`.
- No new runtime dependency is required for this module.

## Commands

From the repository root on Windows PowerShell:

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.lock

# Focused tests
.\.venv\Scripts\python.exe -m pytest tests/test_workflow.py tests/test_service.py tests/test_api.py -q

# Real simulator integration
.\.venv\Scripts\python.exe -m pytest tests/test_simulation.py tests/test_arbiter.py tests/test_benchmarks.py -q

# Full verification
.\.venv\Scripts\python.exe -m pytest -q
ruff check backend tests
.\.venv\Scripts\python.exe -m compileall -q backend
node --check frontend/app.js
.\.venv\Scripts\python.exe -m pip check

# Local judge run
.\.venv\Scripts\python.exe -m backend.cli verify --example case-001 --artifacts artifacts
```

## Project Structure

```text
backend/agent/workflow.py       Proof records and bounded repair state machine
backend/verification/runner.py  Simulation outcome and executable evidence
backend/providers/nebius.py     Validated model actions and provider telemetry
backend/service.py              Persistence and report/artifact serialization
backend/api.py                  Existing run and artifact interfaces
tests/test_workflow.py          Agent-loop and proof-record tests
tests/test_service.py           Artifact and serialization tests
tests/test_api.py               Backward-compatible API contract tests
artifacts/runs/<run-id>/        Immutable per-run evidence exposed to users
```

The module may add a small `backend/agent/proof.py` only if the workflow data structures would otherwise become harder to read. It must not introduce a generic event framework or a second report format.

## Proof Record Contract

`report.json` remains the canonical machine-readable artifact. Existing top-level fields remain valid. The following information becomes explicit and JSON-serializable:

- `schema_version`: integer report schema version, starting at `1`.
- `run_limits`: maximum patch attempts and simulation timeout used for the run.
- `baseline`: existing outcome plus a stable evidence summary containing status, transaction count, first mismatch, simulator version, and an artifact-relative trace path when present.
- `attempts[].investigation`:
  - bounded, normalized transactions actually executed;
  - model hypothesis and declared evidence cycles;
  - simulation status, first mismatch, transaction count, and trace reference;
  - provider, exact model id, latency, token usage when returned, and request id when returned.
- `attempts[].candidate`:
  - concise diagnosis and unified diff;
  - SHA-256 of the candidate source when a patch is accepted;
  - explicit patch rejection reason when rejected.
- `attempts[].verification`:
  - reproducer outcome summary;
  - locked regression outcome summary;
  - separate pass/fail gates rather than a combined confidence score.
- `integrity`: original source hash, locked asset hashes before and after, and an explicit `locked_assets_unchanged` boolean.
- `claim`: a short human-readable claim generated deterministically from the executed gates, never by the model.

Raw source, testbench, trace, stdout, and stderr remain files in the artifact bundle instead of being duplicated into the report. Paths stored in the report are relative to the run root. Missing provider usage or request ids are represented as `null` or an empty object, never invented.

### Code style

Use frozen dataclasses for immutable internal proof records, plain dictionaries only at the serialization boundary, and names that state the evidence represented:

```python
@dataclass(frozen=True)
class OutcomeSummary:
    status: str
    transaction_count: int
    first_failure: dict[str, object] | None
    simulator_version: str | None
    trace_artifact: str | None
```

- Public data fields use explicit names; do not encode meaning in booleans such as `ok1`.
- Derive user-facing claims from simulator states in one function.
- Keep methods small enough that the baseline, investigation, patch, and verification gates remain visually distinct.
- Comments explain security or evidence invariants only.

## Testing Strategy

### Unit tests

- A proof summary serializes a mismatch, a passing outcome, and a missing trace without absolute paths.
- Deterministic claims map every terminal workflow result to wording supported by its gates.
- Provider telemetry preserves returned values and represents unavailable fields honestly.
- Patch rejection records a reason without a candidate hash or verification claim.

### Workflow tests

- A correct design completes with no model calls and a `no failure found in tested cases` claim.
- A defective design records the agent-proposed stimulus, reproduced mismatch, candidate hash, passing reproducer, passing locked regression, and unchanged locked assets.
- A reproducer that does not fail cannot advance to patching.
- A candidate that passes the reproducer but fails locked regression remains unverified.
- Multiple attempts remain ordered and individually attributable to provider requests.
- Cancellation and provider/infrastructure failures produce complete partial proof records without success claims.

### Integration tests

- Real Verilator FIFO and arbiter cases produce report evidence matching their saved simulation results.
- `report.json`, `report.md`, and `artifact-bundle.zip` agree on verdict, hashes, and artifact names.
- Existing API and CLI commands continue to work without requiring new request fields.

Tests for every new branch are written red-first. The full 70-test baseline must remain green, with new proof tests added to it.

## Boundaries

### Always do

- Preserve the original source and hash it before simulation.
- Execute every stimulus represented as evidence.
- Keep model text labeled as hypothesis or diagnosis; keep simulator results labeled as observations.
- Run the accepted candidate against both its reproducer and the complete locked regression suite.
- Hash locked assets before and after every terminal path.
- Validate all model output through the existing Pydantic schemas.
- Keep credentials, full prompts, and hidden reasoning out of reports and logs.

### Ask first

- Add a runtime dependency.
- Change the public run-creation request or existing endpoint paths.
- Remove or rename existing report fields.
- Raise model-call, token, patch-attempt, or simulation-time budgets.

### Never do

- Call a candidate formally proven, safe, optimal, or minimal based on simulation.
- Treat a model-proposed test as independent verification.
- Persist API keys, authorization headers, raw hidden prompts, or private chain-of-thought.
- Let the model edit contracts, oracles, test templates, restrictions, or expected benchmark labels.
- Convert a failed or incomplete gate into a numeric confidence score that suggests success.

## Success Criteria

- Every completed or failed run writes a schema-versioned `report.json` with a deterministic `claim`, integrity result, limits, and artifact-relative evidence references.
- Every model-assisted attempt records the exact normalized stimulus executed, its outcome, the model hypothesis/diagnosis, provider telemetry, patch disposition, and independent verification gates.
- A successful repair claim is impossible unless the reproducer and full locked regression both executed and passed and locked hashes match.
- A correct input makes zero model calls and receives no candidate patch.
- Partial runs remain inspectable after cancellation, provider failure, compile failure, timeout, or patch rejection.
- No report or ZIP entry exposes an absolute host path or secret.
- Existing API clients remain compatible.
- Focused tests, real Verilator integration tests, the full test suite, lint, compilation, JavaScript syntax, and dependency checks pass.

## Non-Goals

- UI redesign; handled by `judge-workbench`.
- New RTL contract families.
- Formal verification or synthesis.
- Automatic submission, hosting, or credential management.
- Claiming a minimal counterexample. The agent-proposed reproducer is bounded and replayed, not proven minimal.
- Publishing repair-rate numbers before a real Nebius-backed evaluation is stored.

## Open Questions

No design choice blocks implementation. The exact NVIDIA model id and live provider evidence remain intentionally unresolved until the Builder Program account exposes the available model catalog.
