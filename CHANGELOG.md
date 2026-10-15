# Changelog

## [Unreleased]

### Added

- Canonical FIFO oracle, deterministic/random verification, Verilator VCD pipeline, six-case benchmark, bounded Nebius repair loop, isolated worker policy, CLI/API/web UI, persistent events, and downloadable reports.
- Contract-pack architecture and a canonical round-robin arbiter pack with its own oracle, directed/random transactions, four-case benchmark, CLI/API selection, trace evidence, and dark-theme web controls.

### Changed

- Refined the dark verification workspace with clearer hierarchy, an explanatory signal pipeline, responsive result panels, and precise reduced-motion-aware interaction feedback.
- Generalized the verification, repair, report, and artifact workflow while keeping the FIFO API and CLI defaults backward compatible.

### Fixed

- Stream FastAPI events from a native async generator, mask generated RTL literals to `DATA_WIDTH`, and give the isolated Verilator worker a practical bounded file limit with compiler caching disabled.
- Publish terminal run status only after artifacts and the evidence-backed verdict are persisted, preventing the UI from racing to a generic completion label.

