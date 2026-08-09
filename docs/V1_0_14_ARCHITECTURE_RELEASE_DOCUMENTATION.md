# IrrigationOS v1.0.14 — Architecture and Release Documentation Reconciliation

## Purpose

Reconcile the canonical architecture and release documents with the implementation that actually shipped through v1.0.13, without changing runtime behavior.

## Reconciled documents

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/IRRIGATIONOS_ARCHITECTURE_V1.md`
- `docs/OPERATING_MODES.md`
- `docs/RELEASE_STRATEGY.md`
- `docs/ROADMAP.md`
- `docs/V1_0_ARCHITECTURE_AUDIT.md`

## Key corrections

1. The Home Assistant coordinator **does** invoke the completed domain pipeline.
2. Pipeline entities, diagnostics, lifecycle validation, and the public API freeze are complete rather than pending.
3. Execution is explicitly **simulation-only**; generated command models are not dispatched.
4. Observation is the only currently commissioned operating mode. Simulation, Shadow, and Live are distinguished as progressively more permissive future product states.
5. Command attribution, ownership, automatic recovery, Flight Recorder-backed live accountability, direct Open-Meteo defaults, and SSURGO onboarding remain target-state architecture unless a later milestone marks them complete.
6. GitHub `main` is documented as the authoritative repository state; fresh local ZIP snapshots are requested only when local state materially matters.

## Safety boundary

This milestone changes documentation, release metadata, and documentation-contract tests only. It does not alter domain logic, Home Assistant entity behavior, controller adapters, scheduling, execution simulation, or runtime monitoring. Live execution remains disabled.

## Remaining before stable public release

- resolve the final public semantic version; because internal milestones already use `1.0.13`/`1.0.14`, a later `1.0.0` tag would be a SemVer downgrade;
- reconcile release metadata and release notes, including the historical `pyproject.toml` project version;
- run final release-candidate validation against the frozen public API and Home Assistant lifecycle contracts;
- deploy/distribute with live execution disabled by default.
