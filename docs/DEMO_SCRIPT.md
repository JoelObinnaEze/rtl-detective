# Three-Minute Demo Script

Target length: 2:45–2:55. Record the hosted build in one take; this is a product pitch, not a setup tutorial.

## 0:00–0:20 — Stakes

"A plausible RTL patch can compile and still be wrong by one clock cycle. RTL Detective is a proof-carrying repair agent: NVIDIA Nemotron proposes, but deterministic Verilator evidence decides."

Show the dark workbench and point to `Nebius Token Factory × NVIDIA Nemotron`.

## 0:20–0:45 — Real failure

Select the synchronous FIFO and `case-001`, then start verification. Explain that the design is tested against a human-authored executable oracle using directed plus seeded-random transactions. Show the baseline mismatch: cycle, transaction, expected signals, and observed signals.

## 0:45–1:20 — Agent investigation

Follow the live states: baseline → investigating → patching. Say that only bounded evidence and the DUT reach the model; credentials, tests, and the oracle do not. If the model's proposed stimulus does not reproduce, call out the visible baseline-prefix replay rather than hiding it or spending another request.

## 1:20–1:50 — Candidate under test

Show the diagnosis and candidate diff. Explain that Nemotron returns structured source lines, the host builds the canonical diff, and the only editable file is `dut.sv`. Point out that test-disabling code and simulator control tasks are rejected before execution.

## 1:50–2:25 — Proof gates

On completion, walk down the gate panel:

1. baseline mismatch recorded;
2. NVIDIA model and token usage recorded;
3. failing reproducer recorded;
4. candidate passes the locked regression;
5. verification assets are byte-for-byte unchanged;
6. one bounded attempt, with no silent retries.

Say the exact claim shown by the product: "Candidate passed the reproducer and listed locked regression tests." Do not call it formal proof.

## 2:25–2:45 — Auditability

Download `artifact-bundle.zip` and briefly show `report.md` or `report.json`. Mention the source/candidate hashes, simulator version, traces, provider metadata, exact transactions, and separate logs.

## 2:45–2:55 — Close

"RTL Detective shortens the first hardware-debug loop without asking engineers to trust AI confidence. It hands them a candidate and the evidence to review it."

## Recording checklist

- Use the public URL and submitted commit.
- Keep the browser at 100% zoom and terminal notifications hidden.
- Never show environment variables, cloud dashboards, or the API key.
- Confirm the video is public, under three minutes, and audible before adding it to Devpost.
