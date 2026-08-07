# IrrigationOS v1.0.12 — Home Assistant Lifecycle Validation

## Purpose

v1.0.12 validates that the completed observation-and-simulation pipeline behaves as a durable Home Assistant integration across normal config-entry lifecycle transitions.

## Validated lifecycle contract

The Home Assistant smoke suite now verifies that:

- a version-3 persisted config entry starts the complete pipeline successfully;
- canonical controller identities and landscape-profile options survive unload/setup transitions unchanged;
- pipeline stage and per-zone pipeline-output entity registry IDs remain stable across unload/setup;
- config-entry reload replaces runtime coordinator state without creating duplicate entity-registry unique IDs;
- pipeline entities retain the same Home Assistant entity IDs across reload;
- a legacy version-1 entry migrates to the canonical version-3 identity/profile model and can then start the completed pipeline;
- migrated areas receive canonical per-zone pipeline-output entities after startup.

## Persistence boundary

v1.0.12 does not add a new persistence store. Durable state remains limited to the existing Home Assistant config-entry data/options contracts, including the canonical identity registry and configured landscape profiles. Pipeline evaluations remain derived immutable runtime state and are rebuilt from current observations and persisted configuration after startup or reload.

## Safety boundary

This is a validation milestone only. It does not change domain algorithms, scheduling policy, execution simulation, Runtime Monitoring semantics, controller adapters, Rachio command behavior, or Home Assistant service exposure.

Observation mode remains the default. Live irrigation execution remains disabled.

## Next milestone

The next v1.0 completion step is to freeze the public domain APIs and compatibility contracts for the completed pipeline.
