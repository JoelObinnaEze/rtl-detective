# RTL Detective — Devpost Submission Narrative

## Links

- Live demo: https://rtl-detective.onrender.com
- Public source: https://github.com/JoelObinnaEze/rtl-detective
- Passing CI: https://github.com/JoelObinnaEze/rtl-detective/actions/workflows/ci.yml
- Demo video: https://youtu.be/UmpgmuvtHXg
- Evaluation record: https://github.com/JoelObinnaEze/rtl-detective/blob/main/docs/EVALUATION.md

## Track

Coding and Agentic Engineering

## One-line pitch

RTL Detective is a proof-carrying repair agent that lets NVIDIA Nemotron investigate SystemVerilog bugs through Nebius Token Factory, then trusts only candidates that pass a replayed reproducer, locked Verilator regression, and integrity checks.

## The problem

RTL failures are unusually hard for general coding agents: a plausible patch can compile while violating cycle semantics, and a confident explanation is not evidence. Hardware engineers need a fast first responder that can localize a failure and propose a repair without quietly changing the test or claiming more than simulation established.

## What it does

1. Validates a canonical synchronous FIFO or round-robin arbiter interface.
2. Runs directed and seeded-random transactions against a hand-authored executable oracle in Verilator.
3. Sends only bounded cycle evidence and the untrusted DUT to NVIDIA Nemotron through Nebius Token Factory.
4. Replays the model's proposed stimulus; if it passes despite a known baseline mismatch, replays the exact baseline failure prefix instead.
5. Accepts a candidate only after its reproducer and independently locked regression pass and all verification-asset hashes remain unchanged.
6. Produces a human-readable report, canonical JSON record, traces, hashes, and downloadable ZIP proof bundle.

The product thesis is simple: **AI may propose; deterministic evidence decides.**

## Why it is distinct

Most AI coding demos end at generated code or a green test badge. RTL Detective makes the evidence chain the product. It records the exact transaction, expected and observed signals, model identity and usage, candidate hash, simulator version, replay result, locked-suite result, and integrity state. Claims are derived from those gates rather than model prose, and the UI exposes every gate to the judge.

## Built with

- Nebius Token Factory OpenAI-compatible inference API
- NVIDIA Nemotron 3 Super 120B A12B
- FastAPI, Pydantic, SQLite, and server-sent events
- Verilator 5.050 in a locked-down Docker worker for untrusted uploads
- Vanilla HTML, CSS, and JavaScript in a responsive dark workbench

## Measured evidence

On October 15, 2026, a real `case-001` repair completed using `nvidia/nemotron-3-super-120b-a12b`:

- 2 provider requests
- 1,789 prompt + 683 completion = 2,472 total tokens
- baseline: functional mismatch; investigation: reproduced
- candidate: reproducer passed; 80-transaction locked regression passed
- locked verification assets unchanged
- candidate SHA-256: `a2244aa9657ed91e9c8022c3402d2417e138f05181b1ff33c1adbc98f8cfd56b`

The bundled benchmark also contains 10 hidden-label cases: 6 defective and 4 correct across FIFO and arbiter contracts. The FIFO parameter matrix passed all 18 configurations and all 54 recorded seed/configuration combinations. These are simulation results for the named contracts, not formal proof.

## Judging rubric

| Criterion | Evidence |
|---|---|
| Technological implementation | Live Nebius/NVIDIA calls, real Verilator execution, executable oracles, bounded repair loop, source restrictions, locked regression, integrity hashes, and portable artifacts |
| Design | Focused dark workbench, progressive live states, cycle-level evidence, explicit provider/model attribution, six proof gates, and responsive layout |
| Potential impact | Reduces the first diagnosis-and-repair loop for FPGA/ASIC engineers while retaining a reviewable human handoff |
| Quality of idea | Treats an AI patch as an untrusted hypothesis and ships the evidence needed to audit it |

## Nebius/NVIDIA feedback

- Token Factory's model catalog and per-model pricing metadata made it easy to choose a model within a tiny budget.
- The structured-output API accepted a named schema envelope (`name`, `schema`, and `strict`); making that exact request shape prominent in the primary docs would shorten integration time.
- Nemotron reasoning needed `chat_template_kwargs.enable_thinking=false` for reliable schema-only responses under a small output budget; this deserves a first-class structured-output example.
- For code generation, an array with one source line per item proved more reliable than asking a model to preserve a large newline-bearing diff string. The host can then construct and validate the canonical diff.

## Significant-update disclosure

Use this paragraph if Devpost treats the project as pre-existing:

> RTL Detective began as an earlier verification prototype. During the hackathon period it gained the Nebius Token Factory + NVIDIA Nemotron runtime integration, bounded investigation/repair orchestration, the round-robin arbiter contract pack, isolated execution, proof schema and artifact bundle, locked-asset integrity checks, benchmark/evaluation workflow, and the judge-facing web experience shown in this submission.
