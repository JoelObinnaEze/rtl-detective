# RTL Detective

RTL Detective is an evidence-first agent for canonical, single-clock SystemVerilog blocks. It compiles the DUT with Verilator, compares every sampled cycle with the selected contract pack's executable oracle, asks an NVIDIA/Nemotron model through Nebius Token Factory for a bounded investigation and candidate diff, then independently reruns the reproducer and locked tests.

It reports only what the saved evidence supports: **failure reproduced**, **candidate passed listed regression tests**, **no failure found in tested cases**, or **repair not verified**. Simulation is not formal proof.

## Supported contract packs

- **Synchronous FIFO:** module `fifo`; parameters `DATA_WIDTH` and `DEPTH`; inputs `clk`, `rst`, `wr_en`, `rd_en`, `din`; outputs `dout`, `full`, `empty`, `count`. It uses synchronous active-high reset, registered `dout`, no fall-through, pre-edge acceptance, and explicit pointer wrapping for non-power-of-two depths.
- **Round-robin arbiter:** module `round_robin_arbiter`; parameter `REQUESTERS` from 2 through 32; inputs `clk`, `rst`, `request`; output `grant`. The registered grant is one-hot-or-zero, selection starts at the saved priority and wraps by requester index, a grant advances priority, and an idle cycle preserves it.

Other policies and interfaces are rejected rather than silently adapted.

## Quick start

Prerequisites: Python 3.11+, and either Docker Desktop/Engine or Verilator 5.050 plus a C++ toolchain. Docker is mandatory for pasted/uploaded RTL; bundled examples may use the local simulator when Docker is unavailable.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --only-binary=:all: -r requirements.lock
.\.venv\Scripts\python -m backend.cli verify --example case-005
.\.venv\Scripts\python -m backend.cli verify --example arbiter-case-003 --contract arbiter --requesters 3
.\.venv\Scripts\python -m backend.cli serve
```

On Linux/macOS, activate `.venv/bin/python` instead. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

`case-005` and `arbiter-case-003` are correct bundled implementations and complete without an AI call. Defective cases reproduce deterministically; repair requires the Nebius settings below.

## Nebius Token Factory

Copy `.env.example` values into your process or service environment; do not commit a real `.env`. The app deliberately reads process environment variables and does not auto-load `.env` files, while `.env*` is ignored to reduce the chance of committing a key.

```powershell
$env:NEBIUS_API_KEY = "..."
.\.venv\Scripts\python -m backend.cli models
$env:NEBIUS_MODEL_ID = "nvidia/nemotron-3-super-120b-a12b"
$env:NEBIUS_MAX_RETRIES = "0"
$env:NEBIUS_MAX_OUTPUT_TOKENS = "1536"
$env:MAX_PATCH_ATTEMPTS = "1"
$env:MAX_PENDING_RUNS = "4"
.\.venv\Scripts\python -m backend.cli verify --example case-001
```

If `NEBIUS_MODEL_ID` is omitted, the app uses the verified `nvidia/nemotron-3-super-120b-a12b` default; override it after running `rtl-detective models` if the catalog changes. The backend verifies the selected ID against the account’s live `/v1/models` response before inference. Calls use Nebius’ OpenAI-compatible `/v1/chat/completions` endpoint and strict JSON-schema output. Retries default to zero and one repair attempt is allowed, so a judge run makes at most two model requests: investigation and patch. Credentials never enter the browser, simulator container, prompt, logs, or artifacts.

Official references: [model listing](https://docs.tokenfactory.nebius.com/api-reference/examples/list-of-models), [text generation](https://docs.tokenfactory.nebius.com/api-reference/examples/text-generation), and [structured JSON output](https://docs.tokenfactory.nebius.com/ai-models-inference/json).

## Verification and tests

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m backend.evaluate --source benchmark/designs/correct/reference_fifo.sv
```

The published offline matrix is `DATA_WIDTH={1,8,16}` × `DEPTH={1,2,3,4,7,8}`, with three recorded seeds per configuration. Raw results are written to `artifacts/evaluation/matrix-results.json`; do not report rates until that file exists and all denominators are stated.

The bundled benchmark contains ten opaque cases: four FIFO defects, two correct FIFOs, two arbiter defects, and two independently structured correct arbiters. Expected labels remain outside model prompts. The published 18-configuration offline matrix remains FIFO-specific until an arbiter matrix is versioned and measured.

## Architecture

1. FastAPI/CLI selects a contract pack, validates its canonical interface, preserves the original, and records a SHA-256 hash.
2. The selected pack supplies a human-authored testbench, directed and seeded-random transactions, an executable oracle, and a locked regression suite.
3. Verilator 5.050 emits observations and a VCD; the selected oracle records the first cycle-level mismatch.
4. Only bounded evidence and untrusted DUT text are sent to the configured Nemotron model.
5. Nemotron returns the complete candidate as structured source lines; the host restores the original locked module header, then creates the canonical unified diff for `dut.sv`. Any surviving header edit, check-disabling edit, foreign code, path traversal, symlink, or oversized input is rejected.
6. Every candidate reruns its proposed reproducer and the locked suite. Oracle, test template, and restriction hashes are compared before and after.
7. SQLite stores ordered events; per-run directories store reports, source, candidate, traces, and a ZIP bundle.

Uploaded RTL runs in `verilator/verilator:v5.050` with no network, a read-only root filesystem, dropped capabilities, a non-root UID, no-new-privileges, and CPU/memory/process/file-size/time limits. The Docker tag is published by the official Verilator image repository. Local subprocess mode is explicitly limited to trusted bundled fixtures.

