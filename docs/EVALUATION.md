# Evaluation Record

All results below were produced on October 15, 2026. They are bounded simulation evidence for the named contracts and configurations, not formal verification or a claim about arbitrary RTL.

## Live Nebius/NVIDIA repair

Run id: `0a3c9445a8864d89b5f70b091e777a23`

| Measure | Result |
|---|---|
| Input | bundled FIFO `case-001`, `DATA_WIDTH=8`, `DEPTH=3` |
| Provider/model | Nebius Token Factory / `nvidia/nemotron-3-super-120b-a12b` |
| Provider requests | 2 |
| Usage | 1,789 prompt, 683 completion, 2,472 total tokens |
| Provider latency | 1,867 ms investigation; 3,214 ms patch |
| Baseline | `functional_mismatch`, first failure at cycle 7 |
| Investigation | `functional_mismatch` after exact baseline-prefix replay |
| Reproducer | passed, 8 transactions |
| Locked regression | passed, 80 transactions |
| Locked assets | unchanged |
| Final verdict | `candidate_passed_listed_tests` |

Candidate SHA-256: `a2244aa9657ed91e9c8022c3402d2417e138f05181b1ff33c1adbc98f8cfd56b`

The portable `report.json` was 35,981 bytes with SHA-256 `CAC985376F92E4BC0CE16A6DCDD2097B38434B6848DC23B22298BAC2C4EC9239`. The 24,914-byte `artifact-bundle.zip` had SHA-256 `A921C538D63D3420C381C1DC35629357C92C4660F7A3E5151021BCDAFEF3C516`.

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
- An earlier live candidate unnecessarily changed the module's default `DEPTH` while the harness explicitly instantiated `DEPTH=3`. That review led to deterministic host-side header restoration and a guard that rejects any surviving change to parameter defaults or ports.
- A bounded confirmation then returned `repair_not_verified` when the pre-normalization guard rejected the same specialization. The final live run above exercised the hardened path: its event trail records header restoration, and its candidate passed the reproducer and locked regression without changing the interface.
- Expected benchmark labels are not included in model prompts.
- The full regression is independent of the model-generated investigation stimulus.
- When that stimulus did not reproduce the already-observed failure, the workflow replayed the exact baseline transaction prefix and recorded the fallback in the event trail; it did not spend another model request.
- Supported interfaces are intentionally narrow: canonical single-clock synchronous FIFO and round-robin arbiter. There is no CDC, asynchronous FIFO, UVM, synthesis, timing closure, or hardware-board claim.
