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

Copy `.env.example` values into your environment; do not commit a real `.env`.

```powershell
$env:NEBIUS_API_KEY = "..."
.\.venv\Scripts\python -m backend.cli models
$env:NEBIUS_MODEL_ID = "<exact NVIDIA/Nemotron ID returned above>"
.\.venv\Scripts\python -m backend.cli verify --example case-001
```

The backend verifies the configured ID against the account’s live `/v1/models` response before inference. Calls use Nebius’ OpenAI-compatible `/v1/chat/completions` endpoint and JSON-schema output. Credentials never enter the browser, simulator container, prompt, logs, or artifacts.

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
5. Unified diffs may modify only a candidate `dut.sv`. Check-disabling edits, foreign code, path traversal, symlinks, and oversized inputs are rejected.
6. Every candidate reruns its proposed reproducer and the locked suite. Oracle, test template, and restriction hashes are compared before and after.
7. SQLite stores ordered events; per-run directories store reports, source, candidate, traces, and a ZIP bundle.

Uploaded RTL runs in `verilator/verilator:v5.050` with no network, a read-only root filesystem, dropped capabilities, a non-root UID, no-new-privileges, and CPU/memory/process/file-size/time limits. The Docker tag is published by the official Verilator image repository. Local subprocess mode is explicitly limited to trusted bundled fixtures.

## API

- `POST /api/runs` — create a run; accepts `contractId` (`fifo` by default or `arbiter`) plus the relevant parameters and supports `Idempotency-Key`.
- `GET /api/runs/{id}` — current state and ordered events.
- `GET /api/runs/{id}/events` — server-sent event stream.
- `POST /api/runs/{id}/cancel` — request cancellation.
- `GET /api/runs/{id}/artifacts` — downloadable outputs.
- `GET /api/examples` — opaque bundled examples.

Interactive states are `queued → validating → baseline → investigating → patching → regression → completed`, with `unresolved`, `invalid_input`, `cancelled`, and `infrastructure_error` terminal alternatives.

## Current verification status

Verified locally on October 14, 2026:

- Python 3.13.7 and Verilator 5.050.
- FIFO and arbiter contract/oracle tests, ten-case real-Verilator benchmark, patch restrictions, provider schema validation, persistence/API/UI contracts, and an end-to-end fake-provider repair with independent regression.
- The published offline matrix passed 18/18 configurations across three recorded seeds per configuration (54 seed/configuration combinations). Raw local output is in `artifacts/evaluation/matrix-results.json`.
- The pinned `verilator/verilator:v5.050` worker passed an actual Docker simulation with its network, filesystem, privilege, and resource restrictions enabled.
- No `NEBIUS_API_KEY` was available, so a live Token Factory request and exact account model ID remain unverified.

## Hackathon checklist

The [official rules](https://nebiusglobalaihackathon.devpost.com/rules) list an October 30, 2026, 10:00 a.m. PDT deadline (11:00 a.m. in Calgary/Edmonton), require a runtime Token Factory or Nebius AI Cloud call using an NVIDIA open-source model, a public open-source repository, a working demo/test build, and a public YouTube demo under three minutes. Judging access must remain free through December 15, 2026.

Before submission: complete and record a real Nebius call, inspect and publish the raw metrics, recheck Docker isolation on the deployment host, publish the repository/demo, record the real UI flow, provide specific Nebius/NVIDIA feedback, and re-check eligibility/current rules. Nothing in this repository submits or purchases anything automatically.

## Limitations

- No arbitrary RTL interfaces, asynchronous FIFO, CDC, metastability, UVM, vendor build systems/IP, synthesis, place-and-route, timing closure, or board programming.
- Cancellation is checked between bounded stages. Container timeouts kill the named worker; cancellation during an active local trusted simulation waits for that subprocess to finish.
- The first release has one active simulation worker and local SQLite storage; it is not a multi-tenant service.

Licensed under Apache-2.0. See `LICENSE`.

