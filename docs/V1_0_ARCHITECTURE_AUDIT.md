# IrrigationOS v1.0 Architecture Audit

## Status

Completed for the v1.0 architecture-freeze branch.

## Baseline

- 449 tests pass.
- Repository validation passes.
- The deterministic domain pipeline is complete through Runtime Monitoring.
- Home Assistant remains observation-only and does not yet invoke the completed domain pipeline.

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
    -> Execution
    -> Runtime Monitoring
```

Each layer has one responsibility and consumes immutable upstream outputs. No downstream
layer recomputes upstream science.

## Findings

### No release-blocking engine redesign

The domain packages have clear boundaries, immutable models, deterministic engines,
explicit schema and algorithm versions, and downstream provenance. No repository-wide
model rename or package reorganization is justified before v1.0.

### Release metadata is stale

The installable Home Assistant integration reported v0.4.2 at audit time in `manifest.json`,
`const.py`, `pyproject.toml`, validation scripts, tests, README, and roadmap documents.
This is accurate for the currently wired Home Assistant runtime, but it does not describe
the completed v0.9.5 domain pipeline.

The integration version must not be changed to v1.0.0 until the v1.0 Home Assistant
wiring and release validation are complete.

### Home Assistant wiring is incomplete

The coordinator currently refreshes controller observations and the early Landscape
Digital Twin only. It does not yet execute the completed domain pipeline or expose its
recommendations, plans, schedules, execution simulations, or runtime reports.

This is the primary product-integration milestone remaining before v1.0.

### Documentation requires reconciliation

The roadmap and architecture documents still emphasize the v0.4.2 observation release
and older monolithic Decision Engine terminology. They must be reconciled with the
layered domain pipeline before release.

### Public API freeze needs enforcement

Stable package exports exist, but the repository did not have one explicit compatibility
test that freezes the public symbols of the v1.0 domain pipeline. That contract is added
by this milestone.

## v1.0 release sequence

1. Freeze and test public domain APIs.
2. Reconcile roadmap and architecture documentation.
3. Wire the complete pipeline into the Home Assistant coordinator in observation and
   simulation modes.
4. Expose stable Home Assistant entities and diagnostics for recommendations, plans,
   schedules, execution simulation, runtime status, blockers, and provenance.
5. Validate startup, reload, migration, persistence, and entity lifecycle in Home
   Assistant.
6. Complete release metadata, release notes, and version bump to v1.0.0.
7. Deploy initially with live execution disabled.

## Deferred beyond v1.0

- Additional controller brands.
- Automatic recovery execution.
- AI-generated decisions.
- Breaking domain-model redesign without a versioned migration.
