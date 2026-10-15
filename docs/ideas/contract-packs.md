# RTL Detective Contract Packs

## Problem Statement

How might we give individual FPGA developers and small hardware teams trustworthy, cycle-level diagnosis and bounded repair for common RTL blocks without pretending arbitrary hardware can be verified from source code alone?

## Recommended Direction

Generalize the existing FIFO implementation into a small contract-pack architecture. Each pack owns a canonical interface, executable oracle, deterministic and randomized transactions, locked regression suite, evidence format, and model context.

Prove the architecture with exactly one additional pack: a round-robin arbiter. It is small enough to implement safely but introduces fairness, request persistence, grant exclusivity, and rotation. That demonstrates RTL Detective can extend beyond storage ordering without becoming a general-purpose EDA suite.

The resulting product remains focused: select a known hardware contract, map a module to it, and receive reproducible evidence rather than an ungrounded AI opinion.

## Target and Success

- **Primary user:** An individual FPGA developer or small hardware team debugging hand-written control logic.
- **Primary job:** Diagnose and repair a failing leaf module.
- **90-day success:** FIFO and arbiter packs both work end-to-end, at least ten previously unseen implementations are evaluated, and results state detection and verified-repair rates with their denominators.
- **Constraint:** Remain local-first and single-user until the verification model is proven across multiple contracts.

## Key Assumptions to Validate

- [ ] Developers will accept a canonical interface or thin adapter in exchange for trustworthy diagnosis. Test this with five representative designs or developer interviews.
- [ ] The current workflow can support a second contract without duplicating most orchestration. Test this by measuring how much arbiter-specific code stays inside the new pack.
- [ ] Evidence-backed diagnosis is more useful than pasting RTL into a general chatbot. Test this by comparing whether developers can identify and fix the same defects with each workflow.
- [ ] The selected NVIDIA model can produce valid bounded patches at a useful rate. Test this against a versioned defect corpus after Nebius access is available.

## MVP Scope

- Extract FIFO-specific semantics behind a contract-pack boundary while preserving current behavior and benchmarks.
- Add one round-robin arbiter contract with a canonical interface.
- Add an executable arbiter oracle, directed cases, randomized sequences, and independently structured correct and defective fixtures.
- Let the CLI and web interface select between the FIFO and arbiter packs.
- Preserve the existing timeline, first-failure evidence, candidate diff, locked regression result, and downloadable artifact bundle.
- Complete offline diagnosis and regression first; enable bounded repair through the existing Nebius provider when access is available.

## Not Doing (and Why)

- **Arbitrary RTL projects** — a trustworthy verdict requires a declared, executable specification.
- **Automatic prose-to-contract generation** — generated tests cannot independently validate generated repairs.
- **UVM or vendor-project ingestion** — integration complexity would overwhelm the core experiment.
- **Formal correctness claims** — the product deliberately reports bounded simulation evidence.
- **CDC, asynchronous logic, and analog behavior** — these require materially different verification models.
- **Cloud accounts and team workspaces** — premature before repeatable single-user value is demonstrated.
- **CI and IDE integrations** — useful only after multiple contract packs prove the abstraction.

## Likely Follow-on Packs

If the arbiter validates the architecture, consider these in order:

1. Ready/valid skid buffer.
2. Parameterized counter or timer.
3. Fixed-priority arbiter.
4. Register file.
5. Simple synchronous RAM wrapper.

## Open Questions

- Should interface adaptation be explicit wrapper RTL, a manifest, or both?
- Which arbiter fairness properties belong in simulation, and which should remain outside the product's claims?
- How should contract-pack versions appear in reports so old evidence remains reproducible?
- What detection and repair thresholds would justify building the third pack?
