# Implementation Plan: Proof Engine

## Overview

Implement the approved `proof-engine` module as four small vertical slices. The existing repair state machine remains authoritative; the work adds a typed proof projection, captures every executed agent attempt, persists portable evidence, and documents the resulting contract. Existing API requests and report fields remain compatible.

## Dependency Graph

```text
SimulationOutcome + model replies + executed transactions
                       │
                       ▼
        typed, deterministic proof summaries
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      correct-input proof   repair-attempt proof
             └─────────┬─────────┘
                       ▼
        portable JSON / Markdown / ZIP artifacts
                       │
                       ▼
       judge-workbench and evaluation-scorecard
```

## Architecture Decisions

- Keep `report.json` as the sole canonical report. New fields are additive and `schema_version` begins at `1`.
- Add one small `backend/agent/proof.py` module for immutable evidence summaries and deterministic claim derivation. This keeps serialization and claim policy out of the repair loop without introducing a framework.
- Preserve the current top-level report and attempt fields so the existing frontend and API remain functional while `judge-workbench` is built later.
- Record only normalized transactions actually passed to the simulator. Model-requested values that fail schema or contract conversion never become evidence.
- Store concise hypothesis and diagnosis text, not full prompts or hidden reasoning.
- Treat successful repair as three independent gates: reproducer passed, locked regression passed, and locked assets unchanged.
- Convert trace references to artifact-relative POSIX paths at the proof boundary; never serialize host paths.
- Persist a sanitized fallback report when an unexpected orchestrator error prevents a normal workflow report.
- Add no dependency and make no endpoint or run-request changes.

## Task List

### Phase 1: Executed proof

- [x] Task 1: Emit proof for deterministic baseline runs
- [x] Task 2: Capture the complete model-assisted attempt trail

### Checkpoint: Workflow proof

- [x] Focused proof and workflow tests pass
- [x] Correct designs make zero provider calls
- [x] Successful repair claims require all three verification gates
- [x] Mutation check proves a removed gate fails a test

### Phase 2: Portable artifacts

- [x] Task 3: Persist coherent and sanitized proof artifacts
- [x] Task 4: Document the proof contract and completed module

### Checkpoint: Complete

- [x] Real FIFO and arbiter simulator tests pass
- [x] Full test suite and static checks pass
- [x] A local bundled run produces matching JSON, Markdown, and ZIP evidence
- [x] No report contains an absolute host path, secret, or unsupported proof claim
- [x] Graphify is updated and the changed dependency path is reviewed
- [x] Atomic commits leave the working tree clean

## Implementation Order

1. Task 1 establishes the proof vocabulary and covers the no-model path first.
2. Task 2 extends the same public record through investigation, patching, rejection, and regression branches.
3. Task 3 serializes the proven structures and handles persistence failures without weakening claims.
4. Task 4 updates user-facing documentation only after runtime behavior is verified.

Tasks are sequential because Tasks 2 and 3 depend on the proof schema established by Task 1. Documentation can only describe the final, tested schema.

## Verification Checkpoints

### After Task 1

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_proof.py tests/test_workflow.py -q
```

### After Task 2

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_proof.py tests/test_workflow.py -q
```

Perform one mutation check by bypassing a successful-repair gate and confirming the focused suite fails, then restore the implementation.

### After Task 3

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_service.py tests/test_api.py tests/test_cli.py -q
.\.venv\Scripts\python.exe -m backend.cli verify --example case-005 --artifacts .test-tmp\proof-smoke
```

### Final

```powershell
.\.venv\Scripts\python.exe -m pytest -q
ruff check backend tests
.\.venv\Scripts\python.exe -m compileall -q backend
node --check frontend/app.js
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Additive fields accidentally break current frontend or clients | Medium | Preserve all existing fields and run API, CLI, and frontend tests unchanged |
| A serialized `Path` exposes the host filesystem | High | Centralize relative trace conversion and test the full JSON and ZIP output for workspace prefixes |
| A claim overstates incomplete evidence | High | Derive claims from explicit terminal verdicts and verification gates; mutation-test the success gate |
| Attempt records become large or duplicate raw simulator output | Medium | Store summaries and artifact references; keep raw stdout, stderr, source, and VCD in the bundle |
| Unexpected orchestrator errors still lack artifacts | Medium | Write a minimal sanitized fallback report before publishing terminal state |
| Live provider behavior differs from the fake provider | Medium | Preserve optional telemetry, validate schemas, and defer measured model claims to `live-nebius-proof` |

## Open Questions

None. Live model selection and measured Token Factory evidence remain outside this module until Nebius account access is available.
