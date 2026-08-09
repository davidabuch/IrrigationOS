# IrrigationOS Operating Modes

## Purpose

Operating modes define what IrrigationOS is permitted to do. They are safety boundaries, not merely UI labels.

## Current release-candidate boundary

The v1.0.14 Home Assistant integration is commissioned in **Observation** mode only. The completed domain pipeline may calculate advisory recommendations, proposed plans/schedules, simulated execution commands, and conservative runtime-monitoring outputs, but **no watering-control endpoint is called**.

`Simulation`, `Shadow`, and `Live` describe progressively more permissive product states. They are not currently user-commissionable modes in the v1.0.14 integration.

## Observation — implemented

- Reads controller and environmental data.
- Builds the synchronized deterministic domain pipeline.
- Publishes read-only observation and simulation entities and redacted diagnostics.
- Records current external/controller watering observations where available.
- May create proposed schedules and simulated command models.
- Does not dispatch start, stop, enable, disable, or reschedule commands.

This is the mandatory initial and current mode for every installation.

## Simulation — future explicit mode

- Uses the same deterministic pipeline while making simulation intent explicit to the user.
- Exercises proposed scheduling and command generation without transport.
- Produces explanations and predicted outcomes.
- Does not send commands.

## Shadow — future commissioning mode

- Builds the plan IrrigationOS would have executed.
- Observes actual controller behavior during the same period.
- Compares planned and actual watering, timing, and outcomes.
- Does not send commands.

Shadow mode is intended to provide evidence before Live activation.

## Live — future control mode

- May dispatch approved canonical operations through the controller adapter.
- Requires explicit user activation and commissioning.
- Requires command attribution, ownership, safety, diagnostics, and durable audit/reconciliation capabilities.
- Must preserve external/manual operation unless an explicit safety policy requires intervention.

Live mode is **not enabled in the current release candidate**.

## Promotion rules

The intended promotion path is:

```text
Observation -> Simulation -> Shadow -> Live
```

A system may demote to a safer mode after faults. It must never automatically promote to a more permissive mode.

## Capability gates

Code may contain models or adapter capabilities needed by future control features. Their presence does not make live execution available. No control endpoint may become reachable without an explicit versioned commissioning milestone, safety gates, and tests.
