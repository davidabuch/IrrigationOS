# IrrigationOS v1.0.10 Runtime Monitoring Pipeline Integration

## Purpose

v1.0.10 integrates the existing deterministic Runtime Monitoring engine into the synchronized Home Assistant pipeline while preserving the Observation-and-simulation-only operating boundary.

## Architecture

The pipeline now reaches the complete frozen v1.0 domain chain:

```text
Scientific Inputs
  -> Water Requirement
  -> Plant Stress
  -> Plant Health
  -> Recommendations
  -> Planning
  -> Scheduling
  -> Execution Simulation
  -> Runtime Monitoring
```

The pipeline adapter consumes canonical `ExecutionPlan` objects and delegates runtime assessment to the existing `build_runtime_report()` domain engine. It does not duplicate runtime-monitoring logic or recompute upstream evidence.

## Truthful simulation boundary

The Home Assistant pipeline does not yet have a live command-result stream for IrrigationOS-issued commands because live execution remains disabled. Therefore v1.0.10 does not fabricate acknowledgements, retries, timeouts, rejections, or interruption state.

- `NO_COMMANDS` execution plans can be evaluated as `NO_EXECUTION`.
- blocked execution plans preserve their blocked state.
- execution plans containing runnable simulated commands remain explicitly unavailable for runtime reconciliation until truthful command-result and interruption observations exist.
- controller availability is taken only from the synchronized controller snapshot; unknown availability is not converted into a false online/offline assertion.

## Provenance

Each area-level runtime result preserves the canonical source `ExecutionPlan`, which in turn preserves Scheduling, Planning, Recommendation, and upstream evidence provenance.

## Safety

v1.0.10 does not:

- call a controller adapter or the Rachio API;
- issue Home Assistant service calls;
- start, stop, retry, or reschedule irrigation;
- execute recovery recommendations;
- infer successful or failed command delivery without evidence.

Observation mode remains the default operating mode. Simulation artifacts are descriptive, not authorization to actuate hardware.

## Next milestone

With the complete frozen domain pipeline now wired into Home Assistant, the next release-completion milestone is to expose stable observation and simulation entities and diagnostics for these pipeline outputs.
