# Demo Voice Lines

Record each paragraph as a separate clip in a quiet room. Leave about half a second of silence before and after each take. WAV or high-quality M4A is preferred; do not add music or effects.

## 01-stakes — 0:00–0:20

“A plausible RTL patch can compile and still be wrong by one clock cycle. RTL Detective is a proof-carrying repair agent for SystemVerilog: NVIDIA Nemotron proposes, but deterministic Verilator evidence decides.”

## 02-baseline — 0:20–0:45

“I select a canonical synchronous FIFO and start verification. The design is compiled and tested against a human-authored executable oracle using directed and seeded-random transactions. When behavior diverges, RTL Detective records the exact cycle, input transaction, expected signals, and observed signals.”

## 03-investigation — 0:45–1:20

“Only the untrusted DUT and bounded failure evidence go to NVIDIA Nemotron through Nebius Token Factory. The API key, oracle, and locked tests never enter the prompt. The model returns structured investigation data and a candidate source file. If its proposed stimulus does not reproduce the bug, the host falls back to the exact baseline failure prefix instead of hiding the result or spending another request.”

## 04-candidate — 1:20–1:50

“The model’s answer is only a hypothesis. RTL Detective restores the locked module header, builds the canonical diff itself, and rejects test-disabling code, simulator control tasks, foreign files, path traversal, symlinks, and oversized input. The candidate then runs with no network access and strict CPU, memory, process, file-size, and time limits.”

## 05-gates — 1:50–2:25

“A successful claim requires every visible gate: the baseline mismatch is recorded; the NVIDIA model, request, latency, and token usage are captured; a failing reproducer is saved; the candidate passes that reproducer and the independently locked regression; and every verification asset remains byte-for-byte unchanged. The product says only that the candidate passed the listed simulation tests. It never calls this formal proof.”

## 06-artifacts — 2:25–2:45

“The downloadable proof bundle contains a readable report, canonical JSON, original and candidate hashes, the simulator version, exact transactions, waveform traces, provider metadata, and separate logs. An engineer can replay the evidence without trusting the model’s explanation.”

## 07-close — 2:45–2:55

“RTL Detective shortens the first hardware-debug loop without asking engineers to trust AI confidence. It hands them a candidate and the evidence to review it.”
