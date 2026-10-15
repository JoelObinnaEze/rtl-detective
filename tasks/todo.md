# Proof Engine Tasks

## Task 1: Emit proof for deterministic baseline runs

**Description:** Add the smallest typed proof model and connect it to the existing no-model workflow path so every correct, compile-failed, timed-out, cancelled, or baseline-mismatch run has a versioned claim, limits, integrity result, and portable baseline summary.

**Acceptance criteria:**

- [x] Existing report fields remain present while `schema_version`, `run_limits`, `claim`, `integrity`, and a baseline evidence summary are added.
- [x] Claims are derived deterministically from executed status/verdict values, and a correct design makes zero provider calls.
- [x] Trace references are relative artifact paths or `null`; no absolute host path is serialized.

**Verification:**

- [x] Red-first tests pass: `.\.venv\Scripts\python.exe -m pytest tests/test_proof.py tests/test_workflow.py -q`
- [x] Static check passes: `ruff check backend/agent/proof.py backend/agent/workflow.py tests/test_proof.py tests/test_workflow.py`

**Dependencies:** None

**Files likely touched:**

- `backend/agent/proof.py`
- `backend/agent/workflow.py`
- `tests/test_proof.py`
- `tests/test_workflow.py`

**Estimated scope:** Medium

## Task 2: Capture the complete model-assisted attempt trail

**Description:** Extend each ordered attempt with the normalized stimulus actually executed, declared evidence cycles, investigation outcome, provider telemetry, patch disposition, candidate hash, and independent reproducer/regression summaries.

**Acceptance criteria:**

- [x] Every recorded transaction was actually converted by the selected contract pack and executed by the simulator.
- [x] Patch rejection, non-reproducing investigation, failed regression, provider failure, cancellation, and multi-attempt paths retain complete partial evidence without a success claim.
- [x] `candidate_passed_listed_tests` requires a passing reproducer, passing locked regression, and unchanged locked hashes.

**Verification:**

- [x] Red-first tests pass: `.\.venv\Scripts\python.exe -m pytest tests/test_proof.py tests/test_workflow.py -q`
- [x] Mutation check: bypass one successful-repair gate, confirm a focused test fails, then restore it.
- [x] Static check passes: `ruff check backend/agent/proof.py backend/agent/workflow.py tests/test_proof.py tests/test_workflow.py`

**Dependencies:** Task 1

**Files likely touched:**

- `backend/agent/proof.py`
- `backend/agent/workflow.py`
- `tests/test_proof.py`
- `tests/test_workflow.py`

**Estimated scope:** Medium

## Checkpoint: Workflow proof

- [x] Tasks 1 and 2 acceptance criteria pass.
- [x] The workflow remains green for correct FIFO, repaired FIFO, and correct arbiter fixtures.
- [x] A fresh diff review finds no model-controlled success claims.

## Task 3: Persist coherent and sanitized proof artifacts

**Description:** Make service serialization produce mutually consistent JSON, Markdown, and ZIP evidence, and write a minimal sanitized proof record when an unexpected orchestrator failure prevents a normal workflow report.

**Acceptance criteria:**

- [x] `report.json`, `report.md`, and ZIP contents agree on verdict, claim, hashes, provider identity, verification gates, and artifact names.
- [x] The serialized report contains no absolute workspace path, API key, authorization header, raw prompt, or hidden reasoning.
- [x] Unexpected orchestrator failure reaches `infrastructure_error` only after a schema-versioned fallback `report.json` is saved.

**Verification:**

- [x] Red-first service tests pass: `.\.venv\Scripts\python.exe -m pytest tests/test_service.py tests/test_api.py tests/test_cli.py -q`
- [x] Local smoke run succeeds: `.\.venv\Scripts\python.exe -m backend.cli verify --example case-005 --artifacts .test-tmp\proof-smoke`
- [x] Inspect `.test-tmp\proof-smoke` report and bundle names against the acceptance criteria.

**Dependencies:** Tasks 1 and 2

**Files likely touched:**

- `backend/service.py`
- `tests/test_service.py`
- `tests/test_api.py`

**Estimated scope:** Medium

## Task 4: Document the proof contract and completed module

**Description:** Update public documentation only after the executable behavior is final, then mark the proof-engine module complete without inventing live-provider results.

**Acceptance criteria:**

- [x] README explains proof-carrying repair, report fields, verification gates, and the local judge path in user language.
- [x] Changelog records the user-visible evidence and portability improvements.
- [x] The approved spec and capability map accurately reflect implementation status and retain the live-Nebius gate.

**Verification:**

- [x] Documentation links and commands match the repository.
- [x] Full verification passes: `.\.venv\Scripts\python.exe -m pytest -q`, `ruff check backend tests`, `.\.venv\Scripts\python.exe -m compileall -q backend`, `node --check frontend/app.js`, `.\.venv\Scripts\python.exe -m pip check`, and `git diff --check`.
- [x] Graphify is updated and the proof path is inspected before review.

**Dependencies:** Task 3

**Files likely touched:**

- `README.md`
- `CHANGELOG.md`
- `SPEC-proof-engine.md`
- `CAPABILITY_MAP.md`

**Estimated scope:** Medium

## Checkpoint: Complete

- [x] Every task and acceptance criterion above is checked.
- [x] Real Verilator FIFO, arbiter, and benchmark tests pass.
- [x] JSON, Markdown, and ZIP evidence agree and contain no host paths or secrets.
- [x] Atomic commits leave the working tree clean and ready for `judge-workbench` planning.
