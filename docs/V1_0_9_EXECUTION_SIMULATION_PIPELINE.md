# IrrigationOS v1.0.9 Execution Simulation Pipeline Integration

## Purpose

v1.0.9 integrates the existing deterministic Execution engine into the synchronized Home Assistant pipeline while preserving the Observation-and-simulation-only operating boundary.

The pipeline now evaluates:

`Observations -> Knowledge -> Water Requirement -> Stress -> Health -> Recommendations -> Planning -> Scheduling -> Execution Simulation`

Runtime Monitoring remains downstream and blocked until its dedicated integration milestone.

## Integration contract

The Home Assistant pipeline passes each canonical proposed `IrrigationSchedule` unchanged into the existing `build_execution_plan()` domain engine. The adapter does not recompute scheduling or upstream science.

For every configured irrigation area, the pipeline stores an immutable `AreaExecutionEvaluation` containing either:

- the canonical `ExecutionPlan`; or
- explicit blocker codes when no schedule exists.

Schedule, scheduled-action, command, and idempotency provenance remain canonical and deterministic.

## Safety boundary

This milestone is simulation-only.

The pipeline may produce immutable controller-command models describing what would be required to execute a genuinely scheduled action, but it does not deliver those commands. No controller adapter methods, Rachio API methods, Home Assistant services, valves, switches, or other hardware transports are invoked by this pipeline stage.

The existing Execution engine's safety-block, idempotency, acknowledgement, retry, timeout, and rejection contracts remain unchanged. v1.0.9 does not implement retries or acknowledgements against live hardware.

## Conservative current behavior

v1.0.8 intentionally introduced no fabricated watering windows. As a result, current pipeline schedules generally preserve manual-only or unschedulable actions rather than runnable scheduled actions. Execution simulation therefore truthfully produces `NO_COMMANDS` where no scheduled command is available.

`NO_COMMANDS` is represented as a partial pipeline stage rather than as successful live execution. Missing schedules remain blocked.

## Explicit non-goals

v1.0.9 does not:

- start or stop an irrigation zone;
- call Rachio command endpoints;
- invoke Home Assistant control services;
- create watering windows;
- promote simulation to autonomous execution;
- implement runtime command acknowledgement or retry loops; or
- integrate Runtime Monitoring.
