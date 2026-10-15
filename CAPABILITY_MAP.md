# Capability Map: Competition-Grade RTL Detective

Status: approved on October 14, 2026. `proof-engine` is implemented and locally verified; live Nebius proof remains pending account access.

## Decision

Evolve RTL Detective rather than replace it. The verified simulation, oracle, bounded Nemotron repair loop, locked-test enforcement, artifact chain, and two contract packs already satisfy the difficult technical core of the Coding and Agentic Engineering track. Rebuilding would spend the remaining submission window recreating working infrastructure instead of improving the four judging dimensions.

Official basis:

- [Hackathon overview](https://nebiusglobalaihackathon.devpost.com/): the Coding and Agentic Engineering track asks for agents that write, run, and test code in Token Factory.
- [Judging guidance](https://nebiusglobalaihackathon.devpost.com/updates/46204-here-s-how-judging-works): organizers say a standout entry plans, writes, tests, and iterates on a real repository with minimal human input.
- [Official rules](https://nebiusglobalaihackathon.devpost.com/rules): implementation, design, impact, and idea quality are equally weighted; a live Nebius/NVIDIA runtime integration is a pass/fail requirement.

## Rubric gaps

| Criterion | Existing strength | Gap to close |
|---|---|---|
| Technological implementation | Real Verilator execution, executable oracles, bounded Nemotron loop, isolated uploads, locked regression | The autonomous reasoning and evidence chain are mostly hidden; no live Token Factory run has been recorded |
| Design | Responsive dark workspace and live event stream | Results stop at a first-mismatch table and raw diff instead of telling the full investigation-to-verification story |
| Potential impact | Specific FPGA/ASIC debugging problem with two supported RTL contracts | No public repair benchmark, judge fast path, or concrete time/quality comparison |
| Quality of idea | AI patches are independently verified instead of trusted | The strongest idea—proof-carrying RTL repair—is not named, visualized, or demonstrated as the product thesis |

## Modules

| Module id | Status | Responsibility | Depends on |
|---|---|---|---|
| `proof-engine` | Implemented locally | Produce an auditable repair record: bounded failing reproducer, model hypothesis and diagnosis, candidate diff, provider telemetry, simulator identity, locked-asset integrity, and independent reproducer/regression outcomes | Existing verification core |
| `judge-workbench` | Next | Rebuild the dark UI around a single narrative: contract → failing cycle → agent investigation → proposed code → verification gates → downloadable proof bundle | `proof-engine` |
| `evaluation-scorecard` | Planned | Run and publish reproducible baselines for locked tests, investigation, and full repair with raw per-case results, explicit denominators, false-positive counts, attempts, runtime, and model usage | `proof-engine`, live Nebius access for final numbers |
| `repo-workflow` | Planned | Add a judgeable real-repository path through a documented CLI/CI workflow while retaining the safe canonical contract boundary | `proof-engine` |
| `submission-kit` | Planned | Provide the hosted-demo runbook, judge quick start, Devpost copy, significant-update disclosure, three-minute script/storyboard, screenshots checklist, and Nebius/NVIDIA feedback template | `judge-workbench`, `evaluation-scorecard`, `repo-workflow` |
| `live-nebius-proof` | Blocked on account | Discover the account's exact NVIDIA model, run a real Token Factory repair, preserve request/model/latency/token evidence, and replace every placeholder in the scorecard and demo | Builder Program approval, `proof-engine` |

Build order: `proof-engine` → `judge-workbench` + `repo-workflow` → `evaluation-scorecard` → `submission-kit`. Run `live-nebius-proof` immediately when credentials arrive, then freeze the measured submission evidence.

## Scope guardrails

- Keep the existing Python/FastAPI/vanilla frontend stack and dark visual language; do not restart in React merely for novelty.
- Keep FIFO and round-robin arbiter as the supported, explicit contract packs. Depth beats adding shallow module families.
- Do not claim formal proof, minimal counterexamples, or repair success without rerunning saved evidence.
- Do not add Tavily solely for a bonus prize; only add it if it materially improves the RTL workflow.
- Do not fabricate Token Factory results while account access is pending.

## Submission gates

- The final app makes a runtime call to Nebius Token Factory using an available NVIDIA open-source model.
- A public repository includes the license, clean setup, judge quick start, and all required assets.
- A free working demo/test build stays accessible through December 15, 2026.
- A public YouTube demo is under three minutes and shows real operation.
- The Devpost entry identifies the track, explains significant in-period updates, and includes specific Nebius/NVIDIA feedback.
- Submission is complete before October 30, 2026 at 10:00 a.m. PDT / 11:00 a.m. America/Edmonton.
