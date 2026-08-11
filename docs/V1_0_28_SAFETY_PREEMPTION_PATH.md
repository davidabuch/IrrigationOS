# v1.0.28 — Safety Preemption Path

## Purpose

Implement the fourth Live-mode safety safeguard without enabling controller command delivery.

## Behavior

- Evaluates deterministic fail-closed preemption reasons for unhealthy system state, stale observations, unavailable controllers, missing ownership, active-watering conflicts, and execution authorization that is not manual-review eligible.
- Terminates an outstanding synthetic acknowledgement lifecycle with a terminal `preempted` state.
- Persists immutable preemption evidence for 30 days.
- Exposes privacy-safe diagnostics while keeping `dispatch_capability` false.

## Safety boundary

This milestone does not send start, stop, or emergency-stop commands to Rachio or any controller. Live-mode commissioning, feature enablement, and authorization remain false.

## Next milestone

Implement the sunrise hard-stop safeguard behind the disabled Live-mode boundary.
