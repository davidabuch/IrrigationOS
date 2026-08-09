# IrrigationOS v1.0.15 Release Notes

## Release status

**Live execution remains disabled.** IrrigationOS v1.0.15 does not enable or automatically commission live irrigation control.

IrrigationOS v1.0.15 is the first stable public release candidate for the completed v1.0 architecture line.

The version is intentionally 1.0.15 rather than 1.0.0 because the repository already published internal v1.0.x implementation milestones through 1.0.14. Using 1.0.15 preserves monotonic semantic version ordering for Home Assistant, HACS, Python packaging, and other update-aware tooling.

## What is included

- Direct Rachio account, controller, and zone discovery through the IrrigationOS integration.
- Canonical controller identities and stable permanent irrigation-area slots.
- Realtime observation with webhook/cloudhook support and polling reconciliation fallback.
- Canonical weather normalization and landscape-profile inputs.
- Deterministic Plant Water Requirement, Plant Stress, Plant Health, Recommendations, Planning, Scheduling, Execution simulation, and Runtime Monitoring pipeline stages.
- Stable Home Assistant pipeline stage and per-zone output entities.
- Redacted diagnostics with pipeline summaries and provenance-safe metadata.
- Startup, reload, migration, persistence, and entity-lifecycle regression coverage.
- Frozen v1.0 public API compatibility contract with machine-readable enforcement.
- Synchronized package, Home Assistant integration, validation, and test version metadata.

## Safety boundary

v1.0.15 does not autonomously control irrigation.

Observation is the only commissioned operating mode. Simulation may construct non-actuating execution plans, but no live start, stop, enable, disable, schedule-change, retry, or recovery command path is commissioned in this release.

Shadow commissioning, live command ownership/attribution, and autonomous execution remain future separately reviewed work.

## Compatibility

The frozen v1.0 public API contract established in v1.0.13 remains authoritative. v1.0.15 introduces no intentional breaking changes to that contract.

## Validation required before tagging

The release commit must pass:

- the complete standard pytest suite;
- Home Assistant smoke/lifecycle tests;
- Ruff;
- MyPy;
- repository validation;
- `git diff --check`;
- GitHub Actions on the merged `main` commit.

Only after those checks are green should `v1.0.15` be tagged or released.

## Distribution

Creating the GitHub tag/release and enabling broader public distribution are explicit post-merge actions. A successful merge does not by itself publish or commission live control.
