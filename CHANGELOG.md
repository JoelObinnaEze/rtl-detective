# Changelog

## [Unreleased]

### Added

- Canonical FIFO oracle, deterministic/random verification, Verilator VCD pipeline, six-case benchmark, bounded Nebius repair loop, isolated worker policy, CLI/API/web UI, persistent events, and downloadable reports.
- Contract-pack architecture and a canonical round-robin arbiter pack with its own oracle, directed/random transactions, four-case benchmark, CLI/API selection, trace evidence, and dark-theme web controls.
- A schema-versioned proof record with deterministic claims, run limits, source and locked-asset integrity hashes, exact executed investigation stimuli, provider telemetry, candidate disposition, and separate reproducer/regression evidence.
- Portable JSON, Markdown, and ZIP proof artifacts with an explicit artifact manifest, externalized simulator logs, and a sanitized fallback report for unexpected orchestrator failures.
- A judge-facing verification gate panel, provider/model evidence, health endpoint, evaluation record, deployment runbook, Devpost copy, and three-minute demo script.

### Changed

- Refined the dark verification workspace with clearer hierarchy, an explanatory signal pipeline, responsive result panels, and precise reduced-motion-aware interaction feedback.
- Generalized the verification, repair, report, and artifact workflow while keeping the FIFO API and CLI defaults backward compatible.
- Made successful repair claims depend on passing the replayed reproducer, the full locked regression suite, and locked-asset integrity rather than model output.
- Capped live inference at one repair attempt with zero provider retries by default, disabled Nemotron reasoning tokens for schema-only calls, and made Nemotron return structured source lines while the host generates the canonical diff.

### Fixed

- Stream FastAPI events from a native async generator, mask generated RTL literals to `DATA_WIDTH`, and give the isolated Verilator worker a practical bounded file limit with compiler caching disabled.
- Publish terminal run status only after artifacts and the evidence-backed verdict are persisted, preventing the UI from racing to a generic completion label.
- Resolve contract-aware CLI defaults, apply bundled manifest parameters when omitted, reject empty source selectors, and block DUT simulation I/O or control tasks from corrupting evidence.
- Encode untrusted provider metadata in Markdown reports, redact provider exception details from persisted evidence, and update pytest to 9.0.3 for the temporary-directory security fix.
- Replay the exact baseline transaction prefix when model-proposed stimulus passes without reproducing the known failure, preserving an honest trace instead of requesting another model response.