## Proof bundle

Each terminal run writes a portable `report.json`, a judge-readable `report.md`, and `artifact-bundle.zip`. The JSON record includes the schema version and run limits; original and candidate SHA-256 hashes; locked-asset hashes; baseline evidence; ordered model attempts; provider, model, request, latency, and usage metadata when returned; the exact normalized reproducer transactions; patch disposition; and separate reproducer and locked-regression outcomes. Artifact references are relative to the run directory, and simulator stdout/stderr remain separate files instead of being embedded in the report.

A successful repair claim has three non-model gates: the accepted candidate must pass the replayed model-proposed reproducer, pass the independently locked regression suite, and leave every locked verification asset unchanged. Correct designs stop after the baseline and make no model call. Rejected patches, provider failures, cancellation, and unexpected orchestrator failures retain the evidence completed so far without claiming a repair.

For the shortest local judge path, run:

```powershell
.\.venv\Scripts\python -m backend.cli verify --example case-005 --artifacts artifacts/judge
```

The command prints the run directory. Open its `report.md` for the narrative proof or `artifact-bundle.zip` for the replayable source, generated testbench, trace, logs, and canonical JSON record. Use a defective case such as `case-001` after configuring Nebius to exercise the full investigation and repair loop.

## API

- `POST /api/runs` — create a run; accepts `contractId` (`fifo` by default or `arbiter`) plus the relevant parameters and supports `Idempotency-Key`.
- `GET /api/runs/{id}` — current state and ordered events.
- `GET /api/runs/{id}/events` — server-sent event stream.
- `POST /api/runs/{id}/cancel` — request cancellation.
- `GET /api/runs/{id}/artifacts` — downloadable outputs.
- `GET /api/examples` — opaque bundled examples.
- `GET /api/health` — service readiness plus non-secret provider/model configuration.

Interactive states are `queued → validating → baseline → investigating → patching → regression → completed`, with `unresolved`, `invalid_input`, `cancelled`, and `infrastructure_error` terminal alternatives.

The service accepts at most `MAX_PENDING_RUNS` active or queued runs (four by default) and returns `503` when that bounded queue is full. On restart, previously nonterminal runs are closed as `infrastructure_error` with a portable interruption report instead of leaving clients waiting forever. This is an in-process guard for the documented single-instance deployment; keep an edge rate limit in front of the public endpoint.

## Current verification status

Verified locally on October 14, 2026:

- Python 3.13.7 and Verilator 5.050.
- The complete test suite, isolated Ruff checks on changed Python files, Python bytecode compilation, frontend JavaScript syntax, locked dependency integrity, and the known-vulnerability audit pass.
- FIFO and arbiter contract/oracle tests, ten-case real-Verilator benchmark, patch restrictions, provider schema validation, persistence/API/UI contracts, and an end-to-end fake-provider repair with an auditable attempt trail and independent regression.
- Schema-versioned JSON, Markdown, and ZIP proof artifacts were cross-checked on a real local Verilator run; the reports use artifact-relative paths and write a sanitized fallback record on unexpected orchestrator failure.
- The published offline matrix passed 18/18 configurations across three recorded seeds per configuration (54 seed/configuration combinations). Raw local output is in `artifacts/evaluation/matrix-results.json`.
- The pinned `verilator/verilator:v5.050` worker passed an actual Docker simulation with its network, filesystem, privilege, and resource restrictions enabled.
- A live `case-001` repair completed through Nebius Token Factory with `nvidia/nemotron-3-super-120b-a12b`: 2 requests, 1,840 prompt tokens, 825 completion tokens, 2,665 total tokens, and an estimated `$0.001295` at the catalog rates observed that day. The model-proposed stimulus was safely replaced by the exact baseline failure prefix when it did not reproduce; the resulting candidate passed both that reproducer and the 80-transaction locked regression while locked assets remained unchanged.
- An October 15 hardening confirmation reached the same live provider/model with two recorded request IDs and 2,492 total tokens. It correctly refused to claim a repair when the model specialized a locked parameter default; that result led to deterministic host-side header restoration before canonical diff generation, covered by offline regression tests without another paid call.

Judge and submission material: [submission copy](SUBMISSION.md), [three-minute demo script](docs/DEMO_SCRIPT.md), [deployment runbook](docs/DEPLOYMENT.md), and [evaluation record](docs/EVALUATION.md). The included `Dockerfile` and `render.yaml` deploy the bundled-example demo on Render's free tier with the Nebius key supplied as a host secret.

## Hackathon checklist

The [official rules](https://nebiusglobalaihackathon.devpost.com/rules) list an October 30, 2026, 10:00 a.m. PDT deadline (11:00 a.m. in Calgary/Edmonton), require a runtime Token Factory or Nebius AI Cloud call using an NVIDIA open-source model, a public open-source repository, a working demo/test build, and a public YouTube demo under three minutes. Judging access must remain free through December 15, 2026.

Before submission: deploy the current commit, publish the repository, record the real UI flow, add both URLs to Devpost, keep judge access available through December 15, and re-check eligibility/current rules. Nothing in this repository submits or purchases anything automatically.

## Limitations

- No arbitrary RTL interfaces, asynchronous FIFO, CDC, metastability, UVM, vendor build systems/IP, synthesis, place-and-route, timing closure, or board programming.
- Cancellation is checked between bounded stages. Container timeouts kill the named worker; cancellation during an active local trusted simulation waits for that subprocess to finish.
- The first release has one active simulation worker and local SQLite storage; it is not a multi-tenant service.

Licensed under Apache-2.0. See `LICENSE`.

