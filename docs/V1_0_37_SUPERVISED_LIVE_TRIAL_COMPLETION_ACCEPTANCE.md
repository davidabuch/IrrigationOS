# v1.0.37 — Supervised Live Trial Completion & Acceptance Evidence

## Purpose

v1.0.37 closes the evidence gap discovered during the first successful supervised physical watering trial. v1.0.36 durably recorded dispatch intent and Rachio HTTP acceptance, but did not continue observing the commanded area through physical completion.

## Boundary

After a supervised first-live start is accepted, IrrigationOS launches a Home Assistant background task. The task requests canonical controller refreshes and observes only the already-approved controller and area slot. It records `target_watering_observed` when the canonical state becomes `WATERING`, then records `first_live_trial_accepted` when that same area returns to `IDLE`.

If watering is not observed within the bounded start grace period, or completion is not observed within the requested runtime plus bounded completion grace period, the task writes explicit terminal failure evidence. Refresh failures are tolerated only until those deadlines; they never cause a retry of the watering command.

## Safety properties

- No second start command is issued.
- No automatic retry is permitted.
- No additional controller or area can be selected by the monitor.
- The monitor uses provider-neutral canonical state after dispatch.
- Native Rachio identifiers are absent from acceptance audit events.
- General Live mode and autonomous scheduling remain disabled.
- `live_control_authorized` remains false.
- Operator approval remains ephemeral and single-use.

## Acceptance evidence

All events for one attempt share the same privacy-safe `attempt_id`:

1. `dispatch_intent` / `commissioned_first_live_start`
2. `transport_outcome` / `start_http_accepted`
3. `acceptance_observation` / `target_watering_observed`
4. `acceptance_terminal` / `first_live_trial_accepted`

A terminal failure instead uses `watering_not_observed_within_grace` or `completion_not_observed_within_grace`.
