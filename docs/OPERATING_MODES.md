# IrrigationOS Operating Modes

## Purpose

Operating modes define what IrrigationOS is permitted to do. They are safety boundaries, not merely UI labels.

## Observation

- Reads controller and environmental data.
- Publishes entities and diagnostics.
- Records observed external watering.
- Does not create executable irrigation plans.
- Does not call any watering-control endpoint.

This is the mandatory initial mode for every installation.

## Simulation

- Builds water-demand assessments and nightly plans.
- Simulates cycle-and-soak timing and resource use.
- Produces explanations and predicted outcomes.
- Does not send commands.

Simulation must be deterministic for a fixed evaluation context.

## Shadow

- Builds the plan IrrigationOS would have executed.
- Observes actual controller behavior during the same period.
- Compares planned and actual watering, timing, and outcomes.
- Does not send commands.

Shadow mode provides commissioning evidence before Live activation.

## Live

- May dispatch approved canonical operations through the controller adapter.
- Requires explicit user activation.
- Requires healthy command attribution, ownership, diagnostics, and Flight Recorder subsystems.
- Enforces hard watering boundaries, including no start before the allowed window and no operation beyond the sunrise safety boundary.
- Preserves external/manual operation unless an explicit safety policy requires intervention.

## Promotion rules

Promotion is one-way only after explicit approval:

```text
Observation -> Simulation -> Shadow -> Live
```

A system may automatically demote to a safer mode after faults. It must never automatically promote to a more permissive mode.

## Demotion triggers

Examples include:

- authentication failure;
- stale or contradictory critical observations;
- repeated command timeouts;
- attribution or ownership failure;
- Flight Recorder failure during Live mode;
- restart state that cannot be reconciled safely;
- user safety stop.

## Capability gates

Code may contain future execution components before Live mode exists, but all control endpoints must remain unreachable unless the required mode and safety gates are satisfied.
