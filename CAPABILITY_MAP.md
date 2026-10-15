# Capability Map: Competition-Grade RTL Detective

Status: released and verified on October 15, 2026. The public repository, hosted demo, 2:26 video, proof engine, judge workbench, evaluation record, and live Nebius/NVIDIA repair are available for review.

## Decision

Evolve RTL Detective rather than replace it. The verified simulation, oracle, bounded Nemotron repair loop, locked-test enforcement, artifact chain, and two contract packs already satisfy the difficult technical core of the Coding and Agentic Engineering track. Rebuilding would spend the remaining submission window recreating working infrastructure instead of improving the four judging dimensions.

Official basis:

- [Hackathon overview](https://nebiusglobalaihackathon.devpost.com/): the Coding and Agentic Engineering track asks for agents that write, run, and test code in Token Factory.
- [Judging guidance](https://nebiusglobalaihackathon.devpost.com/updates/46204-here-s-how-judging-works): organizers say a standout entry plans, writes, tests, and iterates on a real repository with minimal human input.
- [Official rules](https://nebiusglobalaihackathon.devpost.com/rules): implementation, design, impact, and idea quality are equally weighted; a live Nebius/NVIDIA runtime integration is a pass/fail requirement.

## Rubric evidence

| Criterion | Evidence | Deliberate limit |
|---|---|---|
| Technological implementation | Live Nebius/NVIDIA calls, real Verilator execution, executable oracles, bounded repair, isolated uploads, and locked regression | Single-instance demo architecture, not a multi-tenant service |
| Design | Responsive dark workbench, live event stream, explicit provider/model proof, and six visible verification gates | Render's free tier may cold-start after inactivity |
| Potential impact | Specific FPGA/ASIC debugging problem, two RTL contracts, ten-case benchmark, and a 54-run offline matrix | Results apply only to the named contracts and configurations |
| Quality of idea | Proof-carrying RTL repair: AI proposes while deterministic gates decide | Simulation evidence is intentionally not described as formal proof |

## Modules

| Module id | Status | Responsibility | Depends on |
|---|---|---|---|
| `proof-engine` | Implemented locally | Produce an auditable repair record: bounded failing reproducer, model hypothesis and diagnosis, candidate diff, provider telemetry, simulator identity, locked-asset integrity, and independent reproducer/regression outcomes | Existing verification core |
| `judge-workbench` | Implemented | Present contract → failing cycle → investigation → candidate → verification gates → downloadable proof bundle in the dark UI | `proof-engine` |
| `evaluation-scorecard` | Implemented | Publish benchmark, matrix, and live-repair outcomes with explicit denominators, usage, cost, hashes, and limitations | `proof-engine`, `live-nebius-proof` |
| `repo-workflow` | Implemented | Provide CLI/API judge paths and a deployment runbook while retaining the safe canonical contract boundary | `proof-engine` |
| `submission-kit` | Implemented | Provide Devpost copy, significant-update disclosure, judge links, and Nebius/NVIDIA feedback | `judge-workbench`, `evaluation-scorecard`, `repo-workflow` |
| `live-nebius-proof` | Implemented | Record a real Token Factory repair with NVIDIA Nemotron 3 Super and preserve model, latency, token, candidate, regression, and integrity evidence | `proof-engine` |

Completed build order: `proof-engine` → `judge-workbench` + `repo-workflow` → `evaluation-scorecard` → `live-nebius-proof` → `submission-kit`.

## Scope guardrails

- Keep the existing Python/FastAPI/vanilla frontend stack and dark visual language; do not restart in React merely for novelty.
- Keep FIFO and round-robin arbiter as the supported, explicit contract packs. Depth beats adding shallow module families.
- Do not claim formal proof, minimal counterexamples, or repair success without rerunning saved evidence.
- Do not add Tavily solely for a bonus prize; only add it if it materially improves the RTL workflow.
- Treat the recorded live repair as one observed run; do not generalize it into an unsupported repair-rate claim.

## Submission gates

- The final app makes a runtime call to Nebius Token Factory using an available NVIDIA open-source model.
- A public repository includes the license, clean setup, judge quick start, and all required assets.
- A free working demo/test build stays accessible through December 15, 2026.
- A judge-accessible YouTube demo is under three minutes and shows real operation.
- The Devpost entry identifies the track, explains significant in-period updates, and includes specific Nebius/NVIDIA feedback.
- Submission is complete before October 30, 2026 at 10:00 a.m. PDT / 11:00 a.m. America/Edmonton.
