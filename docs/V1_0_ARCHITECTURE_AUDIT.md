# IrrigationOS v1.0 Architecture Audit

## Status

Reconciled through **v1.0.14**. The original audit identified the work required to integrate the completed domain pipeline into Home Assistant; that integration work is now complete through the release-candidate boundary described below.

## Current baseline

- The deterministic domain pipeline is complete through Runtime Monitoring.
- The Home Assistant coordinator invokes the synchronized pipeline on refresh.
- Stable per-stage and per-zone pipeline entities and redacted diagnostics are exposed.
- Startup, unload/setup, config-entry reload, persistence, migration, and entity identity are regression-tested.
- The v1.0 domain and pipeline public API contracts are frozen by a machine-readable compatibility manifest and tests.
- The operating boundary remains **Observation and simulation only**.
- No pipeline output is dispatched to Rachio or another controller.

## Frozen domain pipeline

```text
Observations
    -> Knowledge
    -> Plant Water Requirement
    -> Plant Stress
    -> Plant Health
    -> Recommendations
    -> Planning
    -> Scheduling
    -> Execution simulation
    -> Runtime Monitoring
```

Each layer owns one responsibility, consumes immutable upstream outputs, preserves provenance, and has explicit schema/algorithm version contracts. Downstream layers do not recompute upstream science.

## Findings after reconciliation

### No release-blocking engine redesign

Still valid. The completed domain packages have clear boundaries, immutable models, deterministic engines, and explicit compatibility contracts. A repository-wide rename or package reorganization is not justified before v1.0.0.

### Home Assistant pipeline wiring — complete

Completed across v1.0.1 through v1.0.10. The coordinator now evaluates controller observations, Landscape Digital Twin/scientific evidence, Water Requirement, Stress, Health, Recommendations, Planning, Scheduling, Execution simulation, and Runtime Monitoring.

### Stable pipeline entities and diagnostics — complete

Completed in v1.0.11. Home Assistant exposes stable global stage sensors and compact per-zone pipeline outputs without recomputing domain logic. Diagnostics include a redacted pipeline summary and immutable evaluation snapshot.

### Lifecycle validation — complete

Completed in v1.0.12. Cold startup, unload/setup, reload, persisted identities/options, legacy migration, permanent slot identity, and duplicate-registry protections are covered by Home Assistant smoke tests.

### Public API freeze — complete

Completed in v1.0.13. `docs/V1_0_PUBLIC_API_CONTRACT.json` freezes exact public exports, schema/algorithm versions, enum values, and dataclass field order for the eight domain layers and synchronized pipeline. Compatibility tests fail on accidental drift.

### Architecture/release documentation — reconciled

Completed in v1.0.14. Canonical documents now distinguish implemented Observation/simulation behavior from future Shadow/Live architecture and no longer describe completed integration milestones as pending.

## Current safety boundary

Execution is simulation-only. Canonical command models may be generated, but no watering-control endpoint is invoked. Runtime Monitoring does not fabricate command outcomes for commands that were never sent.

Future live control requires an explicit commissioning milestone covering command attribution, ownership, acknowledgement/reconciliation, safety preemption, durable audit history, and user-controlled promotion.

## Remaining release work

1. Resolve the final public semantic version. Internal milestones already use `1.0.13`/`1.0.14`, so a later `1.0.0` tag would sort lower in SemVer-aware tooling.
2. Reconcile release metadata and release notes, including the historical `pyproject.toml` project version.
3. Run final release-candidate validation against the frozen public contract and Home Assistant lifecycle suite.
4. Deploy/distribute with live execution disabled by default.

## Deferred beyond the current v1.0 release candidate

- Shadow-mode commissioning and comparison against actual controller behavior.
- Live controller command dispatch.
- Command attribution and ownership enforcement for live operations.
- Automatic recovery execution.
- Flight Recorder-backed live accountability.
- Additional controller brands.
- AI-generated decisions.
- Breaking domain-model redesign without a versioned migration.
