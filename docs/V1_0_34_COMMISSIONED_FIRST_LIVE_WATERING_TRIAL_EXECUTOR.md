# v1.0.34 — Commissioned First-Live Watering Trial Executor

## Scope

v1.0.34 adds the narrow executable core for one supervised first-live watering trial. It does not add general Live mode, autonomous scheduling, a Home Assistant execution service, a button, or a coordinator dispatch path.

## Safety boundary

A dispatch attempt is permitted only when the existing live-commissioning manager still reports `first_live_trial_eligible`. The request must exactly match the approved canonical controller identity, controller slot, area slot, and runtime. Runtime remains capped at 120 seconds.

Immediately before dispatch, the executor re-resolves the target from a fresh current Rachio controller snapshot. The canonical controller must still be observed, online, enabled, and Rachio-bound. The approved area must still exist, be configured, enabled, Rachio-bound, and not already watering. Native Rachio identifiers are derived internally from that observed binding rather than accepted from the execution request.

A privacy-safe canonical dispatch-intent audit event must be durably written before actuation is allowed. Native Rachio identifiers are excluded from this audit evidence.

The ephemeral approval is consumed **before** the transport call. This is intentional: a timeout or other ambiguous network result cannot leave behind a reusable approval that might cause duplicate watering. There are no automatic retries. A transport failure is reported as `transport_outcome_unknown`, not success.

## Authority retained outside this milestone

- Observation remains the default and only commissioned operating mode.
- No HA service, switch, button, scheduler callback, or coordinator callback invokes the executor.
- General `live_control_authorized` remains false.
- Autonomous scheduling remains disabled.
- Post-start acknowledgement, observed watering acceptance, stop acknowledgement, safety preemption evidence, and post-run reconciliation remain required before broader authority can be considered.
