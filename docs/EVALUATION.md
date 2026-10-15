# Evaluation Record

All results below were produced on October 14, 2026. They are bounded simulation evidence for the named contracts and configurations, not formal verification or a claim about arbitrary RTL.

## Live Nebius/NVIDIA repair

Run id: `15874ea33720468189c69695438cbad2`

| Measure | Result |
|---|---|
| Input | bundled FIFO `case-001`, `DATA_WIDTH=8`, `DEPTH=3` |
| Provider/model | Nebius Token Factory / `nvidia/nemotron-3-super-120b-a12b` |
| Provider requests | 2 |
| Usage | 1,840 prompt, 825 completion, 2,665 total tokens |
| Provider latency | 1,595 ms investigation; 3,742 ms patch |
| Estimated inference cost | `$0.001295` at the catalog rates observed that day |
| Baseline | `functional_mismatch`, first failure at cycle 7 |
| Investigation | `functional_mismatch` after exact baseline-prefix replay |
| Reproducer | passed, 8 transactions |
| Locked regression | passed, 80 transactions |
| Locked assets | unchanged |
| Final verdict | `candidate_passed_listed_tests` |

Candidate SHA-256: `562129ef969a0e56e4818637dba9dfa7ad54de6f5086e437f56a28e10794d6ab`

The portable `report.json` was 37,608 bytes with SHA-256 `F4A80AAC1AE9EA2CB86B935D5E0CBFFCDDE6F0F1E40E711142425F1E65DF0020`. The 26,014-byte `artifact-bundle.zip` had SHA-256 `242F3C9616EC391553B5A90F3E9DB03168E22097F0A0B11D40C577F0B73BFFD8`.

## Offline verification

- Bundled hidden-label benchmark: 10/10 outcomes matched their manifest—6 functional mismatches and 4 passing designs across FIFO and round-robin arbiter packs.
- FIFO parameter matrix: 18/18 configurations passed for `DATA_WIDTH={1,8,16}` × `DEPTH={1,2,3,4,7,8}`.
- Three recorded seeds per matrix configuration: 54/54 seed/configuration combinations passed.
- A correct design stops after the baseline and makes zero model calls.

Reproduce locally:

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_benchmarks.py
.\.venv\Scripts\python -m backend.evaluate --source benchmark/designs/correct/reference_fifo.sv
```

## Interpretation and limits

- The successful live run demonstrates one end-to-end repair, not a repair-rate benchmark.
- Expected benchmark labels are not included in model prompts.
- The full regression is independent of the model-generated investigation stimulus.
- When that stimulus did not reproduce the already-observed failure, the workflow replayed the exact baseline transaction prefix and recorded the fallback in the event trail; it did not spend another model request.
- Supported interfaces are intentionally narrow: canonical single-clock synchronous FIFO and round-robin arbiter. There is no CDC, asynchronous FIFO, UVM, synthesis, timing closure, or hardware-board claim.
- Cost is an estimate from the observed token counts and the live catalog rates on the run date; provider billing is authoritative.
